"""Chat AI 助手 — SSE 流式端点 + 对话持久化。"""

import json, logging, re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from app.database import get_db, async_session
from app.models.enterprise import AIConfig
from app.models.chat import ChatConversation, ChatMessage
from app.dependencies import get_current_user
from app.services.llm_client import decrypt_api_key
from app.services.markdown_utils import md_to_html
from app.services.mermaid_renderer import render_mermaid_svg
from app.schemas.chat import ChatRequest, ConversationResponse, MessageResponse
from app.services.chat_dispatch import dispatch
from datetime import datetime, timezone
from app.services.sse_utils import sse_line
import asyncio
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

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


def _build_tool_messages(history: list, user_message: str) -> list:
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for h in history:
        role = h.role if h.role != "function" else "tool"
        msg = {"role": role, "content": h.content or ""}
        if h.name and h.role == "function":
            msg["tool_call_id"] = h.name
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})
    return messages


async def _call_llm(messages: list, ai_config: AIConfig) -> dict:
    api_key = decrypt_api_key(ai_config.api_key_encrypted)
    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")
    payload = {"model": ai_config.model_name, "messages": messages, "tools": CHAT_TOOLS, "temperature": ai_config.temperature, "max_tokens": ai_config.max_tokens, "top_p": ai_config.top_p, "stream": False}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{base}/chat/completions", json=payload, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code != 200:
            raise Exception(f"AI调用失败: {resp.status_code} {resp.text[:300]}")
        return resp.json()


async def _call_llm_stream(messages: list, ai_config: AIConfig):
    api_key = decrypt_api_key(ai_config.api_key_encrypted)
    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")
    payload = {"model": ai_config.model_name, "messages": messages, "temperature": ai_config.temperature, "max_tokens": ai_config.max_tokens, "top_p": ai_config.top_p, "stream": True}
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", f"{base}/chat/completions", json=payload, headers={"Authorization": f"Bearer {api_key}"}) as resp:
            if resp.status_code != 200:
                err = await resp.aread()
                raise Exception(f"AI调用失败: {resp.status_code} {err[:300]}")
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass


async def _collect_llm(messages: list, ai_config: AIConfig) -> str:
    """收集 LLM 完整响应（用于需要后处理的场景）"""
    api_key = decrypt_api_key(ai_config.api_key_encrypted)
    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")
    payload = {"model": ai_config.model_name, "messages": messages, "temperature": ai_config.temperature, "max_tokens": ai_config.max_tokens, "top_p": ai_config.top_p, "stream": False}
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{base}/chat/completions", json=payload, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code != 200:
            raise Exception(f"AI调用失败: {resp.status_code} {resp.text[:300]}")
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


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


async def _save_messages(user_id: str, conv_id: str, user_msg: str, assistant_msg: str):
    """保存一轮对话消息到 DB（使用独立 session）"""
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
        await db.commit()


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
        .order_by(ChatMessage.created_at)
    )
    msgs = result.scalars().all()
    return [MessageResponse(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in msgs]


# ─── 主聊天端点 ───

@router.post("")
async def chat(body: ChatRequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == current_user.id))).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "请先在系统设置中配置AI模型")

    # 确保对话存在
    conv_id = body.conversation_id
    if not conv_id:
        conv = ChatConversation(user_id=current_user.id)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    messages = _build_tool_messages(body.history, body.message)

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

    # 多轮工具调用循环（最多5轮）
    async def agent_loop():
        current_msgs = list(messages)
        pending_tool_calls = first_tool_calls
        MAX_ROUNDS = 5
        final_text = ""

        for round_num in range(1, MAX_ROUNDS + 1):
            results = []

            for tc in pending_tool_calls:
                func = tc.get("function", {})
                fn_name = func.get("name", "")
                tc_id = tc.get("id", "")
                try:
                    fn_args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    fn_args = {}
                yield sse_line({"type": "progress", "message": f"[第{round_num}轮] 正在执行: {fn_name}..."})
                result_str = await dispatch(db, current_user, fn_name, fn_args)
                result_obj = json.loads(result_str)

                # 报告生成特殊处理
                if result_obj.get("type") == "report_prompt":
                    yield sse_line({"type": "progress", "message": result_obj.get("message", "正在生成报告...")})
                    try:
                        full_text = await _collect_llm([{"role": "user", "content": result_obj["prompt"]}], ai_config)
                        html = await _md_to_html(full_text)
                        final_text = full_text
                        yield sse_line({"type": "chunk", "content": html, "html": True})
                    except Exception as e:
                        final_text = str(e)
                        yield sse_line({"type": "error", "message": str(e)})
                    yield sse_line({"type": "conv_id", "content": conv_id})
                    yield sse_line({"type": "done"})
                    asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text))
                    return

                yield sse_line({"type": "function_result", "name": fn_name, "result": result_str})
                results.append({"tc_id": tc_id, "name": fn_name, "result": result_str})

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
                asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text))
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
                asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, final_text))
                return

            pending_tool_calls = next_tool_calls

        # 超过最大轮数
        yield sse_line({"type": "error", "message": "操作轮数超过上限，请简化您的问题重试"})
        yield sse_line({"type": "conv_id", "content": conv_id})
        yield sse_line({"type": "done"})
        asyncio.ensure_future(_save_messages(current_user.id, conv_id, body.message, "操作轮数超过上限"))

    return StreamingResponse(agent_loop(), media_type="text/event-stream")
