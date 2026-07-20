import re

fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\generation.py"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

# Strategy: find _build_section_prompt function body and restructure it

old_start = '''def _build_section_prompt(section_title: str, enterprise_data: dict, custom_instruction: str | None = None, section_number: int | None = None, section_key: str | None = None, plan_type: str = "*", accident_type: str | None = None) -> str:
    """构建章节提示词，优先使用数据库模板，未命中则用代码拼接兜底。"""
    # 尝试从数据库获取模板
    if plan_type != "*" and section_key:
        tmpl = get_section_prompt(plan_type, section_key)
        if tmpl and tmpl.get("user_prompt_template"):
            variables = {"enterprise_data": json.dumps(enterprise_data, ensure_ascii=False, indent=2), "accident_type": accident_type or ""}
            prompt = render_template(tmpl["user_prompt_template"], variables)
            if tmpl.get("system_prompt"):
                prompt = tmpl["system_prompt"] + "\\n\\n---\\n\\n" + prompt
            mermaid_inst = _get_mermaid_instruction(section_key, section_title)
            if mermaid_inst:
                prompt += "\\n\\n" + mermaid_inst
            return prompt

    # 兜底：代码拼接
    num_hint = f"这是应急预案的第{section_number}个章节，请在正文中使用\\u201c{section_number}.\\u201d或\\u201c{section_number}.x\\u201d的编号格式。\\n" if section_number is not None else ""

    prompt = f"请撰写应急预案章节《{section_title}》的内容。\\n\\n"
    if accident_type:
        prompt += f"【事故类型：{accident_type}】请围绕{accident_type}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。\\n\\n"

    prompt += f"企业信息：\\n{json.dumps(enterprise_data, ensure_ascii=False, indent=2)}\\n\\n"

    if num_hint:

        prompt += num_hint + "\\n"

    if custom_instruction:

        prompt += f"额外要求：{custom_instruction}\\n\\n"

    mermaid_inst = _get_mermaid_instruction(section_key, section_title)

    if mermaid_inst:

        prompt += mermaid_inst + "\\n"

    prompt += "请直接输出章节正文内容，不要重复章节标题作为正文第一行。"

    reg_ctx = RegulationContextBuilder().get_chapter_context(
        section_key=section_key,
        section_title=section_title,
        plan_type=plan_type,
        enterprise_data=enterprise_data,
    )
    if reg_ctx:
        prompt += "\\n\\n" + REGULATION_WRITING_RULE + "\\n\\n" + reg_ctx

    return prompt'''

assert old_start in content, "Could not find the function!"

new_start = '''def _build_section_prompt(section_title: str, enterprise_data: dict, custom_instruction: str | None = None, section_number: int | None = None, section_key: str | None = None, plan_type: str = "*", accident_type: str | None = None) -> str:
    """构建章节提示词，优先使用数据库模板，未命中则用代码拼接兜底。尾部统一追加法规上下文。"""
    prompt_base = None

    # 策略A：从数据库获取模板
    if plan_type != "*" and section_key:
        tmpl = get_section_prompt(plan_type, section_key)
        if tmpl and tmpl.get("user_prompt_template"):
            variables = {"enterprise_data": json.dumps(enterprise_data, ensure_ascii=False, indent=2), "accident_type": accident_type or ""}
            prompt_base = render_template(tmpl["user_prompt_template"], variables)
            if tmpl.get("system_prompt"):
                prompt_base = tmpl["system_prompt"] + "\\n\\n---\\n\\n" + prompt_base
            mermaid_inst = _get_mermaid_instruction(section_key, section_title)
            if mermaid_inst:
                prompt_base += "\\n\\n" + mermaid_inst

    # 策略B：代码兜底（策略A未命中时）
    if prompt_base is None:
        num_hint = f"这是应急预案的第{section_number}个章节，请在正文中使用\\u201c{section_number}.\\u201d或\\u201c{section_number}.x\\u201d的编号格式。\\n" if section_number is not None else ""

        prompt_base = f"请撰写应急预案章节《{section_title}》的内容。\\n\\n"
        if accident_type:
            prompt_base += f"【事故类型：{accident_type}】请围绕{accident_type}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。\\n\\n"

        prompt_base += f"企业信息：\\n{json.dumps(enterprise_data, ensure_ascii=False, indent=2)}\\n\\n"

        if num_hint:
            prompt_base += num_hint + "\\n"

        if custom_instruction:
            prompt_base += f"额外要求：{custom_instruction}\\n\\n"

        mermaid_inst = _get_mermaid_instruction(section_key, section_title)
        if mermaid_inst:
            prompt_base += mermaid_inst + "\\n"

        prompt_base += "请直接输出章节正文内容，不要重复章节标题作为正文第一行。"

    # 策略A/B 统一尾部追加法规上下文
    reg_ctx = RegulationContextBuilder().get_chapter_context(
        section_key=section_key,
        section_title=section_title,
        plan_type=plan_type,
        enterprise_data=enterprise_data,
    )
    if reg_ctx:
        prompt_base += "\\n\\n" + REGULATION_WRITING_RULE + "\\n\\n" + reg_ctx

    return prompt_base'''

content = content.replace(old_start, new_start, 1)
print("Fix applied: _build_section_prompt restructured")

with open(fpath, "w", encoding="utf-8") as f:
    f.write(content)
print("File written")
