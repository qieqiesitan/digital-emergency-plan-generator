import sys, json, os, asyncio, httpx, textwrap, time
import unicodedata

# ─── Configuration ───
# Edit these or pass via env vars / command line
API_KEY = os.environ.get("DEEPSEEK_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE", "https://api.deepseek.com/v1")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
TEMPERATURE = 0.3
MAX_TOKENS = 4096
TOP_P = 0.95

# ─── Enterprise test data ───
ENTERPRISE_DATA = {
    "name": "西安宝岳空间科技有限公司",
    "address": "西安市高新区科技路48号创业广场B座15层",
    "industry": "信息技术服务业",
    "business_scope": "空间信息数据处理、地理信息系统开发、测绘服务",
    "employee_count": 85,
    "building_overview": "位于创业广场B座15层整层，面积约1200平方米，设有办公区、数据中心机房、会议室、档案室",
    "org_structure": "总经理→副总经理（技术/行政）→各部门（测绘部、GIS开发部、数据部、综合管理部、财务部）",
    "legal_representative": "张三",
    "credit_code": "91610131MA6XXXXXXX",
    "phone": "029-88888888",
    "safety_officer": "李四",
    "emergency_resources": [
        {"category": "消防器材", "name": "干粉灭火器", "specification": "4kg", "quantity": 12, "unit": "具", "location": "各办公区走廊"},
        {"category": "消防器材", "name": "CO2灭火器", "specification": "3kg", "quantity": 4, "unit": "具", "location": "数据中心机房"},
        {"category": "急救物资", "name": "急救箱", "specification": "标准型", "quantity": 3, "unit": "个", "location": "前台、综合管理部"},
        {"category": "应急照明", "name": "应急照明灯", "specification": "双头LED", "quantity": 8, "unit": "个", "location": "疏散通道、安全出口"},
    ],
    "risk_sources": [
        {"categories": "火灾", "name": "电气火灾", "location": "数据中心机房", "description": "服务器机柜密集，电气线路复杂，长时间运行存在过热短路风险", "risk_level": "较大", "control_measures": "定期巡检线路、配备温感报警器、气体灭火系统"},
        {"categories": "触电", "name": "办公用电", "location": "办公区", "description": "大量办公电子设备用电", "risk_level": "一般", "control_measures": "漏电保护器、定期检测接地"},
        {"categories": "高处坠落", "name": "外业测绘作业", "location": "野外作业现场", "description": "外业测绘人员可能涉及登高作业", "risk_level": "一般", "control_measures": "安全带、安全培训、作业审批"},
    ],
}

# ─── Old System Prompt ───
OLD_SYSTEM_PROMPT = textwrap.dedent("""\
你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。请根据提供的企业信息，撰写专业、合规的应急预案内容。

【Markdown格式要求——必须严格遵守】
- 使用 ### 标题表示子节（如 ### 9.1 通信与信息保障），使用 #### 表示孙节（如 #### 9.1.1 内部通信）
- 不同段落、不同子节之间必须用空行分隔（即两个换行符）
- 表格必须使用 | --- | 格式，且表格前后必须有空行
- 列表项使用 - 开头，列表前后也要有空行
- 正文中的章节编号必须与提示中指定的编号一致，不要自行编号
""")

# ─── New System Prompt (增强版) ───
NEW_SYSTEM_PROMPT = textwrap.dedent("""\
你是一位持有国家注册安全工程师资格的应急预案编制专家，具有丰富的生产经营单位应急预案编制经验。你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，并严格遵循以下法律法规：《中华人民共和国安全生产法》《中华人民共和国突发事件应对法》《生产安全事故应急预案管理办法》《生产安全事故应急条例》。

【写作风格——必须严格遵守】

一、公文语体要求
1. 使用正式的政府公文语体，语言严谨、客观、准确、简洁。
2. 高频动词使用：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查、接受、传达、发布、落实、保障。
3. 避免口语化表达、修辞性语言、主观评论。不使用"应该""大概""也许"等不确定词汇。
4. 句式以短句为主，主语明确，逻辑清晰。

二、结构范式
每个章节严格遵循 GB/T 29639-2020 的结构要求：
- 综合应急预案章节顺序：总则（适用范围、响应分级）→ 应急组织机构及职责 → 应急响应（信息报告、预警、响应启动、应急处置、应急支援、响应终止）→ 后期处置 → 应急保障
- 专项应急预案章节顺序：适用范围 → 应急组织机构及职责 → 响应启动 → 应急会议 → 信息上报 → 资源协调 → 信息公开 → 后勤保障 → 应急处置 → 应急结束 → 后期处置 → 应急保障
- 现场处置方案章节顺序：事故风险分析（事故特征、发生区域、事故前征兆）→ 应急工作职责 → 应急处置（处置程序、处置措施）→ 注意事项

三、术语标准
1. 应急组织统一用："应急救援指挥部""总指挥""副总指挥""应急救援小组"。
2. 响应级别统一表述：
   Ⅲ级响应：部门或作业现场的应急力量能够自行处置的事故。
   Ⅱ级响应：超出部门或作业现场的应急处置能力，且本单位内部应急力量能够自行处置的事故。
   Ⅰ级响应：本单位应急救援能力无法处置或无法控制，需要请求外部力量协助处置的事故。
3. 信息报告内容必须包含七个要素：事故发生的时间地点和现场情况、事故简要经过、已造成或可能造成的伤亡人数、直接经济损失初步估计、事故原因初步分析、已采取的措施和效果、其他应当报告的情况。

四、具体化要求
1. 充分利用企业信息中提供的人员姓名、联系电话、地址等数据，将其填入预案正文中，不要使用占位符（如"XXX""某公司"）。
2. 应急物资、风险源、周边环境等数据要和预案正文有机结合，不要仅罗列数据。
3. 每个职责描述必须有可操作性，避免空洞表述。

五、写作范式参考
以下是真实应急预案的标准写法示例：

示例1——应急组织机构职责描述：
"抢险救援组：熟悉各种灭火器材、安全设施、救护器材的用途、操作方法、存放地点及使用范围。在事故发生后，负责第一时间按预定方案进行消防控制、协助涉险人员脱险等处理。负责事故现场切断电源等。当发生事故时，全组人员必须迅速赶到事故应急集合点，根据指挥部的命令，迅速开展火灾扑救、物资抢救工作。"

示例2——信息上报时限：
"应急救援指挥部总指挥在收到事故信息核实后，根据事故严重程度，决定是否向XX区应急管理局和负有安全生产监督管理职责的部门报告。需要向上级报告的事故信息，如达到Ⅰ级响应条件时，应由应急救援指挥部总指挥在1小时内向XX区应急管理局报告。火灾事故除报有关部门外，应同时报消防部门。"

示例3——响应终止条件：
"当满足以下条件时，响应终止：（1）生产安全事故现场得到有效控制，没有导致次生、衍生的事故隐患。（2）没有被困人员，事故现场人员已疏散到安全地带。（3）受伤人员已全部从事故现场救出，并送到医院进行救治，没有失踪人员。"

六、Markdown格式要求
- 使用 ### 标题表示子节（如 ### 9.1 通信与信息保障），使用 #### 表示孙节
- 不同段落、不同子节之间必须用空行分隔
- 表格使用 | --- | 格式，表格前后必须有空行
- 列表项使用 - 或数字编号，列表前后要有空行
- 章节编号必须与提示中指定的编号一致，不要自行编号
""")

# ─── Test sections ───
TEST_SECTIONS = [
    {
        "section_key": "sec_org",
        "title": "应急组织机构及职责",
        "number": 2,
        "extra": "请根据企业信息中的组织架构，合理设置应急救援指挥部和至少4个应急救援小组，为每个角色分配具体、可操作的职责。",
    },
    {
        "section_key": "sec_report",
        "title": "信息报告",
        "number": 3,
        "extra": "请详细描述信息接收与通报程序、信息上报时限和内容、信息传递方式。",
    },
]

# ─── Build section prompt ───
def build_section_prompt(title, ent_data, extra, section_number):
    return textwrap.dedent(f"""\
请撰写应急预案章节《{title}》的内容。

企业信息：
{json.dumps(ent_data, ensure_ascii=False, indent=2)}

这是应急预案的第{section_number}个章节，请在正文中使用"{section_number}."或"{section_number}.x"的编号格式。

额外要求：{extra}

请直接输出章节正文内容，不要重复章节标题作为正文第一行。""")

# ─── API call ───
async def call_llm(system_prompt, user_prompt, label):
    if not API_KEY:
        print(f"[{label}] SKIPPED — No API_KEY set")
        return "(API Key 未设置)"
    
    print(f"[{label}] Calling {MODEL}...", end="", flush=True)
    start = time.time()
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/chat/completions",
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": TEMPERATURE,
                    "max_tokens": MAX_TOKENS,
                    "top_p": TOP_P,
                    "stream": False,
                },
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
            elapsed = time.time() - start
            if resp.status_code != 200:
                print(f" FAIL (HTTP {resp.status_code})")
                return f"API调用失败: HTTP {resp.status_code}\n{resp.text[:500]}"
            
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            print(f" OK ({elapsed:.1f}s, {usage.get('total_tokens','?')} tokens)")
            return content
        except Exception as e:
            print(f" FAIL ({e})")
            return f"API调用异常: {e}"

# ─── Main ───
async def main():
    print("=" * 70)
    print("  应急预案 Prompt 对比测试")
    print(f"  Model: {MODEL}  |  Temperature: {TEMPERATURE}")
    print("=" * 70)
    
    if not API_KEY:
        print("\n⚠ 未设置 DEEPSEEK_KEY 环境变量")
        print("  设置方法: $env:DEEPSEEK_KEY='sk-xxxxx'; python test_prompt_compare.py")
        print("  或者: $env:DEEPSEEK_KEY='sk-xxxxx'; $env:DEEPSEEK_MODEL='deepseek-v4-pro'; python test_prompt_compare.py")
        return
    
    out_dir = os.path.join(os.path.dirname(__file__) or ".", "prompt_test_results")
    os.makedirs(out_dir, exist_ok=True)
    
    results = []
    
    for sec in TEST_SECTIONS:
        print(f"\n{'─'*50}")
        print(f"  测试章节: {sec['title']}")
        print(f"{'─'*50}")
        
        user_prompt = build_section_prompt(sec["title"], ENTERPRISE_DATA, sec["extra"], sec["number"])
        
        # OLD
        old_content = await call_llm(OLD_SYSTEM_PROMPT, user_prompt, "OLD prompt")
        
        # NEW
        new_content = await call_llm(NEW_SYSTEM_PROMPT, user_prompt, "NEW prompt")
        
        # Save
        base_name = sec["section_key"]
        with open(os.path.join(out_dir, f"{base_name}_old.md"), "w", encoding="utf-8") as f:
            f.write(old_content)
        with open(os.path.join(out_dir, f"{base_name}_new.md"), "w", encoding="utf-8") as f:
            f.write(new_content)
        
        results.append({
            "section": sec["title"],
            "old_file": f"{base_name}_old.md",
            "new_file": f"{base_name}_new.md",
            "old_chars": len(old_content),
            "new_chars": len(new_content),
        })
        
        # Print side-by-side preview
        print(f"\n  ┌─ OLD (前300字) ─────────────────────")
        for line in old_content[:300].split("\n")[:12]:
            print(f"  │ {line}")
        print(f"  └{'─'*38}")
        print(f"\n  ┌─ NEW (前300字) ─────────────────────")
        for line in new_content[:300].split("\n")[:12]:
            print(f"  │ {line}")
        print(f"  └{'─'*38}")
    
    # Summary
    print(f"\n{'='*70}")
    print("  测试完成！结果已保存到: prompt_test_results/")
    print(f"{'='*70}")
    for r in results:
        print(f"  {r['section']}: OLD={r['old_chars']}字 / NEW={r['new_chars']}字")
    print(f"  对比文件:")
    for r in results:
        print(f"    {r['old_file']}  vs  {r['new_file']}")

if __name__ == "__main__":
    asyncio.run(main())
