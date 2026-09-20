"""危化品「企业档案文本」与「台账」的一致性（D-2 修复）。

问题：`enterprises.hazardous_chemicals` 原为自由文本，与 `hazardous_chemicals`
台账表并存，且不同提示词各读一份（风险 AI 引导/周边 AI/章节生成读文本，台账明细
另走 `chemicals`）→ 真库出现过「档案写『无』、台账有 2 个品种」的矛盾。

口径：**台账是事实源，档案文本是派生摘要**。
- 台账非空 → 按台账重算档案文本（覆盖手填内容，消除矛盾）；
- 台账为空 → 保留用户手填文本（给还没建台账的企业做 AI 引导兜底）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical

MAX_NAMES = 40          # 摘要里最多列举的品种数，超出只计数
FIELD_LIMIT = 2000      # 与 EnterpriseUpdate schema 的 max_length 一致


def _fmt_amount(value) -> str:
    if value is None:
        return ""
    # Numeric 取回是 Decimal：整数显示不带小数点
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(num)) if num == int(num) else str(num)


def build_chemicals_summary(chemicals) -> str:
    """按台账生成档案文本，形如：`共 2 种：乙醇（CAS 64-17-5，储量 5 t）、氢气`。"""
    rows = [c for c in (chemicals or []) if (getattr(c, "name", "") or "").strip()]
    if not rows:
        return ""
    rows.sort(key=lambda c: c.name)
    items: list[str] = []
    for c in rows:
        extras: list[str] = []
        if getattr(c, "cas_no", None):
            extras.append(f"CAS {c.cas_no}")
        amount = _fmt_amount(getattr(c, "storage_amount", None))
        if amount:
            unit = (getattr(c, "storage_unit", None) or "").strip()
            extras.append(f"储量 {amount}{(' ' + unit) if unit else ''}")
        elif getattr(c, "max_storage", None):
            extras.append(f"最大储存量 {c.max_storage}")
        items.append(f"{c.name}（{'，'.join(extras)}）" if extras else c.name)
    text = f"共 {len(rows)} 种：" + "、".join(items[:MAX_NAMES])
    if len(rows) > MAX_NAMES:
        text += f" 等 {len(rows)} 种"
    return text[:FIELD_LIMIT]


def archive_text_block(enterprise) -> str:
    """提示词里用于交叉校验的「企业档案自述」块（台账 AI 引导共用）。"""
    text = (getattr(enterprise, "hazardous_chemicals", None) or "").strip()
    label = text if text else "（未填写）"
    return (
        f"- 企业档案自述危险化学品：{label}\n"
        "  若自述与已录台账不一致，请以台账为准，并在问题或结果中提示该差异。"
    )


async def sync_enterprise_chemicals_summary(db: AsyncSession, enterprise_id: str) -> str | None:
    """按台账重算档案文本；台账为空或无需改动时返回 None（不写库、不提交）。

    调用方负责 commit（与自身事务一起提交，避免半更新）。
    """
    rows = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
    )).scalars().all()
    summary = build_chemicals_summary(rows)
    if not summary:
        return None
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )).scalar_one_or_none()
    if ent is None or (ent.hazardous_chemicals or "") == summary:
        return None
    ent.hazardous_chemicals = summary
    return summary


async def sync_after_ledger_change(db: AsyncSession, enterprise_id: str) -> None:
    """台账增删改后的统一收尾：先 flush 让改动对查询可见，再重算档案文本。

    不 commit——由调用方与自身事务一起提交（避免"台账写了、档案没写"的半更新）。
    """
    await db.flush()
    await sync_enterprise_chemicals_summary(db, enterprise_id)
