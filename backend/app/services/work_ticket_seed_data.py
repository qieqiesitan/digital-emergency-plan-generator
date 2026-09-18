"""GB 30871-2022 附录A/B 的种子数据与措施解析。

为什么字段与审批矩阵用常量表而不是解析：
附录A 的表格由 PDF 转换而来，存在合并单元格与跨行说明，纯解析易错，
而这两块体量很小（每类票约 15 字段、审批矩阵 4 行）。
人工抄录并标注出处更可靠；数量大的措施清单才值得写解析器。
"""

from __future__ import annotations

import re

STANDARD_REF = "GB 30871-2022"

# 依据：GB 30871-2022 附录B 表B.1「安全作业票的办理、审批内容」
# 说明：办理部门一列对动火票统一为"危险化学品企业"，此处不重复存储。
APPROVAL_MATRIX: list[dict] = [
    {"code": "DHZY", "level": "特级", "approver": "主管领导"},
    {"code": "DHZY", "level": "一级", "approver": "安全管理部门"},
    {"code": "DHZY", "level": "二级", "approver": "所在基层单位"},
    {"code": "YXKJ", "level": None, "approver": "所在基层单位"},
]

# 依据：GB 30871-2022 附录A 表A.1（动火安全作业票）、表A.2（受限空间安全作业票）
# 字段清单为人工抄录，group_name 用于开票向导的分步。
_COMMON_TAIL_FIELDS = [
    {"field_key": "risk_identification", "label": "风险辨识结果", "field_type": "textarea",
     "group_name": "危害因素", "is_required": True, "allow_ai_prefill": True},
    {"field_key": "related_tickets", "label": "关联的其他特殊作业及安全作业票编号",
     "field_type": "text", "group_name": "基本信息", "is_required": False},
]

# 动火票三个等级（特级/一级/二级）票面字段一致——标准附录A 表A.1 只给一套样式，
# 等级差异落在模板行的 level 与审批矩阵上，故三个模板共用同一份字段定义。
_FIRE_FIELDS: list[dict] = [
    {"field_key": "applicant_unit", "label": "作业申请单位", "field_type": "text",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "apply_time", "label": "作业申请时间", "field_type": "datetime",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "work_content", "label": "作业内容", "field_type": "textarea",
     "group_name": "作业内容", "is_required": True, "allow_ai_prefill": True},
    {"field_key": "fire_location", "label": "动火地点及动火部位", "field_type": "text",
     "group_name": "作业内容", "is_required": True},
    {"field_key": "fire_level", "label": "动火作业级别", "field_type": "select",
     "group_name": "作业内容", "is_required": True,
     "options": {"choices": ["特级", "一级", "二级"]}},
    {"field_key": "fire_method", "label": "动火方式", "field_type": "text",
     "group_name": "作业内容", "is_required": True},
    {"field_key": "fire_person", "label": "动火人及证书编号", "field_type": "text",
     "group_name": "人员", "is_required": True},
    {"field_key": "work_unit", "label": "作业单位", "field_type": "text",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "work_leader", "label": "作业负责人", "field_type": "text",
     "group_name": "人员", "is_required": True},
    {"field_key": "work_period", "label": "动火作业实施时间", "field_type": "datetimerange",
     "group_name": "基本信息", "is_required": True},
    *_COMMON_TAIL_FIELDS,
]

_FIRE_LEVELS = ("特级", "一级", "二级")

_FIRE_TEMPLATES: list[dict] = [
    {
        "code": "DHZY",
        "name": "动火安全作业票",
        "level": level,
        "is_graded": True,
        "chapter": 5,
        "fields": _FIRE_FIELDS,
    }
    for level in _FIRE_LEVELS
]

_CONFINED_SPACE_TEMPLATE: dict = {
    "code": "YXKJ",
    "name": "受限空间安全作业票",
    "level": None,
    "is_graded": False,
    "chapter": 6,
    "fields": [
        {"field_key": "applicant_unit", "label": "作业申请单位", "field_type": "text",
         "group_name": "基本信息", "is_required": True},
        {"field_key": "apply_time", "label": "作业申请时间", "field_type": "datetime",
         "group_name": "基本信息", "is_required": True},
        {"field_key": "space_location", "label": "受限空间名称及位置", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "work_content", "label": "作业内容", "field_type": "textarea",
         "group_name": "作业内容", "is_required": True, "allow_ai_prefill": True},
        {"field_key": "work_unit", "label": "作业单位", "field_type": "text",
         "group_name": "基本信息", "is_required": True},
        {"field_key": "work_leader", "label": "作业负责人", "field_type": "text",
         "group_name": "人员", "is_required": True},
        {"field_key": "guardian", "label": "监护人", "field_type": "text",
         "group_name": "人员", "is_required": True},
        {"field_key": "work_period", "label": "作业实施时间", "field_type": "datetimerange",
         "group_name": "基本信息", "is_required": True},
        *_COMMON_TAIL_FIELDS,
    ],
}

TEMPLATES: list[dict] = [*_FIRE_TEMPLATES, _CONFINED_SPACE_TEMPLATE]

_MEASURE_ROW = re.compile(r"^\|\s*\d+\s*\|\s*(?P<text>[^|]{4,})\|")


def parse_measures(text: str, *, chapter: int) -> list[dict]:
    """从附录A 的措施表格里抽出措施条目。

    只认「序号 | 措施正文 | 是否涉及 | 确认人」这种四列行；
    条款锚点按章节号生成（如第 5 章 → GB 30871-2022 5）。
    """
    if not text:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        m = _MEASURE_ROW.match(line.strip())
        if not m:
            continue
        measure = m.group("text").strip()
        if len(measure) < 6:
            continue
        out.append(
            {
                "measure_text": measure,
                "article_anchor": f"{STANDARD_REF} {chapter}",
                "is_mandatory": True,
                "sort_order": len(out) + 1,
            }
        )
    return out
