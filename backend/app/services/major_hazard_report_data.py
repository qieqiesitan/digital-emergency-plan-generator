"""重大危险源辨识报告：章节装配（纯数据，不碰 docx）。

把版式与内容分开：本模块只产 [{"key","title","content"}]，
交给 app/services/report_docx.generate_report_docx 渲染。
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Iterable, Optional

logger = logging.getLogger("major_hazard_report_data")

STANDARD_LABEL = "GB 18218-2018《危险化学品重大危险源辨识》"

UNIT_TYPE_LABEL = {"production": "生产单元", "storage": "储存单元"}


class ReportNotReadyError(ValueError):
    """报告所需数据不完整（最常见：还没固化过计算快照）。"""


def _num(value: Any, digits: int = 6) -> str:
    """Decimal/float → 去尾零字符串；None → '—'。"""
    if value is None:
        return "—"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return str(round(n, digits)).rstrip("0").rstrip(".") or "0"


def conclusion_sentence(snapshot: dict, unit_name: str) -> str:
    """生成辨识结论一句话。不构成时也要显式写出来，不能留空。"""
    if snapshot.get("is_major_hazard"):
        return (
            f"经辨识，本单位「{unit_name}」内危险化学品的数量已等于或超过 "
            f"{STANDARD_LABEL} 表1/表2 规定的临界量，构成危险化学品重大危险源，"
            f"分级指标 R = {_num(snapshot.get('r_value'))}，"
            f"判定为**{snapshot.get('level') or '（未定级）'}重大危险源**。"
        )
    return (
        f"经辨识，本单位「{unit_name}」内危险化学品的数量未达到 "
        f"{STANDARD_LABEL} 表1/表2 规定的临界量，"
        f"不构成危险化学品重大危险源（辨识指标 s = {_num(snapshot.get('s_value'))} < 1）。"
    )


def _basic_chapter(enterprise_name: str, unit, record) -> dict:
    lines = [
        f"- 单位名称：{enterprise_name}",
        f"- 单元名称：{unit.name}",
        f"- 单元类型：{UNIT_TYPE_LABEL.get(unit.unit_type, unit.unit_type)}",
    ]
    if getattr(unit, "boundary_desc", None):
        lines.append(f"- 单元边界：{unit.boundary_desc}")
    if getattr(unit, "address", None):
        lines.append(f"- 所在位置：{unit.address}")
    if getattr(unit, "department", None) or getattr(unit, "responsible_person", None):
        lines.append(
            f"- 责任部门及责任人：{getattr(unit, 'department', None) or '—'} / "
            f"{getattr(unit, 'responsible_person', None) or '—'}"
        )
    if record is not None and getattr(record, "hazard_code", None):
        lines.append(f"- 重大危险源编码：{record.hazard_code}")
    return {"key": "basic", "title": "一、企业基本情况", "content": "\n".join(lines)}


def _basis_chapter(evidences: Iterable[dict]) -> dict:
    anchors = [e.get("article_anchor") for e in evidences if e.get("article_anchor")]
    lines = [
        f"本报告依据 {STANDARD_LABEL} 编制。",
        "",
        "辨识方法：单元内存在危险化学品的数量等于或超过表1、表2 规定的临界量时，"
        "即定为重大危险源。多品种按式(1) 计算，s ≥ 1 即构成；"
        "分级按式(2) R = α × Σ βi × (qi/Qi) 计算，按表6 判定级别。",
    ]
    if anchors:
        lines += ["", "具体引用条文："] + [f"- {a}" for a in anchors]
    return {"key": "basis", "title": "二、辨识依据与方法", "content": "\n".join(lines)}


def _units_chapter(unit) -> dict:
    rows = [
        "| 单元名称 | 单元类型 | 所在位置 | 责任部门 | 责任人 |",
        "|---|---|---|---|---|",
        f"| {unit.name} | {UNIT_TYPE_LABEL.get(unit.unit_type, unit.unit_type)} | "
        f"{getattr(unit, 'address', None) or '—'} | {getattr(unit, 'department', None) or '—'} | "
        f"{getattr(unit, 'responsible_person', None) or '—'} |",
    ]
    return {"key": "units", "title": "三、重大危险源单元清单", "content": "\n".join(rows)}


def _chemicals_chapter(chemicals: list) -> dict:
    rows = [
        "| 危险化学品 | 物理状态 | 设计最大量 q(t) | 临界量 Q(t) | 校正系数 β | β 来源 |",
        "|---|---|---|---|---|---|",
    ]
    for c in chemicals:
        source_label = {
            "table3": "表3（按名称）",
            "table4": "表4（按危险性类别）",
            "manual": "人工指定",
        }.get(getattr(c, "beta_source", "manual"), "人工指定")
        rows.append(
            f"| {c.chemical_name} | {getattr(c, 'physical_state', None) or '—'} | "
            f"{_num(c.q_design_max)} | {_num(c.critical_quantity_t)} | "
            f"{_num(c.beta, 3)} | {source_label} |"
        )
    rows += [
        "",
        "注：设计最大量按 GB 18218-2018 4.2.2 确定——储罐及其他容器、设备或仓储区的"
        "危险化学品实际存在量按设计最大量计，非台账登记的日常储存量。",
    ]
    return {"key": "chemicals", "title": "四、单元内危险化学品与临界量", "content": "\n".join(rows)}


def _metrics_chapter(snapshot: dict) -> dict:
    rows = [
        "| 危险化学品 | qi(t) | Qi(t) | qi/Qi | βi | βi×qi/Qi |",
        "|---|---|---|---|---|---|",
    ]
    for item in snapshot.get("chemicals", []):
        rows.append(
            f"| {item['name']} | {_num(item['q'])} | {_num(item['Q'])} | "
            f"{_num(item['q_over_Q'])} | {_num(item['beta'], 3)} | "
            f"{_num(item['beta_times_q_over_Q'])} |"
        )
    rows += [
        "",
        f"按式(1)：**s = Σqi/Qi = {_num(snapshot.get('s_value'))}**",
        f"结论：{'构成' if snapshot.get('is_major_hazard') else '不构成'}重大危险源"
        f"（{'s ≥ 1' if snapshot.get('is_major_hazard') else 's < 1'}）。",
    ]
    return {"key": "metrics", "title": "五、辨识指标计算", "content": "\n".join(rows)}


def _grading_chapter(snapshot: dict) -> dict:
    if not snapshot.get("is_major_hazard"):
        return {
            "key": "grading",
            "title": "六、分级判定",
            "content": (
                f"该单元辨识指标 s = {_num(snapshot.get('s_value'))} < 1，"
                "**不构成危险化学品重大危险源**，故不进行分级判定。"
            ),
        }
    return {
        "key": "grading",
        "title": "六、分级判定",
        "content": "\n".join(
            [
                f"- 厂区外 500m 范围内可能暴露人员数量：{snapshot.get('exposed_population')} 人",
                f"- 暴露人员校正系数 α：{_num(snapshot.get('alpha'), 2)}（GB 18218-2018 表5）",
                f"- 分级指标 R = α × Σβi×(qi/Qi) = **{_num(snapshot.get('r_value'))}**",
                f"- 判定级别：**{snapshot.get('level') or '（未定级）'}**（GB 18218-2018 表6）",
                "",
                "分级标准：一级 R≥100；二级 100>R≥50；三级 50>R≥10；四级 R<10。",
            ]
        ),
    }


def _conclusion_chapter(snapshot: dict, unit) -> dict:
    return {
        "key": "conclusion",
        "title": "七、辨识结论",
        "content": conclusion_sentence(snapshot, unit.name),
    }


def _responsible_chapter(record) -> dict:
    if record is None:
        return {
            "key": "responsible",
            "title": "八、包保责任人",
            "content": "该单元**尚未建立档案**，包保责任人信息待补充后另行报备。",
        }
    rows = [
        "| 职责 | 姓名 | 职务 | 联系电话 |",
        "|---|---|---|---|",
    ]
    for label, prefix in (("主要负责人", "chief"), ("技术负责人", "tech"), ("操作负责人", "oper")):
        rows.append(
            f"| {label} | {getattr(record, f'{prefix}_name', None) or '—'} | "
            f"{getattr(record, f'{prefix}_post', None) or '—'} | "
            f"{getattr(record, f'{prefix}_phone', None) or '—'} |"
        )
    return {"key": "responsible", "title": "八、包保责任人", "content": "\n".join(rows)}


def _appendix_chapter(evidences: Iterable[dict]) -> dict:
    items = list(evidences)
    if not items:
        content = "本报告未单独挂载法规条文依据。"
    else:
        lines = []
        for e in items:
            note = f"（{e['note']}）" if e.get("note") else ""
            relation = e.get("relation") or "依据"
            lines.append(f"- {e['article_anchor']} — {relation}{note}")
        content = "\n".join(lines)
    return {"key": "appendix", "title": "附录：法规依据条文", "content": content}


def build_chapters(
    *,
    enterprise_name: str,
    unit,
    chemicals: list,
    snapshot: Optional[dict],
    record: Optional[Any],
    evidences: Iterable[dict],
) -> list[dict]:
    """装配全部章节。没有计算快照时直接拒绝——没有结论的报告是废纸。"""
    if snapshot is None:
        raise ReportNotReadyError(
            "该单元尚未进行辨识计算，请先在「计算与分级」页固化一次结果后再导出报告"
        )
    evidence_list = list(evidences)
    return [
        _basic_chapter(enterprise_name, unit, record),
        _basis_chapter(evidence_list),
        _units_chapter(unit),
        _chemicals_chapter(chemicals),
        _metrics_chapter(snapshot),
        _grading_chapter(snapshot),
        _conclusion_chapter(snapshot, unit),
        _responsible_chapter(record),
        _appendix_chapter(evidence_list),
    ]
