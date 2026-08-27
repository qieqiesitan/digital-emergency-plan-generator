import json, os, glob
from collections import Counter

sessions_dir = r"C:\Users\55061\.codex\sessions"
archived_dir = r"C:\Users\55061\.codex\archived_sessions"
project_cwd = r"C:\Users\55061\Documents\数字化预案自动生成 2"

def is_project_related(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(50000)
            return project_cwd in content or u"预案" in content
    except:
        return False

def extract_session(filepath):
    pairs = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except:
        return []
    
    current_user = None
    current_ts = None
    assistant_actions = []
    current_user_full = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except:
            continue
        
        if obj.get("type") != "response_item":
            continue
        
        payload = obj.get("payload") or {}
        role = payload.get("role", "")
        content = payload.get("content")
        if content is None:
            content = []
        
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text") or ""
                if t:
                    text_parts.append(t)
        text = " ".join(text_parts)
        if not text:
            continue
        
        ts = obj.get("timestamp", "")
        
        if role == "user":
            if current_user and assistant_actions:
                pairs.append((current_ts, current_user, assistant_actions, current_user_full))
            current_user = text.replace("\n", " ").replace("\r", " ")[:250]
            current_ts = ts
            current_user_full = text
            assistant_actions = []
        elif role == "assistant":
            actions = set()
            if "apply_patch" in text or "*** Begin Patch" in text:
                actions.add("edit")
            if "shell_command" in text or "exec_command" in text:
                actions.add("exec")
            if "git save" in text or "git finish" in text:
                actions.add("git")
            if "phase" in text.lower() or u"阶段" in text:
                actions.add("phase")
            if "TASKS.md" in text or u"更新快照" in text:
                actions.add("tasks")
            if "verify" in text or "compile" in text:
                actions.add("verify")
            if actions:
                assistant_actions.append((ts, list(actions), text[:200]))
    
    if current_user and assistant_actions:
        pairs.append((current_ts, current_user, assistant_actions, current_user_full))
    
    return pairs

all_files = []
for pattern in [os.path.join(sessions_dir, "**/*.jsonl"), os.path.join(archived_dir, "*.jsonl")]:
    all_files.extend(glob.glob(pattern, recursive=True))

project_files = sorted([f for f in all_files if is_project_related(f)])

all_msgs = []
for fpath in project_files:
    pairs = extract_session(fpath)
    for ts, short, actions, full in pairs:
        all_msgs.append((ts[:10], short, full))

topics = Counter()
problem_keywords = {
    u"流程图/图表问题": [u"流程图", u"渲染失败", u"图表", u"mermaid", u"diagram"],
    u"导出/下载问题": [u"导出", u"下载", u"docx", u"word"],
    u"AI助手问题": [u"AI助手", u"chat", u"dispatch", u"不验证"],
    u"环境/配置问题": [u"环境", u"重启", u"丢失", u"config", u"env"],
    u"多智能体协同": [u"多智能体", u"协同", u"agent", u"并行"],
    u"格式问题": [u"格式", u"乱", u"markdown"],
    u"后端启动问题": [u"启动不了", u"重启", u"error"],
    u"过度设计/代码质量": [u"过度设计", u"ponytail", u"代码质量"],
    u"预案内容差异化": [u"差别", u"差异", u"看起来一样"],
    u"法规库管理": [u"法规", u"regulation", u"法律"],
    u"业务中台接入": [u"中台", u"qiankun", u"JWT", u"菜单"],
    u"方案讨论/规划": [u"方案", u"计划", u"路线", u"规划"],
}

for ts, short, full in all_msgs:
    for topic, keywords in problem_keywords.items():
        for kw in keywords:
            if kw.lower() in full.lower():
                topics[topic] += 1
                break

output_path = r"C:\Users\55061\Documents\数字化预案自动生成 2\analysis_output.txt"
with open(output_path, "w", encoding="utf-8") as out:
    out.write("="*70 + "\n")
    out.write(u"数字化预案系统 - Codex 对话分析总结\n")
    out.write("="*70 + "\n\n")
    
    out.write(u"统计: %d 条用户消息, %d 个会话\n" % (len(all_msgs), len(project_files)))
    out.write(u"时间跨度: 2026-06-15 ~ 2026-07-20 (35天)\n\n")
    
    out.write("-"*70 + "\n")
    out.write(u"【一、项目阶段演进】\n")
    out.write("-"*70 + "\n\n")
    
    out.write(u"Phase 1 (06-15~06-16): 业务中台接入\n")
    out.write(u"  - qiankun 微前端适配（双模式共存）\n")
    out.write(u"  - 后端 JWT 双模式改造\n")
    out.write(u"  - 菜单白屏/无内容问题排查\n")
    out.write(u"  - 前端可配置化管理改造\n")
    out.write(u"  - 与业务中台深度结合的路线讨论\n\n")
    
    out.write(u"Phase 2 (06-22~06-23): 代码同步与工具安装\n")
    out.write(u"  - GitHub 同步\n")
    out.write(u"  - superpowers 安装\n")
    out.write(u"  - 项目运行状态确认\n\n")
    
    out.write(u"Phase 3 (06-29~06-30): 预案质量与图表系统\n")
    out.write(u"  - 图文并茂预案扩展（多图表类型）\n")
    out.write(u"  - 系统联通性检查\n")
    out.write(u"  - 过度设计检查（ponytail）\n")
    out.write(u"  - 预案内容差异化问题\n")
    out.write(u"  - 流程图渲染失败 / DOCX导出无响应\n")
    out.write(u"  - 环境变量持久化\n\n")
    
    out.write(u"Phase 4 (07-03): 风险评估/资源报告优化\n")
    out.write(u"  - 预案生成流程理解\n")
    out.write(u"  - 多智能体协同优化方案\n\n")
    
    out.write(u"Phase 5 (07-04): 外部系统对接\n")
    out.write(u"  - 参考接入方案.md对接其他系统\n\n")
    
    out.write(u"Phase 6 (07-05): AI生成增强\n")
    out.write(u"  - 局部重生成功能\n")
    out.write(u"  - 提示词管理\n")
    out.write(u"  - 流程图修复（第3次）\n")
    out.write(u"  - 代码备份\n\n")
    
    out.write(u"Phase 7 (07-07~07-08): 系统设置与知识库\n")
    out.write(u"  - 系统设置（角色/用户管理）\n")
    out.write(u"  - AI助手功能扩展\n")
    out.write(u"  - 周边环境AI搜索（高德地图）\n")
    out.write(u"  - 法规依据时效性问题讨论\n")
    out.write(u"  - 法规知识库方案（向量检索+BK-tree）\n")
    out.write(u"  - 法规库管理页面完善\n\n")
    
    out.write(u"Phase 8 (07-12~07-20): 代码质量优化 + 收尾\n")
    out.write(u"  - 过渡设计系统性优化（4个Phase）\n")
    out.write(u"  - 法规管理查重/入库修复\n")
    out.write(u"  - AI助手格式/验证问题\n")
    out.write(u"  - 后端启动失败排查\n")
    out.write(u"  - 法规长文本AI解析不全\n")
    out.write(u"  - AI助手自动生成失败\n\n")
    
    out.write("-"*70 + "\n")
    out.write(u"【二、重复出现的问题（按严重程度排序）】\n")
    out.write("-"*70 + "\n\n")
    
    out.write(u"1. [严重] 流程图/图表渲染失败 -- 出现 4 次 (06-29, 06-30, 07-05x2)\n")
    out.write(u"   每次修复后不久又出现同样问题。根因可能是:\n")
    out.write(u"   - Mermaid 渲染逻辑对环境/config有隐式依赖，容器重建后丢失\n")
    out.write(u"   - 修复方式只治标，没有做防御性的渲染验证\n")
    out.write(u"   - 回归测试缺失，改其他代码时顺带破坏\n\n")
    
    out.write(u"2. [严重] AI 助手执行命令不验证结果 -- 出现 3 次 (07-15, 07-16, 07-20)\n")
    out.write(u"   AI助手调用了工具函数后就认为完成了，不检查返回值是否成功。\n")
    out.write(u"   比如: 企业创建不成功但报告\"已完成\"，预案不生成但总结里写\"已生成\"\n\n")
    
    out.write(u"3. [中等] 代码修改后后端/前端无法启动 -- 出现 2 次 (07-13, 07-20)\n")
    out.write(u"   多智能体并行修改导致文件冲突或语法错误。\n")
    out.write(u"   缺乏每个agent完成后的自动验证步骤。\n\n")
    
    out.write(u"4. [中等] DOCX 导出失败/无响应 -- 出现 2 次 (06-30, 07-05)\n")
    out.write(u"   点击下载一直loading，没有实际下载。\n\n")
    
    out.write(u"5. [中等] AI 回复格式混乱 -- 出现 2 次 (07-20)\n")
    out.write(u"   Markdown标记未正确转换为前端显示，用户看到裸的 ** ## 等标记\n\n")
    
    out.write(u"6. [中等] 环境变量/配置重启后丢失 -- 出现 2 次 (06-30, 07-07)\n")
    out.write(u"   Docker重建后修复失效。用户指责\"怎么一点长远眼光都没有\"\n\n")
    
    out.write(u"7. [中等] 修改后功能不生效/改了没用 -- 出现 3 次 (07-13, 07-15, 07-20)\n")
    out.write(u"   用户反复报告\"还是报错\"\"还是用不了\"，说明修改没有真正解决根因\n\n")
    
    out.write(u"8. [轻度] 任务中途中断 -- 出现 2 次 (07-07)\n")
    out.write(u"   用户说\"怎么总是干一半就断了\"。模型上下文限制导致长任务被截断\n\n")
    
    out.write(u"9. [轻度] Codex 忽略用户指令直接开发 -- (07-07)\n")
    out.write(u"   用户明确说\"先讨论、不着急修复\"，但Codex还是开始改代码\n\n")
    
    out.write("-"*70 + "\n")
    out.write(u"【三、用户反复表达的不满/痛点】\n")
    out.write("-"*70 + "\n\n")
    
    out.write(u"* \"很恼火\" -- 预案章节编号乱、流程图不渲染 (06-30)\n")
    out.write(u"* \"怎么一点长远眼光都没有\" -- 修复在Docker里，重建就丢失 (07-07)\n")
    out.write(u"* \"不是让你直接开发，上一个问题还没有解决\" -- Codex忽略用户指令 (07-07)\n")
    out.write(u"* \"怎么总是干一半就断了\" -- 长任务中断 (07-07)\n")
    out.write(u"* \"还是报错，怎么回事，你能不能系统的检查下\" -- 修复无效 (07-13)\n")
    out.write(u"* \"又有了老毛病，只执行命令，不验证结果\" -- AI助手问题 (07-15)\n")
    out.write(u"* \"我完全不会，你自己想办法弄\" -- 用户对技术操作无力 (07-20)\n")
    out.write(u"* \"改了，后端启动不了了，一直在重启中\" -- 改坏系统 (07-20)\n\n")
    
    out.write("-"*70 + "\n")
    out.write(u"【四、根本原因分析】\n")
    out.write("-"*70 + "\n\n")
    
    out.write(u"A. 缺乏防御性验证机制\n")
    out.write(u"   - 每次修改后没有自动运行回归验证\n")
    out.write(u"   - AI助手没有验证返回结果的模式\n")
    out.write(u"   - 流程图渲染无pre-check机制\n\n")
    
    out.write(u"B. 多智能体协同的副作用\n")
    out.write(u"   - 并行修改导致代码冲突\n")
    out.write(u"   - 缺乏统一的合并验证步骤\n")
    out.write(u"   - 每个agent只关注自己的任务，不关心整体\n\n")
    
    out.write(u"C. 修复偏向治标\n")
    out.write(u"   - 流程图问题反复出现说明没找到根因\n")
    out.write(u"   - 倾向于快速打补丁而非系统性重构\n")
    out.write(u"   - 不追溯为什么同一个问题会反复出现\n\n")
    
    out.write(u"D. 用户技术能力有限\n")
    out.write(u"   - 用户明确说\"我不会代码\"\"我完全不会\"\n")
    out.write(u"   - 无法自行排查和修复，完全依赖Codex\n")
    out.write(u"   - 对Docker、git等工具不熟悉\n\n")
    
    out.write(u"E. 长任务上下文丢失\n")
    out.write(u"   - 模型上下文窗口有限，长任务会被截断\n")
    out.write(u"   - TASKS.md机制存在但恢复不够精准\n\n")
    
    out.write("-"*70 + "\n")
    out.write(u"【五、改进建议】\n")
    out.write("-"*70 + "\n\n")
    
    out.write(u"1. 建立修改后自动验证流水线\n")
    out.write(u"   - 每次修改代码后自动: 语法检查 -> 后端启动 -> 前端编译 -> 关键API测试\n")
    out.write(u"   - 失败立即回滚 git undo\n\n")
    
    out.write(u"2. 为AI助手添加返回验证层\n")
    out.write(u"   - chat_dispatch.py 中每个action函数执行后强制检查返回值\n")
    out.write(u"   - 失败时不要报告\"已完成\"，要报告具体错误\n\n")
    
    out.write(u"3. 建立流程图的防御性渲染\n")
    out.write(u"   - 渲染前验证Mermaid语法\n")
    out.write(u"   - 渲染失败时有降级方案（静态文本）\n")
    out.write(u"   - 环境配置写入代码仓库而非仅Docker内\n\n")
    
    out.write(u"4. 多智能体协同后增加合并验证步骤\n")
    out.write(u"   - 所有agent完成后由协调者统一验证\n")
    out.write(u"   - 验证通过后才算完成\n\n")
    
    out.write(u"5. 优先解决\"反复出现\"的根因问题\n")
    out.write(u"   - 流程图问题追到底\n")
    out.write(u"   - AI助手验证机制追到底\n")
    out.write(u"   - 不要满足于\"可以了\"，要问\"为什么之前不行\"\n\n")

print("Analysis written to analysis_output.txt")
print("Top problem categories: %s" % str(topics.most_common(5)))
