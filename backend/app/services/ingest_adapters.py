"""三种来源适配：把原始输入拆成"带来源定位的行"。

共同契约：返回 [{source_locator, confidence, raw_payload}]，
由调用方交给 ingest_service.create_item 落成 pending 条目。
本模块**不接触数据库**，便于单测。
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence


class AdapterError(ValueError):
    """输入结构不满足适配要求（如缺必填列）。"""


def rows_from_file_text(text: Optional[str], filename: str) -> list[dict]:
    """文件抽取形态：把纯文本按段落切成候选行。

    真正的字段抽取由 AI 完成（见计划 6），本函数只负责**分段 + 标注来源定位**，
    保证每条后续抽取结果都能追溯回原文位置。
    """
    if not text or not text.strip():
        return []
    rows: list[dict] = []
    for idx, block in enumerate(re.split(r"\n\s*\n", text), start=1):
        block = block.strip()
        if not block:
            continue
        rows.append(
            {
                "source_locator": f"{filename} 段{idx}",
                "confidence": "low",  # 未经过 AI 抽取与人工确认，一律先标 low
                "raw_payload": {"text": block, "origin_file": filename},
            }
        )
    return rows


def rows_from_sheet(
    raw_rows: Sequence[Sequence],
    mapping: dict[str, str],
    required: Iterable[str] = (),
) -> list[dict]:
    """表格导入形态：首行作表头，按 mapping（源列名→目标字段）逐行转换。

    必填字段必须在 mapping 的值里出现，否则直接报错——不能等到每行都缺字段才发现。
    """
    if not raw_rows:
        return []
    header = [str(h).strip() if h is not None else "" for h in raw_rows[0]]
    required_set = set(required)
    mapped_targets = set(mapping.values())
    missing = required_set - mapped_targets
    if missing:
        raise AdapterError(f"必填字段未在映射表中覆盖：{sorted(missing)}")

    index_of = {name: i for i, name in enumerate(header) if name}
    for target in required_set:
        src = next((s for s, t in mapping.items() if t == target), None)
        if src is not None and src not in index_of:
            raise AdapterError(f"必填字段「{target}」对应的源列「{src}」不在表头中")

    rows: list[dict] = []
    for line_no, raw in enumerate(raw_rows[1:], start=2):
        if raw is None:
            continue
        values = list(raw)
        if not any(str(v).strip() for v in values if v is not None):
            continue  # 跳过空行
        payload: dict = {}
        for src_name, target in mapping.items():
            col = index_of.get(src_name)
            if col is None or col >= len(values):
                continue
            cell = values[col]
            payload[target] = cell.strip() if isinstance(cell, str) else cell
        rows.append(
            {
                "source_locator": f"第 {line_no} 行",
                "confidence": "high",  # 结构化表格直接映射，可信度高于文本抽取
                "raw_payload": payload,
            }
        )
    return rows


async def ingest_rows(
    db,
    *,
    job_id: str,
    source_id: str,
    target_entity: str,
    rows: Sequence[dict],
) -> dict:
    """把适配产出的行落成 pending 条目。返回 {created, skipped}。"""
    from app.services.ingest_service import build_idempotency_key, create_item

    created = skipped = 0
    for row in rows:
        key = build_idempotency_key(
            source_id=source_id,
            target=target_entity,
            external_id=row.get("source_locator"),
            payload=row.get("raw_payload"),
        )
        out = await create_item(
            db,
            job_id=job_id,
            idempotency_key=key,
            raw_payload=row["raw_payload"],
            target_entity=target_entity,
            source_locator=row.get("source_locator"),
            confidence=row.get("confidence", "medium"),
        )
        if out["created"]:
            created += 1
        else:
            skipped += 1
    return {"created": created, "skipped": skipped}
