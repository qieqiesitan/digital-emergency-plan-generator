"""AI 抽取服务：把资料文本抽成结构化候选，落进 DataHub 待确认队列。

**本模块没有任何写业务表的路径**——只调 create_item 产出 pending 条目。
这是"未经人工确认不得入库"在代码结构上的保证。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.standard_constants import CriticalQuantity, HazardBetaFactor
from app.services.extraction_prompts import (
    ExtractionSchemaError,
    build_messages,
    validate_payload,
)
from app.services.ingest_service import build_idempotency_key, create_item
from app.services.llm_client import llm_text_completion

logger = logging.getLogger("extraction_service")

STANDARD = "GB18218-2018"
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def parse_model_json(raw: str) -> list[dict]:
    """解析模型输出。容忍代码围栏、单个对象、前后噪声。"""
    if not raw or not raw.strip():
        raise ValueError("模型返回为空")
    text = _FENCE.sub("", raw).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
        end = max(text.rfind("]"), text.rfind("}"))
        if start < 0 or end <= start:
            raise ValueError("模型输出不是合法 JSON") from None
        data = json.loads(text[start : end + 1])
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    raise ValueError("模型输出既不是对象也不是数组")


def reconcile_with_constants(
    row: dict,
    *,
    critical_rows: Sequence[CriticalQuantity],
    beta_rows: Sequence[HazardBetaFactor],
) -> dict:
    """用常量表复核 Q 与 β。

    **模型给的 Q/β 一律不采信。** Q 与 β 是 GB 18218 的法定查表值；
    查得到用表值，查不到留空并降级为 low，交人工指定危险性类别。
    """
    name = row.get("chemical_name")
    out = dict(row)

    q = None
    for c in critical_rows:
        if c.chemical_name == name and c.critical_t is not None:
            q = float(c.critical_t)
            break
    out["critical_quantity_t"] = q

    beta = None
    for b in beta_rows:
        if b.source_table == "3" and b.chemical_name == name:
            beta = float(b.beta)
            break
    out["beta"] = beta

    if q is None or beta is None:
        missing = []
        if q is None:
            missing.append("临界量")
        if beta is None:
            missing.append("校正系数 β")
        out["confidence"] = "low"
        out["review_note"] = (
            "、".join(missing) + "未能按标准查表得出，需人工指定危险性类别后补齐"
        )
    return out


async def _load_constants(db: AsyncSession, name: str):
    q_res = await db.execute(
        select(CriticalQuantity).where(
            CriticalQuantity.standard == STANDARD,
            CriticalQuantity.chemical_name == name,
        )
    )
    b_res = await db.execute(
        select(HazardBetaFactor).where(HazardBetaFactor.standard == STANDARD)
    )
    return list(q_res.scalars().all()), list(b_res.scalars().all())


async def extract_candidates(
    db: AsyncSession,
    *,
    job_id: str,
    source_id: str,
    target_entity: str,
    text: str,
    filename: str,
    ai_config,
    timeout: int = 120,
) -> dict:
    """抽取并落队列。返回 {queued, skipped, invalid}。"""
    messages = build_messages(target_entity=target_entity, text=text, source_hint=filename)
    raw = await llm_text_completion(messages, ai_config, timeout=timeout)
    try:
        rows = parse_model_json(raw)
    except ValueError as exc:
        raise ExtractionSchemaError(f"模型输出无法解析为 JSON：{exc}") from exc

    queued = skipped = invalid = 0
    for row in rows:
        try:
            valid = validate_payload(target_entity, row)
        except ExtractionSchemaError as exc:
            logger.warning("抽取结果结构不合法，已跳过：%s", exc)
            invalid += 1
            continue

        if target_entity == "major_hazard_unit_chemical":
            critical_rows, beta_rows = await _load_constants(db, valid.get("chemical_name"))
            valid = reconcile_with_constants(
                valid, critical_rows=critical_rows, beta_rows=beta_rows
            )

        key = build_idempotency_key(
            source_id=source_id,
            target=target_entity,
            external_id=valid.get("source_locator"),
            payload={k: v for k, v in valid.items() if k != "source_locator"},
        )
        out = await create_item(
            db,
            job_id=job_id,
            idempotency_key=key,
            raw_payload=valid,
            target_entity=target_entity,
            source_locator=valid.get("source_locator"),
            confidence=valid.get("confidence", "medium"),
        )
        if out["created"]:
            queued += 1
        else:
            skipped += 1
    return {"queued": queued, "skipped": skipped, "invalid": invalid}
