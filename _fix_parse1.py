fpath = r'C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# Step 1: Replace PARSE_PROMPT with PARSE_META_PROMPT (remove articles section)
old_start = 'PARSE_PROMPT = \"\"\"你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取结构化信息。'
old_end = '  "articles": [{"number": "第一条", "text": "..."}, {"number": "第二条", "text": "..."}]\\n}\"\"\"'

idx_start = content.index(old_start)
idx_end = content.index(old_end) + len(old_end)

new_meta = '''PARSE_META_PROMPT = \"\"\"你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取元数据。

输入文本（仅展示开头部分）：
{raw_text}

请仔细提取以下字段：

1. 法规编号：从文本开头或标题附近查找（如 GB/T 29639-2020、主席令第88号等）
2. 法规全称：文本开头或标题行的完整名称
3. 发布机关：发布日期前的发文机关全称
4. 发布日期
5. 施行日期
6. 替代关系：查找"替代"、"代替"、"废止"等关键词
7. 上位法依据：通常在"依据"、"根据"后列出
8. 适用主题标签：从 [风险评估、危险辨识、危险化学品、重大危险源、事故分类、应急管理、应急预案、应急预案编制、应急演练、应急响应、应急救援、应急救援物资、应急资源、应急资源调查、消防安全、灭火器、特殊作业、安全培训、安全评价、职业健康、特种设备、备案、演练、评估] 中选择1-5个
9. 法规类型：law（法律）、standard（标准）、policy（政策）

只返回纯JSON，不要任何解释文字：
{
  "code": "GB/T 29639-2020",
  "full_name": "生产经营单位生产安全事故应急预案编制导则",
  "issuing_body": "国家市场监督管理总局、国家标准化管理委员会",
  "issue_date": "2020年9月29日",
  "effective_date": "2021年4月1日",
  "replaces": ["GB/T 29639-2013"],
  "based_on": ["中华人民共和国安全生产法", "生产安全事故应急预案管理办法"],
  "node_type": "standard",
  "topics": ["应急预案编制", "应急管理", "应急演练"]
}\"\"\"

'''

content = content[:idx_start] + new_meta + content[idx_end:]

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Step 1 done: PARSE_PROMPT → PARSE_META_PROMPT')