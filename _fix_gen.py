import sys
fpath = r'C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\generation.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    prompt = f\"请撰写应急预案章节《{section_title}》的内容。\\n\\n\"
    if accident_type:
        prompt += f\"【事故类型：{accident_type}】请围绕{accident_type}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。\\n\\n\"

    prompt += f\"企业信息：\\n{json.dumps(enterprise_data, ensure_ascii=False, indent=2)}\\n\\n\"

    if num_hint:

        prompt += num_hint + \"\\n\"

    if custom_instruction:

        prompt += f\"额外要求：{custom_instruction}\\n\\n\"

    mermaid_inst = _get_mermaid_instruction(section_key, section_title)

    if mermaid_inst:

        prompt += mermaid_inst + \"\\n\"

    prompt += \"请直接输出章节正文内容，不要重复章节标题作为正文第一行。\"

    reg_ctx = RegulationContextBuilder().get_chapter_context(
        section_key=section_key,
        section_title=section_title,
        plan_type=plan_type,
        enterprise_data=enterprise_data,
    )
    if reg_ctx:
        prompt += \"\\n\\n\" + REGULATION_WRITING_RULE + \"\\n\\n\" + reg_ctx

    return prompt'''

new = '''    prompt = f\"请撰写应急预案章节《{section_title}》的内容。\\n\\n\"
    if accident_type:
        prompt += f\"【事故类型：{accident_type}】请围绕{accident_type}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。\\n\\n\"

    prompt += f\"企业信息：\\n{json.dumps(enterprise_data, ensure_ascii=False, indent=2)}\\n\\n\"

    if num_hint:

        prompt += num_hint + \"\\n\"

    if custom_instruction:

        prompt += f\"额外要求：{custom_instruction}\\n\\n\"

    mermaid_inst = _get_mermaid_instruction(section_key, section_title)

    if mermaid_inst:

        prompt += mermaid_inst + \"\\n\"

    prompt += \"请直接输出章节正文内容，不要重复章节标题作为正文第一行。\"

    reg_ctx = RegulationContextBuilder().get_chapter_context(
        section_key=section_key,
        section_title=section_title,
        plan_type=plan_type,
        enterprise_data=enterprise_data,
    )
    if reg_ctx:
        prompt += \"\\n\\n\" + REGULATION_WRITING_RULE + \"\\n\\n\" + reg_ctx

    return prompt

def _collect_enterprise_data(enterprise, risk_sources, resources):
    '''Collect enterprise data dict from ORM models.''''

# Simple approach: find "return prompt" that ends the template path
# and remove the early return so it falls through to regulation injection
content = content.replace(
    '''            if mermaid_inst:
                prompt += \"\\n\\n\" + mermaid_inst
            return prompt

    # 兜底：代码拼接''',
    '''            if mermaid_inst:
                prompt += \"\\n\\n\" + mermaid_inst

    # 兜底：代码拼接''',
    1
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed early return in DB template path")