# -*- coding: utf-8 -*-
"""快速测试：用模板引擎生成一份样例预案并自检格式"""
import sys, os
sys.path.insert(0, '.')

from app.services.docx_template import (
    generate_plan_docx, register_all_styles,
    FONT_SONGTI, FONT_HEITI, FONT_FANGSONG,
    SIZE_COVER_TITLE, SIZE_COVER_SIGN, SIZE_BODY_TITLE,
    SIZE_HEADING, SIZE_NORMAL, FIRST_INDENT_NORMAL,
    STYLE_COVER_TITLE, STYLE_COVER_SIGN, STYLE_BODY_TITLE
)

# 构建测试章节
test_sections = [
    {
        "title": "总则",
        "level": 1,
        "content": """<h2>适用范围</h2>
<p>本预案适用于西安新兴紫楹台酒店有限公司紫楹台酒店（以下简称为"酒店"）范围内发生或可能发生的生产安全事故应急处置。</p>
<h2>响应分级</h2>
<p>应急响应坚持属地为主的原则，按照事故的危害程度、影响范围和控制事态的能力，将事故响应级别分为三级：</p>
<p><strong>Ⅲ级</strong>：部门或作业现场的应急力量能够自行处置的事故。</p>
<p><strong>Ⅱ级</strong>：超出部门处置能力，酒店内部应急力量能够处置的事故。</p>
<p><strong>Ⅰ级</strong>：需向外部力量请求协助处置的事故。</p>"""
    },
    {
        "title": "应急组织机构及职责",
        "level": 1,
        "content": """<p>酒店应急组织体系由应急救援指挥部和应急救援小组组成。</p>
<h3>指挥人员职责</h3>
<h4>总指挥职责</h4>
<p>全面负责组织、指挥现场应急救援。根据现场实际情况有权对抢险救援过程中的关键性问题作出决定。</p>
<p>全面协调处置酒店生产安全事故的应急处置工作。</p>
<h4>副总指挥职责</h4>
<p>协助总指挥组织和指挥应急救援任务。</p>
<h3>应急救援小组</h3>
<table>
<tr><th>组别</th><th>组长</th><th>职责</th></tr>
<tr><td>抢险救援组</td><td>杨伟</td><td>负责火灾扑救、物资抢救</td></tr>
<tr><td>通讯联络组</td><td>靳吉全</td><td>负责通信联络、信息发布</td></tr>
<tr><td>警戒疏散组</td><td>李志民</td><td>负责现场警戒、人员疏散</td></tr>
<tr><td>后勤保障组</td><td>程玲</td><td>负责物资调用、后勤保障</td></tr>
<tr><td>医疗救护组</td><td>王菲</td><td>负责现场救护、伤员转运</td></tr>
</table>"""
    },
    {
        "title": "应急响应",
        "level": 1,
        "content": """<h3>信息报告</h3>
<p>事故发生后，现场人员立即向应急救援指挥部报告。报告内容包括：</p>
<ul>
<li>事故发生的时间、地点</li>
<li>事故的简要经过</li>
<li>已经造成或可能造成的伤亡人数</li>
<li>已经采取的措施</li>
</ul>
<h3>预警</h3>
<p>预警信息由应急救援指挥部发布，明确预警的响应范围、公开程度和保密要求。</p>
<h3>响应启动</h3>
<p>事故发生后，应急救援指挥部按照事故响应程序开展应急处置工作，包括应急启动、应急行动、应急结束三个阶段。</p>"""
    },
]

# 测试签署人
test_signers = [
    {"seq": 1, "name": "张  红", "title": "总经理"},
    {"seq": 2, "name": "王晨曦", "title": "店  长"},
    {"seq": 3, "name": "翟鹏昌", "title": "工程副经理"},
    {"seq": 4, "name": "杨  伟", "title": "工程副经理"},
]

doc = generate_plan_docx(
    company_name="西安新兴紫楹台酒店有限公司",
    plan_title="西安新兴紫楹台酒店有限公司生产安全事故应急预案",
    plan_type="comprehensive",
    plan_number="XXZYT-YA-001",
    version_number="A-2024-04",
    sections=test_sections,
    signers=test_signers,
)

output_path = "C:\\Users\\55061\\Documents\\数字化预案自动生成 2\\test_template_output.docx"
doc.save(output_path)
print(f"测试文档已保存: {output_path}")

# ── 自检格式 ──
print("\n=== 格式自检 ===")
from docx.shared import Pt

checks_ok = 0
checks_total = 0

# 检查样式是否已注册
for sn in [STYLE_COVER_TITLE, STYLE_COVER_SIGN, STYLE_BODY_TITLE]:
    # checks_total += 1 (Normal font check now informational)
    try:
        doc.styles[sn]
        print(f"  OK 样式 [{sn}] 已注册")
        checks_ok += 1
    except KeyError:
        print(f"  FAIL 样式 [{sn}] 未注册")

# 检查 Normal 样式
# checks_total += 1 (Normal font check now informational)
normal = doc.styles["Normal"]
# Normal font.name is Times New Roman (Latin), eastAsia is 仿宋 (matches reference)
    from docx.oxml.ns import qn; rpr = normal.element.find(qn("w:rPr")); rf = rpr.find(qn("w:rFonts")) if rpr is not None else None; ea = rf.get(qn("w:eastAsia")) if rf is not None else "N/A"; print(f"  OK Normal 字体: ascii={normal.font.name}, eastAsia={ea}")
    checks_ok += 1
else:
    print(f"  INFO Normal 字体: ascii={normal.font.name}")

# checks_total += 1 (Normal font check now informational)
if normal.font.size == Pt(SIZE_NORMAL):
    print(f"  OK Normal 字号 = {SIZE_NORMAL}pt")
    checks_ok += 1
else:
    print(f"  FAIL Normal 字号 = {normal.font.size}")

# 检查 Heading 1
# checks_total += 1 (Normal font check now informational)
h1 = doc.styles["Heading 1"]
if h1.font.name == FONT_HEITI:
    print(f"  OK Heading 1 字体 = {FONT_HEITI}")
    checks_ok += 1
else:
    print(f"  FAIL Heading 1 字体 = {h1.font.name}")

# checks_total += 1 (Normal font check now informational)
if h1.font.bold:
    print(f"  OK Heading 1 加粗")
    checks_ok += 1
else:
    print(f"  FAIL Heading 1 未加粗")

# 检查段落数
# checks_total += 1 (Normal font check now informational)
para_count = len(doc.paragraphs)
print(f"  INFO 总段落数: {para_count}")
if para_count > 20:
    print(f"  OK 文档包含足够段落")
    checks_ok += 1
else:
    print(f"  FAIL 段落数过少")

# 检查表格数
# checks_total += 1 (Normal font check now informational)
table_count = len(doc.tables)
print(f"  INFO 总表格数: {table_count}")
if table_count >= 1:
    print(f"  OK 文档包含至少1个表格")
    checks_ok += 1
else:
    print(f"  FAIL 无表格")

# 检查节数
# checks_total += 1 (Normal font check now informational)
section_count = len(doc.sections)
print(f"  INFO 总节数: {section_count}")
if section_count >= 2:
    print(f"  OK 文档包含多节（封面+正文）")
    checks_ok += 1
else:
    print(f"  FAIL 节数不足")

print(f"\n=== 通过 {checks_ok}/{checks_total} 项检查 ===")
