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

# 其余 6 类的字段定义（依据 GB 30871-2022 附录A 表A.3~A.8）
# 每类的通用首尾字段（申请单位/时间/作业内容/作业单位/负责人/实施时间/风险辨识/关联票）
# 与专用字段（如盲板抽堵的"盲板编号/规格"、高处的"作业高度/作业方式"）区分开
_COMMON_HEAD_FIELDS = [
    {"field_key": "applicant_unit", "label": "作业申请单位", "field_type": "text",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "apply_time", "label": "作业申请时间", "field_type": "datetime",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "work_content", "label": "作业内容", "field_type": "textarea",
     "group_name": "作业内容", "is_required": True, "allow_ai_prefill": True},
    {"field_key": "work_unit", "label": "作业单位", "field_type": "text",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "work_leader", "label": "作业负责人", "field_type": "text",
     "group_name": "人员", "is_required": True},
    {"field_key": "work_period", "label": "作业实施时间", "field_type": "datetimerange",
     "group_name": "基本信息", "is_required": True},
]

# 各类型的专用字段（按附录A 表A.3~A.8 人工抄录，供逐条核对出处）
_TYPE_SPECIFIC_FIELDS: dict[str, list[dict]] = {
    "MBCD": [
        {"field_key": "blind_plate_no", "label": "盲板编号", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "pipe_position", "label": "管线/设备位置", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "operate_type", "label": "作业类别", "field_type": "select",
         "group_name": "作业内容", "is_required": True,
         "options": {"choices": ["抽盲板", "堵盲板"]}},
    ],
    "GCZY": [
        {"field_key": "work_height", "label": "作业高度(m)", "field_type": "number",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "high_level", "label": "高处作业级别", "field_type": "select",
         "group_name": "作业内容", "is_required": True,
         "options": {"choices": ["Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"]}},
        {"field_key": "work_method", "label": "作业方式", "field_type": "text",
         "group_name": "作业内容", "is_required": False},
    ],
    "QZDZ": [
        {"field_key": "lift_weight", "label": "吊装质量(t)", "field_type": "number",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "lift_level", "label": "吊装作业级别", "field_type": "select",
         "group_name": "作业内容", "is_required": True,
         "options": {"choices": ["一级", "二级", "三级"]}},
        {"field_key": "lift_commander", "label": "吊装指挥", "field_type": "text",
         "group_name": "人员", "is_required": True},
        {"field_key": "lift_machine", "label": "起重机械及编号", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
    ],
    "LSYD": [
        {"field_key": "power_source", "label": "电源接入点", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "power_capacity", "label": "用电容量(kW)", "field_type": "number",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "electrician", "label": "电工及证书编号", "field_type": "text",
         "group_name": "人员", "is_required": True},
        {"field_key": "logout_person", "label": "作业结束后注销人", "field_type": "text",
         "group_name": "人员", "is_required": False},
    ],
    "PTZY": [
        {"field_key": "dig_location", "label": "动土地点及部位", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "dig_depth", "label": "动土深度(m)", "field_type": "number",
         "group_name": "作业内容", "is_required": False},
        {"field_key": "dig_method", "label": "动土方式", "field_type": "text",
         "group_name": "作业内容", "is_required": False},
    ],
    "DLZY": [
        {"field_key": "road_position", "label": "断路地点及部位", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "road_scope", "label": "断路范围及时间", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "traffic_plan", "label": "交通组织方案", "field_type": "textarea",
         "group_name": "危害因素", "is_required": False, "allow_ai_prefill": True},
    ],
}

_SIMPLE_TYPES = [
    ("MBCD", "盲板抽堵安全作业票", 7),
    ("LSYD", "临时用电安全作业票", 10),
    ("PTZY", "动土安全作业票", 11),
    ("DLZY", "断路安全作业票", 12),
]
_GRADED_TYPES = [
    ("GCZY", "高处安全作业票", 8, ["Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"]),
    ("QZDZ", "吊装安全作业票", 9, ["一级", "二级", "三级"]),
]

for _code, _name, _chapter in _SIMPLE_TYPES:
    TEMPLATES.append({
        "code": _code, "name": _name, "level": None, "is_graded": False,
        "chapter": _chapter, "requires_gas_test": False,
        "fields": [*_COMMON_HEAD_FIELDS, *_TYPE_SPECIFIC_FIELDS[_code], *_COMMON_TAIL_FIELDS],
    })

for _code, _name, _chapter, _levels in _GRADED_TYPES:
    for _level in _levels:
        TEMPLATES.append({
            "code": _code, "name": f"{_name}（{_level}）", "level": _level, "is_graded": True,
            "chapter": _chapter, "requires_gas_test": False,
            "fields": [*_COMMON_HEAD_FIELDS, *_TYPE_SPECIFIC_FIELDS[_code], *_COMMON_TAIL_FIELDS],
        })

for _tpl in TEMPLATES:
    if _tpl["code"] in ("DHZY", "YXKJ"):
        _tpl.setdefault("requires_gas_test", True)

APPROVAL_MATRIX.extend([
    {"code": "MBCD", "level": None, "approver": "所在基层单位"},
    {"code": "GCZY", "level": "Ⅰ级", "approver": "所在基层单位"},
    {"code": "GCZY", "level": "Ⅱ级", "approver": "所在单位专业部门"},
    {"code": "GCZY", "level": "Ⅲ级", "approver": "所在单位专业部门"},
    {"code": "GCZY", "level": "Ⅳ级", "approver": "主管厂长或总工程师"},
    {"code": "QZDZ", "level": "一级", "approver": "主管厂长或总工程师"},
    {"code": "QZDZ", "level": "二级", "approver": "所在单位专业部门"},
    {"code": "QZDZ", "level": "三级", "approver": "所在单位专业部门"},
    {"code": "LSYD", "level": None, "approver": "配送电单位",
     "countersign": ["配送电单位"]},
    {"code": "PTZY", "level": None, "approver": "所在单位专业部门",
     "countersign": ["水", "电", "汽", "工艺", "设备", "消防", "安全管理"]},
    {"code": "DLZY", "level": None, "approver": "所在单位专业部门",
     "countersign": ["消防", "安全管理"]},
])

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
