"""GB 18218-2018 标准常量 ORM。

这四张表存的是**标准原文**（临界量、校正系数、分级阈值），用于展示、审计与证据链；
计算引擎的判级逻辑写在 app/services/major_hazard_calc.py 里（纯函数），
并由 tests/test_major_hazard_calc.py 与 tests/test_major_hazard_models.py 双向对齐，
避免"数据驱动计算"在常量被误改时静默算错。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CriticalQuantity(Base):
    """GB 18218-2018 表1/表2：危险化学品的临界量 Q（吨）。"""

    __tablename__ = "critical_quantities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    table_no: Mapped[str] = mapped_column(String(4), nullable=False)  # '1' | '2'
    chemical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String(500))
    cas_no: Mapped[Optional[str]] = mapped_column(String(120))
    category: Mapped[Optional[str]] = mapped_column(String(80))  # 表2 的类别
    symbol: Mapped[Optional[str]] = mapped_column(String(20))  # 表2 的符号（J1/W1.1）
    critical_t: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    critical_note: Mapped[Optional[str]] = mapped_column(String(80))  # 如"150(净重)"
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HazardBetaFactor(Base):
    """GB 18218-2018 表3/表4：校正系数 β。"""

    __tablename__ = "hazard_beta_factors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    source_table: Mapped[str] = mapped_column(String(4), nullable=False)  # '3' | '4'
    chemical_name: Mapped[Optional[str]] = mapped_column(String(200))  # 表3
    category: Mapped[Optional[str]] = mapped_column(String(80))  # 表4
    symbol: Mapped[Optional[str]] = mapped_column(String(20))  # 表4（J1/W5.2…）
    beta: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExposureAlphaFactor(Base):
    """GB 18218-2018 表5：厂外可能暴露人员校正系数 α。"""

    __tablename__ = "exposure_alpha_factors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    population_min: Mapped[int] = mapped_column(Integer, nullable=False)
    population_max: Mapped[Optional[int]] = mapped_column(Integer)
    alpha: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MajorHazardLevel(Base):
    """GB 18218-2018 表6：重大危险源级别与 R 值的对应关系。"""

    __tablename__ = "major_hazard_levels"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    level_name: Mapped[str] = mapped_column(String(20), nullable=False)  # 一级/二级/三级/四级
    r_expression: Mapped[str] = mapped_column(String(60), nullable=False)  # 原文表达，如 "R≥100"
    r_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    r_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
