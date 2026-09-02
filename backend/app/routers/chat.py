"""Chat AI 助手 — SSE 流式端点 + 对话持久化。"""

import json, logging, re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from app.database import get_db, async_session
from app.models.enterprise import AIConfig
from app.models.chat import ChatConversation, ChatMessage
from app.dependencies import get_current_user
from app.services.llm_client import llm_chat_completion, llm_collect_all, LLMError
from app.services.markdown_utils import md_to_html
from app.services.mermaid_renderer import render_mermaid_svg
from app.schemas.chat import ChatRequest, ConversationResponse, MessageResponse
from app.services.chat_dispatch import dispatch
from app.services.user_preference_service import get_preferences, invalidate_cache
from datetime import datetime, timezone
from app.services.sse_utils import sse_line
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

CHAT_CONTEXT_BUDGET = 8000
MAX_ROUNDS = 8  # 模块级常量：agent_loop 多轮工具调用上限


def _build_final_summary_prompt(completed: list, remaining: list) -> str:
    """超轮数时引导 LLM 输出部分成功总结。"""
    done = "、".join(completed) if completed else "无"
    todo = "、".join(remaining) if remaining else "无"
    return (f"这是最后一轮。请直接总结所有操作结果。每个操作必须说明成功与否（看verified字段）。"
            f"已完成操作：{done}；未完成操作：{todo}。不要调用更多函数。")

READ_TOOL_NAMES = frozenset({
    "get_dashboard", "list_enterprises", "get_enterprise", "list_risk_sources",
    "list_resources", "list_plans", "get_plan", "list_templates",
    "list_risk_assessments", "get_risk_assessment", "list_resource_investigations",
    "get_resource_investigation", "get_regulation_stats", "list_regulations",
    "search_regulations", "search_regulation_articles", "get_ai_config",
    "get_generation_progress", "get_workflow_progress", "get_preferences",
})

CHAT_TOOLS = [
    {"type": "function", "function": {"name": "get_dashboard", "description": "获取仪表盘统计概览：企业数、预案数(含已完成/生成中)、风险事件数、应急资源数", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "autofill_enterprise", "description": "智能添加企业：根据简称自动查询工商数据，校准为完整公司名称，同步填充信用代码、法人、行业、地址、注册资本等信息", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "企业名称或简称(必填)"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "list_enterprises", "description": "列出当前用户的所有企业，可按名称关键词搜索", "parameters": {"type": "object", "properties": {"keyword": {"type": "string", "description": "企业名称关键词"}}, "required": []}}},
    {"type": "function", "function": {"name": "get_enterprise", "description": "获取企业详情：基本信息+风险分级管控列表+应急资源列表+预案列表", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string"}, "name": {"type": "string", "description": "企业名称模糊匹配"}}, "required": []}}},
    {"type": "function", "function": {"name": "create_enterprise", "description": "创建新企业（手动填写，不自动填充工商数据。如需自动填充请用 autofill_enterprise）", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "企业名称(必填)"}, "industry": {"type": "string"}, "address": {"type": "string"}, "employee_count": {"type": "integer"}, "phone": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "update_enterprise", "description": "更新企业信息", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}, "name": {"type": "string"}, "industry": {"type": "string"}, "address": {"type": "string"}, "employee_count": {"type": "integer"}, "phone": {"type": "string"}}, "required": ["enterprise_id"]}}},
    {"type": "function", "function": {"name": "delete_enterprise", "description": "删除企业及其关联数据。不可逆操作，请先向用户确认。", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}}, "required": ["enterprise_id"]}}},
    {"type": "function", "function": {"name": "list_risk_sources", "description": "列出指定企业的风险分级管控数据", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}}, "required": ["enterprise_id"]}}},
    {"type": "function", "function": {"name": "list_resources", "description": "列出指定企业的所有应急资源", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}}, "required": ["enterprise_id"]}}},
    {"type": "function", "function": {"name": "create_resource", "description": "为企业创建应急资源", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}, "name": {"type": "string", "description": "资源名称(必填)"}, "category": {"type": "string", "description": "资源类别"}, "quantity": {"type": "integer", "description": "数量"}, "unit": {"type": "string", "description": "单位"}, "location": {"type": "string", "description": "存放地点"}}, "required": ["enterprise_id", "name"]}}},
    {"type": "function", "function": {"name": "update_resource", "description": "更新应急资源信息", "parameters": {"type": "object", "properties": {"resource_id": {"type": "string", "description": "资源ID(必填)"}, "name": {"type": "string"}, "category": {"type": "string"}, "quantity": {"type": "integer"}, "unit": {"type": "string"}, "location": {"type": "string"}}, "required": ["resource_id"]}}},
    {"type": "function", "function": {"name": "delete_resource", "description": "删除应急资源", "parameters": {"type": "object", "properties": {"resource_id": {"type": "string", "description": "资源ID(必填)"}}, "required": ["resource_id"]}}},
    {"type": "function", "function": {"name": "list_plans", "description": "列出预案：可按 enterprise_id 查某企业的预案，或按 keyword 搜索预案名称", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string"}, "keyword": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "get_plan", "description": "获取预案详情：基本信息+章节列表+各章节内容", "parameters": {"type": "object", "properties": {"plan_id": {"type": "string", "description": "预案ID(必填)"}}, "required": ["plan_id"]}}},
    {"type": "function", "function": {"name": "create_plan", "description": "创建新预案", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"}, "plan_type": {"type": "string", "description": "预案类型: 综合应急预案/专项应急预案/现场处置方案"}, "title": {"type": "string", "description": "预案名称(必填)"}, "accident_type": {"type": "string", "description": "事故类型"}}, "required": ["enterprise_id", "title"]}}},
    {"type": "function", "function": {"name": "delete_plan", "description": "删除预案及其所有章节。不可逆操作，请先向用户确认。", "parameters": {"type": "object", "properties": {"plan_id": {"type": "string", "description": "预案ID(必填)"}}, "required": ["plan_id"]}}},
    {"type": "function", "function": {"name": "list_templates", "description": "列出可用的预案模板", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "list_risk_assessments", "description": "列出企业的风险评估报告", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID"}}, "required": []}}},
    {"type": "function", "function": {"name": "get_risk_assessment", "description": "获取风险评估报告详情", "parameters": {"type": "object", "properties": {"assessment_id": {"type": "string", "description": "评估报告ID(必填)"}}, "required": ["assessment_id"]}}},
    {"type": "function", "function": {"name": "list_resource_investigations", "description": "列出企业的应急资源调查报告", "parameters": {"type": "object", "properties": {"enterprise_id": {"type": "string", "description": "企业ID"}}, "required": []}}},
    {"type": "function", "function": {"name": "get_resource_investigation", "description": "获取应急资源调查报告详情", "parameters": {"type": "object", "properties": {"investigation_id": {"type": "string", "description": "调查报告ID(必填)"}}, "required": ["investigation_id"]}}},
    {"type": "function", "function": {"name": "get_regulation_stats", "description": "获取法规库统计信息：法规总数、最近更新等", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "list_regulations", "description": "列出法规库中的法规条目，可按关键词搜索", "parameters": {"type": "object", "properties": {"keyword": {"type": "string", "description": "法规名称关键词"}}, "required": []}}},
    {"type": "function", "function": {"name": "search_regulations", "description": "通过知识图谱搜索匹配的法规内容", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词或问题(必填)"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "export_plan_docx", "description": "导出预案为Word文档(.docx)", "parameters": {"type": "object", "properties": {"plan_id": {"type": "string", "description": "预案ID(必填)"}}, "required": ["plan_id"]}}},
    {"type": "function", "function": {"name": "get_ai_config", "description": "查看当前AI配置信息（供应商、模型名称等）", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "generate_plan_content", "description": "为指定预案在后台逐章自动生成正文内容（AI生成），完成后用户可在预案编辑页查看各章节内容", "parameters": {"type": "object", "properties": {"plan_id": {"type": "string", "description": "预案ID(必填)"}}, "required": ["plan_id"]}}},
    {"type": "function", "function": {"name": "search_regulation_articles", "description": "语义检索法规条文原文。当用户询问安全生产、应急管理、消防、职业健康、特种设备、危化品等法律法规问题时，必须调用此工具查找相关法律条文的具体内容和出处。返回条文原文、所属法规全称、文号、条款号。注意：此工具返回的是具体条文，不是法规列表。", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "用户问题的关键词或完整句子，用于匹配法规条文"}, "top_k": {"type": "integer", "description": "返回条数，默认8，范围3-15"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "generate_report", "description": "生成图文并茂的分析报告（Markdown格式，含Mermaid图表）。支持主题：系统概览、企业分析、预案进度、风险分布等。", "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "报告主题，如系统概览、企业分析"}, "report_type": {"type": "string", "description": "报告类型: summary(概览)/analysis(分析)"}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "get_generation_progress",
     "description": "查询预案AI生成进度（聊天内触发的后台生成）。当用户询问生成进度或是否完成时调用",
     "parameters": {"type": "object", "properties": {"plan_id": {"type": "string", "description": "预案ID(必填)"}},
                    "required": ["plan_id"]}}},
    {"type": "function", "function": {"name": "query_enterprise_knowledge",
     "description": "基于企业画像（风险分级管控、评估报告、应急资源）语义问答。用户询问某企业风险状况、管控措施、资源配备时使用",
     "parameters": {"type": "object",
                    "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"},
                                   "question": {"type": "string", "description": "问题(必填)"}},
                    "required": ["enterprise_id", "question"]}}},
    {"type": "function", "function": {"name": "run_workflow",
     "description": "启动端到端工作流并在后台执行。可用模板：create_enterprise_plan（录入企业→创建预案→生成正文→导出Word）、regulatory_compliance（企业法规合规报告）。工作流在后台运行，用 get_workflow_progress 查询进度",
     "parameters": {"type": "object",
                    "properties": {"workflow_name": {"type": "string", "description": "工作流模板名（必填）"},
                                   "params": {"type": "object", "description": "工作流参数，如 {'name': '公司名称'} 或 {'enterprise_id': '企业ID'}"}},
                    "required": ["workflow_name"]}}},
    {"type": "function", "function": {"name": "get_workflow_progress",
     "description": "查询端到端工作流的运行进度与各步骤状态。用户询问「一键生成/工作流进度/到哪一步」时调用",
     "parameters": {"type": "object",
                    "properties": {"run_id": {"type": "string", "description": "工作流运行ID（必填）"}},
                    "required": ["run_id"]}}},
    {"type": "function", "function": {"name": "get_preferences",
     "description": "查看当前用户已保存的个性化偏好（生成风格、详细程度、报告主题、常用企业等），便于生成内容遵循用户习惯",
     "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "set_preferences",
     "description": "保存当前用户的个性化偏好，后续对话与内容生成自动遵循。键：style_preference(practical实用/formal规范正式)、detail_level(concise简洁/detailed详细)、report_topics(JSON数组)、common_enterprise_ids(JSON数组)、extra(其他要求文本)",
     "parameters": {"type": "object",
                    "properties": {"key": {"type": "string", "description": "偏好键（必填）"},
                                   "value": {"type": "string", "description": "偏好值（必填）；数组类键传 JSON 数组字符串"}},
                    "required": ["key", "value"]}}},
]

CHAT_SYSTEM_PROMPT = """你是数字化应急预案自动生成系统的AI助手。核心能力：查询创建修改删除企业和预案、智能添加企业（autofill_enterprise自动查工商数据校准全称）、查看风险分级管控和应急资源、查看评估报告和调查报告、搜索法规库、导出Word、生成图文报告。重要规则：用户要求任何分析报告、概览、总结时，必须调用 generate_report 工具（主题如系统概览、企业分析、法规库报告、风险分布等），禁止直接用函数返回的数据自行拼凑报告。用户说「添加XX公司」优先用autofill_enterprise。删除前先确认。回复简洁专业用中文。每次操作后汇报verified验证状态。

【法规引用规则 — 必须严格遵守】
当用户询问安全生产、应急管理、消防、职业健康、特种设备、危险化学品、事故调查、隐患排查、安全培训、应急预案编制等法律法规相关问题时，必须执行以下步骤：

1. 立即调用 search_regulation_articles 工具检索相关法规条文。query 参数应为用户问题的完整句子或关键词，不要自行提炼。

2. 回答必须基于工具返回的实际条文内容，不得编造法规名称或条款号。如果工具返回了条文，应在回答中体现条文要求。如果工具返回为空（articles=[]），明确告知用户："法规库中暂未找到与您问题直接相关的条文，以下建议基于一般性原则——"然后可以基于常识给出指导，但不要编造具体法规名称和条款号。

3. 回答末尾必须以「📋 引用法规」为标题，列出所引用的法规。每一条引用格式为：
   - 《法规全称》（文号）第X条
   示例：
   - 《中华人民共和国安全生产法》（2021修正）第二十一条
   - 《生产安全事故应急预案管理办法》（应急管理部令第2号）第八条

4. 引用列表只包含实际在回答中用到的法规，不要为了凑数列出无关法规。如果工具返回的条文中没有明确的"第X条"编号，则只写法规名称和文号，不写条款号。

5. 如果用户问的问题与法律法规无关（如系统操作、数据统计），不需要调用此工具，也不需要添加引用列表。"""


# ── 用户偏好 → system prompt ──

_PREF_SECTION_ORDER = (
    "style_preference", "detail_level", "report_topics",
    "common_enterprise_ids", "extra",
)
_PREF_CN_LABELS = {
    "style_preference": "生成风格",
    "detail_level": "详细程度",
    "report_topics": "报告主题偏好",
    "common_enterprise_ids": "常用企业（按ID）",
    "extra": "其他偏好要求",
}
_PREF_VALUE_CN = {
    "style_preference": {"practical": "实用为主", "formal": "规范正式"},
    "detail_level": {"concise": "简洁", "detailed": "详细"},
}


def build_system_prompt_with_prefs(prefs: dict | None) -> str:
    """在 CHAT_SYSTEM_PROMPT 末尾追加用户偏好段；无有效偏好时原样返回（保守）。

    偏好与基础提示合并为同一条 system 消息：长对话截断逻辑保留第一条 system，
    因此压缩后偏好提示仍然生效。
    """
    lines = []
    for key in _PREF_SECTION_ORDER:
        value = (prefs or {}).get(key)
        if value is None or value == "" or value == [] or value == {}:
            continue
        label = _PREF_CN_LABELS.get(key, key)
        if isinstance(value, list):
            rendered = "、".join(str(v) for v in value)
        elif isinstance(value, dict):
            rendered = str(value)
        else:
            cn = (_PREF_VALUE_CN.get(key) or {}).get(str(value))
            rendered = f"{value}（{cn}）" if cn else str(value)
        lines.append(f"- {label}：{rendered}")
    if not lines:
        return CHAT_SYSTEM_PROMPT
    section = "\n".join(lines)
    return f"{CHAT_SYSTEM_PROMPT}\n\n【用户偏好 — 请遵守】\n{section}"


async def _call_llm(messages: list, ai_config: AIConfig) -> dict:
    return await llm_chat_completion(messages, ai_config, stream=False, timeout=60, tools=CHAT_TOOLS)


async def _call_llm_stream(messages: list, ai_config: AIConfig):
    try:
        gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=180)
        async for chunk in gen:
            yield chunk
    except LLMError as e:
        # 保持原 chat.py 文案（无空格）
        raise Exception(f"AI调用失败: {e.status_code} {e.text[:300]}")


async def _collect_llm(messages: list, ai_config: AIConfig) -> str:
    """收集 LLM 完整响应（用于需要后处理的场景）"""
    return await llm_collect_all(messages, ai_config, timeout=180)


async def _generate_report_text(system_prompt: str, prompt: str, ai_config):
    """生成报告：system_prompt 非空时作为 system 消息传入。"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return await _collect_llm(messages, ai_config)


async def _render_mermaid_blocks(md_text: str) -> str:
    """提取 Markdown 中的 Mermaid 代码块，渲染为 SVG。"""
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    async def _replace(m):
        code = m.group(1).strip()
        try:
            svg = await render_mermaid_svg(code)
            return f'<div style="margin:16px 0;padding:12px;background:#fafafa;border:1px solid #e8e8e8;border-radius:6px;overflow-x:auto;text-align:center;">{svg}</div>'
        except Exception:
            return f'<pre style="background:#fff2f0;border:1px solid #ffccc7;padding:12px;border-radius:6px;"><code>{m.group(0)}</code></pre>'
    parts = []
    last_end = 0
    for m in pattern.finditer(md_text):
        parts.append(md_text[last_end:m.start()])
        parts.append(await _replace(m))
        last_end = m.end()
    parts.append(md_text[last_end:])
    return "".join(parts)


async def _md_to_html(md_text: str) -> str:
    """Markdown → HTML（含 Mermaid 渲染）"""
    html = await _render_mermaid_blocks(md_text)
    return md_to_html(html, output_format="html5")


# _sse → sse_line (移入 services/sse_utils.py)


async def _save_messages(user_id: str, conv_id: str, user_msg: str, assistant_msg: str,
                         tool_trace: list | None = None):
    """保存一轮对话消息到 DB（使用独立 session）。

    tool_trace: [{"round_no", "fn_name", "result"}]，按轮保存 assistant 占位 + tool 消息。
    """
    async with async_session() as db:
        # 更新会话时间
        conv = await db.get(ChatConversation, conv_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            # 首次对话自动设标题
            if conv.title == "新对话":
                conv.title = user_msg[:30] + ("..." if len(user_msg) > 30 else "")
        # 保存消息
        db.add(ChatMessage(conversation_id=conv_id, role="user", content=user_msg))
        db.add(ChatMessage(conversation_id=conv_id, role="assistant", content=assistant_msg))
        if tool_trace:
            db.add(ChatMessage(conversation_id=conv_id, role="assistant", content=""))
            for item in tool_trace:
                db.add(ChatMessage(
                    conversation_id=conv_id, role="tool",
                    name=item.get("fn_name", ""),
                    content=(item.get("result") or "")[:4000],
                ))
        await db.commit()


async def _record_tool_call(db, conv_id: str, round_no: int, fn_name: str, fn_args: dict,
                            result: str, status: str, duration_ms: int) -> None:
    """写入一条工具执行记录（进度持久化用）。"""
    from app.models.chat_tool_call import ChatToolCall
    db.add(ChatToolCall(
        conversation_id=conv_id, round_no=round_no, fn_name=fn_name,
        fn_args=fn_args or {}, result=(result or "")[:4000],
        status=status, duration_ms=duration_ms,
    ))
    await db.commit()


def _safe_tool_args(tc) -> dict:
    try:
        return json.loads(tc.get("function", {}).get("arguments", "{}"))
    except json.JSONDecodeError:
        return {}


async def _run_tool_isolated(fn_name: str, fn_args: dict, user_id: str) -> str:
    """独立 session 执行只读工具（AsyncSession 不支持并发共享）。"""
    from app.models.user import User
    async with async_session() as sdb:
        user = await sdb.get(User, user_id)
        return await dispatch(sdb, user, fn_name, fn_args)


async def _execute_pending_tools(pending_tool_calls, db, current_user, round_num, conv_id):
    """读工具并行（独立 session），写工具串行（共享请求 db）。返回按原顺序的 [(tc, result_str)]。"""
    reads, writes = [], []
    for tc in pending_tool_calls:
        fn_name = tc.get("function", {}).get("name", "")
        (reads if fn_name in READ_TOOL_NAMES else writes).append(tc)

    results: list = []
    if reads:
        outs = await asyncio.gather(*[
            _run_tool_isolated(tc["function"]["name"], _safe_tool_args(tc), current_user.id)
            for tc in reads
        ])
        results.extend(zip(reads, outs))
    for tc in writes:
        fn_name = tc["function"]["name"]
        result_str = await dispatch(db, current_user, fn_name, _safe_tool_args(tc))
        results.append((tc, result_str))

    by_id = {tc["id"]: (tc, out) for tc, out in results}
    return [by_id[tc["id"]] for tc in pending_tool_calls]


async def _load_history_rows(db, conv_id: str):
    """按时间顺序加载会话全部历史消息行 + 工具调用实参记录（B20）。"""
    from app.models.chat_tool_call import ChatToolCall
    rows = (await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.seq)
    )).scalars().all()
    tool_rows = (await db.execute(
        select(ChatToolCall)
        .where(ChatToolCall.conversation_id == conv_id)
        .order_by(ChatToolCall.created_at, ChatToolCall.id)
    )).scalars().all()
    return rows, tool_rows


def _rebuild_messages_from_rows(rows, user_message: str, tool_rows: list | None = None) -> list:
    """DB 历史 → OpenAI messages。assistant(content="") + 连续 tool 行还原为 tool_calls。

    tool_rows: 可选 ChatToolCall 记录（按执行顺序），用于补全 tool_call 的真实 arguments
    （B20：避免历史重建把参数退化为 "{}"，长对话续轮决策质量下降）。
    """
    msgs = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    args_queue = list(tool_rows or [])
    i, n = 0, len(rows)
    while i < n:
        r = rows[i]
        if r.role == "assistant" and not (r.content or ""):
            tool_msgs = []
            j = i + 1
            while j < n and rows[j].role == "tool":
                tool_msgs.append(rows[j])
                j += 1
            if tool_msgs:
                calls = []
                for idx, tr in enumerate(tool_msgs):
                    args_text = "{}"
                    match_idx = next(
                        (k for k, rec in enumerate(args_queue)
                         if getattr(rec, "fn_name", None) == (tr.name or "")),
                        None,
                    )
                    if match_idx is not None:
                        rec = args_queue.pop(match_idx)
                        args_text = json.dumps(rec.fn_args or {}, ensure_ascii=False)
                    calls.append({
                        "id": f"call_{idx}",
                        "type": "function",
                        "function": {"name": tr.name or "", "arguments": args_text},
                    })
                msgs.append({"role": "assistant", "content": None, "tool_calls": calls})
                for idx, tr in enumerate(tool_msgs):
                    msgs.append({"role": "tool", "tool_call_id": f"call_{idx}",
                                 "content": tr.content or ""})
                i = j
                continue
            i += 1
            continue  # 空 assistant 且无 tool 行 → 跳过占位
        role = r.role if r.role != "function" else "tool"
        msgs.append({"role": role, "content": r.content or ""})
        i += 1
    msgs.append({"role": "user", "content": user_message})
    return msgs


def _estimate_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        text = m.get("content") or ""
        total += len(text) // 2 + 4
    return total


def _repair_tool_call_boundaries(msgs: list) -> list:
    """B7：截断后修正 tool_calls 配对边界，避免 OpenAI 400。

    - 丢弃无对应 assistant 的孤儿 tool 消息（截断窗口以 tool 开头）
    - 丢弃 tool 响应已被切掉的悬空 assistant(tool_calls)
    - 完整 assistant(tool_calls)+tool 配对原样保留
    """
    out = []
    i, n = 0, len(msgs)
    while i < n:
        m = msgs[i]
        if m.get("role") == "tool":
            i += 1
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            pending = {tc.get("id") for tc in m["tool_calls"] if tc.get("id")}
            if not pending:
                out.append(m)
                i += 1
                continue
            j = i + 1
            seen = set()
            while j < n and msgs[j].get("role") == "tool":
                tid = msgs[j].get("tool_call_id")
                if tid not in pending or tid in seen:
                    break
                seen.add(tid)
                j += 1
            if pending - seen:
                # 有 tool 响应被切掉 → 整组丢弃
                i = j
                continue
            out.extend(msgs[i:j])
            i = j
            continue
        out.append(m)
        i += 1
    return out


def truncate_by_token_budget(messages: list, budget: int = CHAT_CONTEXT_BUDGET) -> list:
    """超预算时：保留系统提示 + 最近 30% 轮次，中间轮压缩为一条历史摘要。"""
    if _estimate_tokens(messages) <= budget:
        return messages
    system = messages[0] if messages and messages[0]["role"] == "system" else None
    rest = messages[1:] if system else messages
    keep_last = rest[-max(1, int(len(rest) * 0.3)):]
    middle = rest[:-max(1, int(len(rest) * 0.3))]
    parts = []
    for m in middle:
        text = (m.get("content") or "").strip()
        if text:
            parts.append(text[:300])
    summary = {"role": "system", "content": "【历史摘要】" + "；".join(parts[-10:])}
    result = ([system] if system else []) + [summary] + keep_last
    return _repair_tool_call_boundaries(result)


# ─── CRUD 端点 ───

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(current_user=Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(
        select(ChatConversation)
        .where(ChatConversation.user_id == current_user.id)
        .order_by(desc(ChatConversation.updated_at))
    )
    convs = result.scalars().all()
    return [ConversationResponse(id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at) for c in convs]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(current_user=Depends(get_current_user), db=Depends(get_db)):
    conv = ChatConversation(user_id=current_user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(id=conv.id, title=conv.title, created_at=conv.created_at, updated_at=conv.updated_at)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    conv = await db.get(ChatConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "对话不存在")
    await db.delete(conv)
    await db.commit()
    return {"ok": True}


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def list_messages(conv_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    conv = await db.get(ChatConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "对话不存在")
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.seq)
    )
    msgs = result.scalars().all()
    return [MessageResponse(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in msgs]


@router.get("/conversations/{conv_id}/tool-calls")
async def list_tool_calls(conv_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    from app.models.chat_tool_call import ChatToolCall
    conv = (await db.execute(
        select(ChatConversation).where(ChatConversation.id == conv_id)
    )).scalar_one_or_none()
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "对话不存在")
    rows = (await db.execute(
        select(ChatToolCall)
        .where(ChatToolCall.conversation_id == conv_id)
        .order_by(ChatToolCall.created_at, ChatToolCall.id)
    )).scalars().all()
    return [{
        "id": r.id, "round_no": r.round_no, "fn_name": r.fn_name,
        "status": r.status, "duration_ms": r.duration_ms, "created_at": r.created_at,
    } for r in rows]


# ─── 主聊天端点 ───

@router.post("")
async def chat(body: ChatRequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    from app.services.ai_config_service import get_system_ai_config
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    # 确保对话存在
    conv_id = body.conversation_id
    if not conv_id:
        conv = ChatConversation(user_id=current_user.id)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    rows, tool_rows = await _load_history_rows(db, conv_id)
    messages = _rebuild_messages_from_rows(rows, body.message, tool_rows)
    # 偏好注入：_rebuild 后、截断前替换第一条 system 消息（截断保留 system，
    # 保证长对话压缩后偏好段仍在）；无有效偏好时 build_* 原样返回基础提示。
    try:
        prefs = await get_preferences(db, current_user.id)
        # chat 注入读最新值：读后清理进程内缓存，保证偏好写入后下一轮对话立即生效
        invalidate_cache(current_user.id)
        messages[0]["content"] = build_system_prompt_with_prefs(prefs)
    except Exception:
        logger.exception("用户偏好加载失败，回退默认 system prompt")
    messages = truncate_by_token_budget(messages)

    # 第一轮 LLM 调用
    try:
        llm_resp = await _call_llm(messages, ai_config)
    except Exception as e:
        raise HTTPException(500, str(e))

    choice = llm_resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    first_tool_calls = msg.get("tool_calls", [])

    # 无工具调用 → 直接返回文本
    if not first_tool_calls:
        text_content = msg.get("content", "")
        async def text_gen():
            if text_content:
                yield sse_line({"type": "chunk", "content": text_content})
            yield sse_line({"type": "conv_id", "content": conv_id})
            yield sse_line({"type": "done"})
            # 保存消息
            asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, text_content))
        return StreamingResponse(text_gen(), media_type="text/event-stream")

    # 多轮工具调用循环（最多 MAX_ROUNDS 轮）
    async def agent_loop():
        current_msgs = list(messages)
        pending_tool_calls = first_tool_calls
        final_text = ""
        trace = []

        for round_num in range(1, MAX_ROUNDS + 1):
            results = []

            # B8：工具执行与结果解析整体兜底——json.loads / result_obj.get / tc["id"]
            # 等任一异常都不允许生成器崩溃，必须发出 error + conv_id + done 并保存已收集轨迹。
            try:
                tool_results = await _execute_pending_tools(
                    pending_tool_calls, db, current_user, round_num, conv_id)
                for tc, result_str in tool_results:
                    fn_name = tc.get("function", {}).get("name", "")
                    tc_id = tc.get("id", "")
                    fn_args = _safe_tool_args(tc)
                    result_obj = json.loads(result_str)
                    is_err = isinstance(result_obj, dict) and "error" in result_obj
                    yield sse_line({"type": "progress", "message": f"[第{round_num}轮] 正在执行: {fn_name}..."})
                    # 打点：并行路径下每条工具的精确时长未单独采集，暂记 0（计划允许简化）
                    try:
                        await _record_tool_call(db, conv_id, round_num, fn_name, fn_args,
                                                result_str, "error" if is_err else "success", 0)
                    except Exception:
                        logger.exception("记录工具调用失败（不影响主流程）")
                    yield sse_line({"type": "tool_step", "name": fn_name, "status": "error" if is_err else "success",
                                    "duration_ms": 0})
                    trace.append({"round_no": round_num, "fn_name": fn_name, "result": result_str})

                    # 报告生成特殊处理
                    if result_obj.get("type") == "report_prompt":
                        yield sse_line({"type": "progress", "message": result_obj.get("message", "正在生成报告...")})
                        try:
                            full_text = await _generate_report_text(
                                result_obj.get("system_prompt", ""), result_obj["prompt"], ai_config)
                            html = await _md_to_html(full_text)
                            final_text = full_text
                            yield sse_line({"type": "chunk", "content": html, "html": True})
                        except Exception as e:
                            final_text = str(e)
                            yield sse_line({"type": "error", "message": str(e)})
                        yield sse_line({"type": "conv_id", "content": conv_id})
                        yield sse_line({"type": "done"})
                        asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text, tool_trace=trace))
                        return

                    yield sse_line({"type": "function_result", "name": fn_name, "result": result_str})
                    results.append({"tc_id": tc_id, "name": fn_name, "result": result_str})
            except Exception as e:
                final_text = str(e)
                yield sse_line({"type": "error", "message": str(e)})
                yield sse_line({"type": "conv_id", "content": conv_id})
                yield sse_line({"type": "done"})
                asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text, tool_trace=trace))
                return

            # 构建上下文
            current_msgs.append({"role": "assistant", "content": None, "tool_calls": pending_tool_calls})
            for r in results:
                current_msgs.append({"role": "tool", "tool_call_id": r["tc_id"], "content": r["result"]})

            # 最终轮或中间轮
            if round_num == MAX_ROUNDS:
                current_msgs.append({"role": "user", "content": "这是最后一轮。请直接总结所有操作结果。每个操作必须说明成功与否（看verified字段）。不要调用更多函数。"})
            else:
                current_msgs.append({"role": "user", "content": "请检查上述操作结果（verified表示成功）。如需继续调用函数完成用户任务，请继续；如果任务已完成，请直接总结汇报。"})

            # 下一轮 LLM 调用
            try:
                next_resp = await _call_llm(current_msgs, ai_config)
            except Exception as e:
                final_text = str(e)
                yield sse_line({"type": "error", "message": str(e)})
                yield sse_line({"type": "conv_id", "content": conv_id})
                yield sse_line({"type": "done"})
                asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text, tool_trace=trace))
                return

            choice = next_resp.get("choices", [{}])[0]
            new_msg = choice.get("message", {})
            next_tool_calls = new_msg.get("tool_calls", [])

            if not next_tool_calls:
                # 任务完成，流式输出最终总结
                final_msgs = current_msgs + [{"role": "user", "content": "请直接用自然语言总结所有操作结果。每个操作说明是否成功（verified字段）。"}]
                try:
                    async for chunk in _call_llm_stream(final_msgs, ai_config):
                        final_text += chunk
                        yield sse_line({"type": "chunk", "content": chunk})
                except Exception as e:
                    final_text = str(e)
                    yield sse_line({"type": "error", "message": str(e)})
                yield sse_line({"type": "conv_id", "content": conv_id})
                yield sse_line({"type": "done"})
                asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text, tool_trace=trace))
                return

            pending_tool_calls = next_tool_calls

        # 超过最大轮数：部分成功汇报（不再报「请简化问题」）
        done_names = [t["fn_name"] for t in trace]
        remaining = [tc.get("function", {}).get("name", "") for tc in pending_tool_calls]
        final_msgs = current_msgs + [{"role": "user",
                                      "content": _build_final_summary_prompt(done_names, remaining)}]
        try:
            async for chunk in _call_llm_stream(final_msgs, ai_config):
                final_text += chunk
                yield sse_line({"type": "chunk", "content": chunk})
        except Exception as e:
            final_text = str(e)
            yield sse_line({"type": "error", "message": str(e)})
        yield sse_line({"type": "conv_id", "content": conv_id})
        yield sse_line({"type": "done"})
        asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text, tool_trace=trace))
        return

    return StreamingResponse(agent_loop(), media_type="text/event-stream")



