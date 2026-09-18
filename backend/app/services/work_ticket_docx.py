"""作业票法定票面 DOCX 渲染与打印快照。

打印即固化：每次打印生成不可变快照（含内容 hash），之后修改票据内容
只能产生新的打印版本。没有这条，"票面被事后改过"就无法证明。

票面结构依据 GB 30871-2022 附录A 表A.1~A.8；三联标注依据附录B 表B.2。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional, Sequence

from docx import Document
from docx.shared import Pt

from app.services.docx_template import (
    add_body_title,
    add_normal_paragraph,
    build_table,
    register_all_styles,
    set_page_margins,
)

logger = logging.getLogger("work_ticket_docx")

# 依据 GB 30871-2022 附录B 表B.2「安全作业票的持有及保存」
THREE_COPIES = [
    "第一联 监护人/作业单位",
    "第二联 所在基层单位",
    "第三联 存档",
]


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def build_snapshot(
    *,
    instance,
    template,
    node_records: Sequence[dict],
    gas_tests: Sequence[dict],
) -> dict:
    """构造打印快照。只包含票面所需字段，不塞无关数据。"""
    values = instance.values or {}
    fields = sorted(getattr(template, "fields", []) or [], key=lambda f: f.sort_order)
    measures = sorted(getattr(template, "measures", []) or [], key=lambda m: m.sort_order)
    confirmed = set(values.get("confirmed_measures", []) or [])
    return {
        "code": instance.code,
        "ticket_type": instance.ticket_type,
        "level": instance.level,
        "status": instance.status,
        "valid_from": _iso(instance.valid_from),
        "valid_to": _iso(instance.valid_to),
        "fields": [
            {
                "label": f.label,
                "value": values.get(f.field_key),
            }
            for f in fields
        ],
        "measures": [
            {
                "sort_order": m.sort_order,
                "measure_text": m.measure_text,
                "article_anchor": m.article_anchor,
                "confirmed": m.sort_order in confirmed,
            }
            for m in measures
        ],
        "node_records": [
            {
                "node_key": r.get("node_key"),
                "action": r.get("action"),
                "acted_by": r.get("acted_by"),
                "opinion": r.get("opinion"),
                "created_at": _iso(r.get("created_at")),
            }
            for r in node_records
        ],
        "gas_tests": [
            {
                "sampled_at": _iso(g.get("sampled_at")),
                "location": g.get("location"),
                "gas_type": g.get("gas_type"),
                "result": g.get("result"),
                "tester": g.get("tester"),
                "conclusion": g.get("conclusion"),
            }
            for g in gas_tests
        ],
        "copies": list(THREE_COPIES),
    }


def content_hash(snapshot: dict) -> str:
    """内容 hash。按键排序序列化，保证键序变化不影响结果。"""
    body = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def render_ticket_docx(*, snapshot: dict, company_name: str = "") -> Document:
    """渲染法定票面。版式复用 docx_template 的公文能力。"""
    doc = Document()
    register_all_styles(doc)
    section = doc.sections[0]
    set_page_margins(section, 2.0, 2.0, 2.0, 2.0)

    title = f"{snapshot.get('ticket_type', '')} 安全作业票"
    add_body_title(doc, title)
    if company_name:
        add_normal_paragraph(doc, f"单位名称：{company_name}")
    add_normal_paragraph(doc, f"编号：{snapshot.get('code', '')}")
    if snapshot.get("level"):
        add_normal_paragraph(doc, f"作业级别：{snapshot['level']}")

    build_table(
        doc,
        ["项目", "内容"],
        [[f["label"], "" if f["value"] is None else str(f["value"])] for f in snapshot["fields"]],
    )

    if snapshot["gas_tests"]:
        add_normal_paragraph(doc, "气体检测记录")
        build_table(
            doc,
            ["取样时间", "地点", "气体", "结果", "分析人", "结论"],
            [
                [
                    g["sampled_at"] or "",
                    g["location"] or "",
                    g["gas_type"] or "",
                    g["result"] or "",
                    g["tester"] or "",
                    g["conclusion"] or "",
                ]
                for g in snapshot["gas_tests"]
            ],
        )

    add_normal_paragraph(doc, "安全措施确认")
    build_table(
        doc,
        ["序号", "安全措施", "依据条款", "是否确认"],
        [
            [str(m["sort_order"]), m["measure_text"], m["article_anchor"],
             "已确认" if m["confirmed"] else "未确认"]
            for m in snapshot["measures"]
        ],
    )

    if snapshot["node_records"]:
        add_normal_paragraph(doc, "审批记录")
        build_table(
            doc,
            ["节点", "动作", "办理人", "意见", "时间"],
            [
                [r["node_key"] or "", r["action"] or "", r["acted_by"] or "",
                 r["opinion"] or "", r["created_at"] or ""]
                for r in snapshot["node_records"]
            ],
        )

    add_normal_paragraph(doc, "作业票份数：" + "；".join(snapshot["copies"]))
    add_normal_paragraph(doc, "注：本票应至少保存一年（GB 30871-2022 附录B.3）。")
    return doc
