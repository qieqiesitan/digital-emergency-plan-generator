import os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)

with open("scripts/_original_chat.py", "r", encoding="utf-8-sig") as f:
    content = f.read()

# 1. Add tool definition
old_tool = "{\"type\": \"function\", \"function\": {\"name\": \"generate_report\", \"description\": \""
new_tool = "{\"type\": \"function\", \"function\": {\"name\": \"search_regulation_articles\", \"description\": \"语义检索法规条文原文。当用户询问安全生产、应急管理、消防、职业健康、特种设备、危化品等法律法规问题时，必须调用此工具查找相关法律条文的具体内容和出处。返回条文原文、所属法规全称、文号、条款号。注意：此工具返回的是具体条文，不是法规列表。\", \"parameters\": {\"type\": \"object\", \"properties\": {\"query\": {\"type\": \"string\", \"description\": \"用户问题的关键词或完整句子，用于匹配法规条文\"}, \"top_k\": {\"type\": \"integer\", \"description\": \"返回条数，默认8，范围3-15\"}}, \"required\": [\"query\"]}}},\n    {\"type\": \"function\", \"function\": {\"name\": \"generate_report\", \"description\": \""
content = content.replace(old_tool, new_tool)
print("Tool replaced:", old_tool not in content)

# 2. Extend prompt
old_end = "验证状态。\""
rules = "验证状态。\n\n【法规引用规则 — 必须严格遵守】\n当用户询问安全生产、应急管理、消防、职业健康、特种设备、危险化学品、事故调查、隐患排查、安全培训、应急预案编制等法律法规相关问题时，必须执行以下步骤：\n\n1. 立即调用 search_regulation_articles 工具检索相关法规条文。query 参数应为用户问题的完整句子或关键词，不要自行提炼。\n\n2. 回答必须基于工具返回的实际条文内容，不得编造法规名称或条款号。如果工具返回了条文，应在回答中体现条文要求。如果工具返回为空（articles=[]），明确告知用户：\"法规库中暂未找到与您问题直接相关的条文，以下建议基于一般性原则——\"然后可以基于常识给出指导，但不要编造具体法规名称和条款号。\n\n3. 回答末尾必须以「📋 引用法规」为标题，列出所引用的法规。每一条引用格式为：\n   - 《法规全称》（文号）第X条\n   示例：\n   - 《中华人民共和国安全生产法》（2021修正）第二十一条\n   - 《生产安全事故应急预案管理办法》（应急管理部令第2号）第八条\n\n4. 引用列表只包含实际在回答中用到的法规，不要为了凑数列出无关法规。如果工具返回的条文中没有明确的\"第X条\"编号，则只写法规名称和文号，不写条款号。\n\n5. 如果用户问的问题与法律法规无关（如系统操作、数据统计），不需要调用此工具，也不需要添加引用列表。\""
content = content.replace(old_end, rules)
print("Prompt replaced:", old_end not in content)

out_path = os.path.join(root, "app", "routers", "chat.py")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done! File written to:", out_path)