"""风险分级管控清单：层级展平、默认管控层级、Excel 台账导出、公开脱敏。"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def default_control_level(mapping: dict, current_level: str | None) -> str:
    """按现有风险等级查默认管控层级；未知/缺失回退「岗位」。"""
    return mapping.get(current_level or "", "岗位")


def flatten_rows(zones: list, mapping: dict) -> list[dict]:
    """把 分区→风险点→单元→事件 树展平为清单行（含 zone_id/object_id 供筛选）。"""
    rows = []
    for z in zones:
        for obj in z.objects or []:
            for unit in obj.units or []:
                for ev in unit.events or []:
                    rows.append(_row(z, obj, unit, ev, mapping))
            for ev in obj.events or []:
                rows.append(_row(z, obj, None, ev, mapping))
    return rows


def _row(z, obj, unit, ev, mapping) -> dict:
    measures = "；".join(
        f"{m.measure_category}:{m.description}" for m in (ev.measures or [])) or "-"
    return {
        "zone_id": z.id, "object_id": obj.id,
        "zone": z.name, "object": obj.name, "unit": unit.name if unit else "-",
        "accident": ev.accident_type, "inherent": ev.inherent_risk_level or ev.risk_level or "-",
        "current": ev.risk_level or "-",
        "control_level": ev.control_level or default_control_level(mapping, ev.risk_level),
        "measures": measures, "unit_name": obj.responsible_unit or "-",
        "person": obj.responsible_person or "-", "phone": obj.contact_phone or "-",
    }


_COLUMN_MAP = {
    "分区": "zone", "风险点": "object", "单元": "unit", "事故类型": "accident",
    "固有等级": "inherent", "现有等级": "current", "管控层级": "control_level",
    "管控措施": "measures", "责任单位": "unit_name", "责任人": "person", "联系电话": "phone",
}


def build_ledger_workbook(rows: list[dict]) -> Workbook:
    """把英文键行（flatten_rows 输出）写入中文表头台账。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "风险管控清单"
    headers = list(_COLUMN_MAP)
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="EEF2F7")
    for r in rows:
        ws.append([r[_COLUMN_MAP[h]] for h in headers])
    return wb


PUBLIC_FIELDS = ["zone", "object", "unit", "accident", "inherent", "current",
                 "control_level", "measures", "unit_name"]


def desensitize(rows: list[dict]) -> list[dict]:
    """公开脱敏：仅保留 PUBLIC_FIELDS，不含 person/phone/内部键。"""
    return [{k: r.get(k) for k in PUBLIC_FIELDS} for r in rows]
