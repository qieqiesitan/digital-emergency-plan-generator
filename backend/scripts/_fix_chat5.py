import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with open("backend/scripts/_original_chat.py", "r", encoding="utf-8-sig") as f:
    content = f.read()

# 1. Add tool definition
old_tool = '{"type": "function", "function": {"name": "generate_report", "description": "'
new_tool_def = '{"type": "function", "function": {"name": "search_regulation_articles", "description": "'
new_tool_def += chr(35821)+chr(20041)+chr(26816)+chr(32034)+chr(27861)+chr(35268)+chr(26465)+chr(25991)+chr(21407)+chr(25991)+chr(12290)+chr(24403)+chr(29992)+chr(25143)+chr(35810)+chr(38382)+chr(23433)+chr(20840)+chr(29983)+chr(20135)+chr(12289)+chr(24212)+chr(24613)+chr(31649)+chr(29702)+chr(12289)+chr(28040)+chr(38450)+chr(12289)+chr(32844)+chr(19994)+chr(20581)+chr(24247)+chr(12289)+chr(29305)+chr(31181)+chr(35774)+chr(22791)+chr(12289)+chr(21361)+chr(21270)+chr(21697)+chr(31561)+chr(27861)+chr(24459)+chr(27861)+chr(35268)+chr(38382)+chr(39064)+chr(26102)+chr(65292)+chr(24517)+chr(39035)+chr(35843)+chr(29992)+chr(27492)+chr(24037)+chr(20855)+chr(26597)+chr(25214)+chr(30456)+chr(20851)+chr(27861)+chr(24459)+chr(26465)+chr(25991)+chr(30340)+chr(20855)+chr(20307)+chr(20869)+chr(23481)+chr(21644)+chr(20986)+chr(22788)+chr(12290)+chr(36820)+chr(22238)+chr(26465)+chr(25991)+chr(21407)+chr(25991)+chr(12289)+chr(25152)+chr(23646)+chr(27861)+chr(35268)+chr(20840)+chr(31216)+chr(12289)+chr(25991)+chr(21495)+chr(12289)+chr(26465)+chr(27454)+chr(21495)+chr(12290)+chr(27880)+chr(24847)+chr(65306)+chr(27492)+chr(24037)+chr(20855)+chr(36820)+chr(22238)+chr(30340)+chr(26159)+chr(20855)+chr(20307)+chr(26465)+chr(25991)+chr(65292)+chr(19981)+chr(26159)+chr(27861)+chr(35268)+chr(21015)+chr(34920)+chr(12290)
new_tool_def += '", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "'
new_tool_def += chr(29992)+chr(25143)+chr(38382)+chr(39064)+chr(30340)+chr(20851)+chr(38190)+chr(35789)+chr(25110)+chr(23436)+chr(25972)+chr(21477)+chr(23376)+chr(65292)+chr(29992)+chr(20110)+chr(21305)+chr(37197)+chr(27861)+chr(35268)+chr(26465)+chr(25991)
new_tool_def += '"}, "top_k": {"type": "integer", "description": "'
new_tool_def += chr(36820)+chr(22238)+chr(26465)+chr(25968)+chr(65292)+chr(40664)+chr(35748)+chr(56)+chr(65292)+chr(33539)+chr(22260)+chr(51)+chr(45)+chr(49)+chr(53)
new_tool_def += '"}}, "required": ["query"]}}},\n    {"type": "function", "function": {"name": "generate_report", "description": "'
content = content.replace(old_tool, new_tool_def)

# 2. Extend prompt
old_end = chr(39564)+chr(35777)+chr(29366)+chr(24577)+chr(12290)+chr(34)
rules = chr(39564)+chr(35777)+chr(29366)+chr(24577)+chr(12290)
rules += '\n\n【法规引用规则 — 必须严格遵守】\n'
rules += '当用户询问安全生产、应急管理、消防、职业健康、特种设备、危险化学品、事故调查、隐患排查、安全培训、应急预案编制等法律法规相关问题时，必须执行以下步骤：\n\n'
rules += '1. 立即调用 search_regulation_articles 工具检索相关法规条文。query 参数应为用户问题的完整句子或关键词，不要自行提炼。\n\n'
rules += '2. 回答必须基于工具返回的实际条文内容，不得编造法规名称或条款号。如果工具返回了条文，应在回答中体现条文要求。如果工具返回为空（articles=[]），明确告知用户："法规库中暂未找到与您问题直接相关的条文，以下建议基于一般性原则——"然后可以基于常识给出指导，但不要编造具体法规名称和条款号。\n\n'
rules += '3. 回答末尾必须以「\U0001f4cb 引用法规」为标题，列出所引用的法规。每一条引用格式为：\n'
rules += '   - 《法规全称》（文号）第X条\n'
rules += '   示例：\n'
rules += '   - 《中华人民共和国安全生产法》（2021修正）第二十一条\n'
rules += '   - 《生产安全事故应急预案管理办法》（应急管理部令第2号）第八条\n\n'
rules += '4. 引用列表只包含实际在回答中用到的法规，不要为了凑数列出无关法规。如果工具返回的条文中没有明确的"第X条"编号，则只写法规名称和文号，不写条款号。\n\n'
rules += '5. 如果用户问的问题与法律法规无关（如系统操作、数据统计），不需要调用此工具，也不需要添加引用列表。"'

content = content.replace(old_end, rules)

out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "app", "routers", "chat.py")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(content)
print("chat.py updated successfully")