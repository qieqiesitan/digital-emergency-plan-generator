 # 风险管理功能全面重构 实现计划

 > **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development（推荐）逐任务实现。步骤使用复选框（`- [ ]`）语法跟踪进度。

 **目标：** 将当前扁平化的风险源管理（risk_sources 单表）重构为五层级风险分级管控体系（分区→对象→单元→事件→措施），支持 LS 矩阵/LEC/煤矿 LS/直接判定四种评估方法自动评定风险等级

 **架构：** 新增 6 张核心表（risk_zones / risk_objects / risk_units / risk_events / risk_measures / risk_assessment_methods），通过 JSONB 配置实现多方法计算引擎；前端以树状层级交互替代当前扁平表格；向下兼容旧 risk_sources 数据通过迁移向导导入

 **技术栈：** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL JSONB + React/TypeScript + Ant Design 5

 ---

 ## 数据模型设计

 ### 新表 ER 关系

 ```
 enterprises (1)───(N) risk_zones (1)───(N) risk_objects (1)───(N) risk_units (1)───(N) risk_events (1)───(N) risk_measures
                                    │                          │
                                    │ (risk_objects 可独立存在)  │ (risk_events 也可直接挂在 risk_objects 下)
                                    └──────────────────────────┴──────────────────────────────────────────┘
 ```

 ### 方法引擎设计

 四种方法各自的计算逻辑：

 | 方法 | 输入参数 | 计算 | 等级判定 |
 |------|----------|------|----------|
 | LS 矩阵 | L(1-5), S(1-5) | R = L × S | R≥20→重大, 15-16→较大, 9-12→一般, <9→低 |
 | LEC 评价法 | L(1-10), E(1-6), C(1-100) | D = L × E × C | D≥320→重大, 160-319→较大, 70-159→一般, <70→低 |
 | 煤矿 LS | L(1-5), S(1-5) | R = L × S | （使用煤矿行业专用判定表） |
 | 直接判定 | — | — | 人工选择等级 |

 方法配置存储在 `risk_assessment_methods.config` JSONB 中，包含完整的矩阵表、阈值表、分级标准文本。

 ---

 ## 文件结构

 | 文件 | 操作 | 职责 |
 |------|:--:|------|
 | `backend/db_migration_risk_overhaul.sql` | **新建** | 全部 DDL（6 表 + 旧表标记字段） |
 | `backend/app/models/risk_management.py` | **新建** | 6 个新 ORM 模型 |
 | `backend/app/schemas/risk_management.py` | **新建** | 全部 Pydantic schema |
 | `backend/app/services/risk_method_engine.py` | **新建** | 多方法计算引擎 |
 | `backend/app/services/risk_context_builder.py` | **新建** | 分级管控上下文构建（替代旧的 build_risk_assessment_context） |
 | `backend/app/routers/risk_management.py` | **新建** | 全层级 CRUD API（~30 个端点） |
 | `backend/app/routers/risk_sources_ext.py` | 修改 | 标记 deprecated，旧端点保留但返回 410 提示迁移 |
 | `backend/app/routers/risk_assessment.py` | 修改 | 报告生成上下文改用新模型 |
 | `backend/app/routers/enterprises.py` | 修改 | 企业详情增加 risk_method_config 字段 |
 | `backend/app/models/enterprise.py` | 修改 | Enterprise 增加 risk_method_config JSONB；RiskSource 增加 migrated 标记 |
 | `backend/app/main.py` | 修改 | 注册 risk_management 路由 |
 | `frontend/src/types/riskManagement.ts` | **新建** | 全层级 TS 类型定义 |
 | `frontend/src/services/riskManagementService.ts` | **新建** | 全层级 API 调用 |
 | `frontend/src/utils/riskMethodEngine.ts` | **新建** | 前端方法计算工具（实时预览评级） |
 | `frontend/src/components/enterprise/RiskMethodConfigPanel.tsx` | **新建** | 风险评估方法配置面板 |
 | `frontend/src/components/enterprise/RiskHierarchyTree.tsx` | **新建** | 五层层级树状组件 |
 | `frontend/src/components/enterprise/RiskZoneForm.tsx` | **新建** | 风险分区表单（含厂区平面图选区） |
 | `frontend/src/components/enterprise/RiskObjectForm.tsx` | **新建** | 风险分析对象/风险点表单 |
 | `frontend/src/components/enterprise/RiskUnitForm.tsx` | **新建** | 风险分析单元表单 |
 | `frontend/src/components/enterprise/RiskEventForm.tsx` | **新建** | 风险事件表单（含方法参数联动） |
 | `frontend/src/components/enterprise/RiskMeasureForm.tsx` | **新建** | 管控措施表单（含检查项目） |
 | `frontend/src/components/enterprise/RiskMigrationWizard.tsx` | **新建** | 旧数据迁移向导 |
 | `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx` | 修改 | 风险源 Tab 替换为新层级组件 |
 | `frontend/src/pages/Enterprise/RiskAssessmentTab.tsx` | 修改 | 报告生成上下文适配新模型 |

 ---

 ## 任务 1：数据库迁移 DDL

 **文件：** `backend/db_migration_risk_overhaul.sql`

 - [ ] **步骤 1：编写完整 DDL**

 ```sql
 -- ============================================================
 -- 风险管理功能全面重构 DDL
 -- ============================================================

 -- 1. 风险评估方法配置表
 CREATE TABLE IF NOT EXISTS risk_assessment_methods (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     enterprise_id UUID REFERENCES enterprises(id) ON DELETE CASCADE,
     method_type VARCHAR(20) NOT NULL CHECK (method_type IN ('LS', 'LEC', 'COAL_LS', 'DIRECT')),
     name VARCHAR(100) NOT NULL,
     config JSONB NOT NULL DEFAULT '{}'::jsonb,
     is_active BOOLEAN NOT NULL DEFAULT true,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ram_enterprise ON risk_assessment_methods(enterprise_id);

 -- 2. 风险分区表
 CREATE TABLE IF NOT EXISTS risk_zones (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
     name VARCHAR(255) NOT NULL,
     description TEXT,
     sort_order INTEGER NOT NULL DEFAULT 0,
     floor_plan_polygon JSONB,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_rz_enterprise ON risk_zones(enterprise_id);

 -- 3. 风险分析对象表
 CREATE TABLE IF NOT EXISTS risk_objects (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
     zone_id UUID REFERENCES risk_zones(id) ON DELETE SET NULL,
     name VARCHAR(255) NOT NULL,
     category VARCHAR(100),
     location VARCHAR(500),
     location_x FLOAT,
     location_y FLOAT,
     description TEXT,
     image_url VARCHAR(500),
     is_risk_point BOOLEAN NOT NULL DEFAULT false,
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ro_enterprise ON risk_objects(enterprise_id);
 CREATE INDEX idx_ro_zone ON risk_objects(zone_id);

 -- 4. 风险分析单元表
 CREATE TABLE IF NOT EXISTS risk_units (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     object_id UUID NOT NULL REFERENCES risk_objects(id) ON DELETE CASCADE,
     name VARCHAR(255) NOT NULL,
     unit_type VARCHAR(50),
     description TEXT,
     location VARCHAR(500),
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ru_object ON risk_units(object_id);

 -- 5. 风险事件表
 CREATE TABLE IF NOT EXISTS risk_events (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     unit_id UUID REFERENCES risk_units(id) ON DELETE CASCADE,
     object_id UUID REFERENCES risk_objects(id) ON DELETE CASCADE,
     accident_type VARCHAR(100) NOT NULL,
     description TEXT,
     trigger_conditions TEXT,
     consequences TEXT,
     method_type VARCHAR(20) NOT NULL DEFAULT 'LS'
         CHECK (method_type IN ('LS', 'LEC', 'COAL_LS', 'DIRECT')),
     method_params JSONB NOT NULL DEFAULT '{}'::jsonb,
     risk_level VARCHAR(20),
     risk_score VARCHAR(50),
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     CONSTRAINT ck_event_parent CHECK (
         (unit_id IS NOT NULL AND object_id IS NULL)
         OR (unit_id IS NULL AND object_id IS NOT NULL)
     )
 );
 CREATE INDEX idx_re_unit ON risk_events(unit_id);
 CREATE INDEX idx_re_object ON risk_events(object_id);

 -- 6. 风险管控措施表
 CREATE TABLE IF NOT EXISTS risk_measures (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     event_id UUID NOT NULL REFERENCES risk_events(id) ON DELETE CASCADE,
     measure_category VARCHAR(50) NOT NULL
         CHECK (measure_category IN ('engineering', 'management', 'ppe', 'emergency')),
     measure_type VARCHAR(100),
     description TEXT NOT NULL,
     responsible_person VARCHAR(100),
     deadline DATE,
     check_items JSONB DEFAULT '[]'::jsonb,
     status VARCHAR(20) NOT NULL DEFAULT 'pending'
         CHECK (status IN ('pending', 'implemented', 'expired')),
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_rm_event ON risk_measures(event_id);

 -- 7. 旧 risk_sources 表增加 migrated 标记
 ALTER TABLE risk_sources ADD COLUMN IF NOT EXISTS migrated BOOLEAN NOT NULL DEFAULT false;

 -- 8. enterprises 表增加风险方法配置
 ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS risk_method_config JSONB DEFAULT '{}'::jsonb;

 -- 9. 预置系统级 LS 评估方法
 INSERT INTO risk_assessment_methods (id, enterprise_id, method_type, name, config)
 VALUES (
     gen_random_uuid(), NULL, 'LS', 'L×S 风险矩阵法（5 级）',
     '{
       "l_levels": [
         {"value": 1, "label": "极不可能", "desc": "有充分有效的防范控制监测保护措施，员工安全意识高，严格执行操作规程"},
         {"value": 2, "label": "不太可能", "desc": "危害一旦发生能及时发现，并定期进行监测，或现场有防范控制措施并能有效执行"},
         {"value": 3, "label": "可能", "desc": "没有保护措施，或未严格按操作程序执行，或危害的发生容易被发现"},
         {"value": 4, "label": "较可能", "desc": "危害的发生不容易被发现，现场没有检测系统，或控制措施未有效执行"},
         {"value": 5, "label": "极可能", "desc": "在现场没有采取防范监测保护控制措施，或危害的发生不能被发现"}
       ],
       "s_levels": [
         {"value": 1, "label": "很低", "desc": "轻微伤害，无财产损失，不影响运营"},
         {"value": 2, "label": "低", "desc": "轻微伤害，财产损失<1万，基本不影响运营"},
         {"value": 3, "label": "中", "desc": "人员轻伤，财产损失1-10万，短期影响运营"},
         {"value": 4, "label": "高", "desc": "人员重伤，财产损失10-100万，较长时间停运"},
         {"value": 5, "label": "很高", "desc": "人员死亡，财产损失>100万，长期停运或关闭"}
       ],
       "risk_thresholds": [
         {"min": 20, "max": 25, "level": "重大", "action": "立即整改", "deadline": "立即"},
         {"min": 15, "max": 16, "level": "较大", "action": "立即或近期整改", "deadline": "近期"},
         {"min": 9, "max": 12, "level": "一般", "action": "2年内治理", "deadline": "2年"},
         {"min": 1, "max": 8, "level": "低", "action": "有条件有经费时治理", "deadline": "有条件时"}
       ],
       "formula": "R = L × S",
       "l_range": [1, 5],
       "s_range": [1, 5]
     }'::jsonb
 );

 -- 10. 预置系统级 LEC 评价法
 INSERT INTO risk_assessment_methods (id, enterprise_id, method_type, name, config)
 VALUES (
     gen_random_uuid(), NULL, 'LEC', 'LEC 评价法（格雷厄姆-金尼法）',
     '{
       "l_levels": [
         {"value": 0.1, "label": "实际不可能"},
         {"value": 0.2, "label": "极不可能"},
         {"value": 0.5, "label": "很不可能"},
         {"value": 1, "label": "可能性小"},
         {"value": 3, "label": "可能但不经常"},
         {"value": 6, "label": "相当可能"},
         {"value": 10, "label": "完全可以预料"}
       ],
       "e_levels": [
         {"value": 0.5, "label": "非常罕见"},
         {"value": 1, "label": "每年几次"},
         {"value": 2, "label": "每月一次"},
         {"value": 3, "label": "每周一次"},
         {"value": 6, "label": "逐日"},
         {"value": 10, "label": "连续暴露"}
       ],
       "c_levels": [
         {"value": 1, "label": "引人注意"},
         {"value": 3, "label": "重大"},
         {"value": 7, "label": "严重"},
         {"value": 15, "label": "非常严重"},
         {"value": 40, "label": "灾难"},
         {"value": 100, "label": "大灾难"}
       ],
       "risk_thresholds": [
         {"min": 320, "max": 9999, "level": "重大", "action": "立即停止作业整改"},
         {"min": 160, "max": 319, "level": "较大", "action": "立即或近期整改"},
         {"min": 70, "max": 159, "level": "一般", "action": "限期整改"},
         {"min": 0, "max": 69, "level": "低", "action": "日常管理"}
       ],
       "formula": "D = L × E × C",
       "l_range": [0.1, 10],
       "e_range": [0.5, 10],
       "c_range": [1, 100]
     }'::jsonb
 );
 ```

 - [ ] **步骤 2：执行迁移验证**

 ```bash
 cd backend
 $env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan"
 python -c "
 import asyncio
 from app.database import engine, Base
 # 导入全部模型确保 create_all 能发现
 from app.models.enterprise import Enterprise, RiskSource
 from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure, RiskAssessmentMethod
 async def check():
     async with engine.begin() as conn:
         await conn.run_sync(Base.metadata.create_all)
     print('OK: all tables created')
 asyncio.run(check())
 "
 ```

 - [ ] **步骤 3：Commit**

 ```bash
 git add backend/db_migration_risk_overhaul.sql
 git commit -m "feat: risk management overhaul DDL — 6 new tables + method presets"
 ```

 ---

 ## 任务 2：后端 ORM 模型

 **文件：** `backend/app/models/risk_management.py`（新建）

 - [ ] **步骤 1：编写 6 个 ORM 模型**

 ```python
 from datetime import datetime
 from uuid import uuid4
 from typing import Optional
 from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, func, CheckConstraint
 from sqlalchemy.orm import Mapped, mapped_column, relationship
 from sqlalchemy.dialects.postgresql import UUID, JSONB
 from app.database import Base


 class RiskAssessmentMethod(Base):
     __tablename__ = "risk_assessment_methods"

     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     enterprise_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=True, index=True)
     method_type: Mapped[str] = mapped_column(String(20), nullable=False)
     name: Mapped[str] = mapped_column(String(100), nullable=False)
     config: Mapped[dict] = mapped_column(JSONB, default=dict)
     is_active: Mapped[bool] = mapped_column(Boolean, default=True)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


 class RiskZone(Base):
     __tablename__ = "risk_zones"

     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
     name: Mapped[str] = mapped_column(String(255), nullable=False)
     description: Mapped[Optional[str]] = mapped_column(Text)
     sort_order: Mapped[int] = mapped_column(Integer, default=0)
     floor_plan_polygon: Mapped[Optional[dict]] = mapped_column(JSONB)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

     objects = relationship("RiskObject", back_populates="zone", cascade="all, delete-orphan", lazy="selectin")


 class RiskObject(Base):
     __tablename__ = "risk_objects"

     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
     zone_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_zones.id", ondelete="SET NULL"), nullable=True)
     name: Mapped[str] = mapped_column(String(255), nullable=False)
     category: Mapped[Optional[str]] = mapped_column(String(100))
     location: Mapped[Optional[str]] = mapped_column(String(500))
     location_x: Mapped[Optional[float]] = mapped_column(Float)
     location_y: Mapped[Optional[float]] = mapped_column(Float)
     description: Mapped[Optional[str]] = mapped_column(Text)
     image_url: Mapped[Optional[str]] = mapped_column(String(500))
     is_risk_point: Mapped[bool] = mapped_column(Boolean, default=False)
     sort_order: Mapped[int] = mapped_column(Integer, default=0)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

     zone = relationship("RiskZone", back_populates="objects", lazy="selectin")
     units = relationship("RiskUnit", back_populates="object", cascade="all, delete-orphan", lazy="selectin")
     events = relationship("RiskEvent", back_populates="object", cascade="all, delete-orphan", lazy="selectin",
                           primaryjoin="RiskObject.id==RiskEvent.object_id")


 class RiskUnit(Base):
     __tablename__ = "risk_units"

     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     object_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="CASCADE"), nullable=False, index=True)
     name: Mapped[str] = mapped_column(String(255), nullable=False)
     unit_type: Mapped[Optional[str]] = mapped_column(String(50))
     description: Mapped[Optional[str]] = mapped_column(Text)
     location: Mapped[Optional[str]] = mapped_column(String(500))
     sort_order: Mapped[int] = mapped_column(Integer, default=0)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

     object = relationship("RiskObject", back_populates="units", lazy="selectin")
     events = relationship("RiskEvent", back_populates="unit", cascade="all, delete-orphan", lazy="selectin")


 class RiskEvent(Base):
     __tablename__ = "risk_events"

     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     unit_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_units.id", ondelete="CASCADE"), nullable=True)
     object_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="CASCADE"), nullable=True)
     accident_type: Mapped[str] = mapped_column(String(100), nullable=False)
     description: Mapped[Optional[str]] = mapped_column(Text)
     trigger_conditions: Mapped[Optional[str]] = mapped_column(Text)
     consequences: Mapped[Optional[str]] = mapped_column(Text)
     method_type: Mapped[str] = mapped_column(String(20), default="LS")
     method_params: Mapped[dict] = mapped_column(JSONB, default=dict)
     risk_level: Mapped[Optional[str]] = mapped_column(String(20))
     risk_score: Mapped[Optional[str]] = mapped_column(String(50))
     sort_order: Mapped[int] = mapped_column(Integer, default=0)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

     unit = relationship("RiskUnit", back_populates="events", lazy="selectin")
     object = relationship("RiskObject", back_populates="events", lazy="selectin",
                           primaryjoin="RiskEvent.object_id==RiskObject.id")
     measures = relationship("RiskMeasure", back_populates="event", cascade="all, delete-orphan", lazy="selectin")


 class RiskMeasure(Base):
     __tablename__ = "risk_measures"

     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_events.id", ondelete="CASCADE"), nullable=False, index=True)
     measure_category: Mapped[str] = mapped_column(String(50), nullable=False)
     measure_type: Mapped[Optional[str]] = mapped_column(String(100))
     description: Mapped[str] = mapped_column(Text, nullable=False)
     responsible_person: Mapped[Optional[str]] = mapped_column(String(100))
     deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
     check_items: Mapped[list] = mapped_column(JSONB, default=list)
     status: Mapped[str] = mapped_column(String(20), default="pending")
     sort_order: Mapped[int] = mapped_column(Integer, default=0)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

     event = relationship("RiskEvent", back_populates="measures", lazy="selectin")
 ```

 - [ ] **步骤 2：修改 Enterprise 模型增加 risk_method_config 字段**

 在 `backend/app/models/enterprise.py` 的 Enterprise 类中，`surrounding_info` 字段之后添加：

 ```python
 risk_method_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
 ```

 - [ ] **步骤 3：验证模型可导入**

 ```bash
 cd backend
 python -c "from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure, RiskAssessmentMethod; print('OK')"
 ```

 - [ ] **步骤 4：Commit**

 ```bash
 git add backend/app/models/risk_management.py backend/app/models/enterprise.py
 git commit -m "feat: risk management ORM models — 6 new tables + enterprise.risk_method_config"
 ```

 ---

 ## 任务 3：后端 Pydantic Schema

 **文件：** `backend/app/schemas/risk_management.py`（新建）

 - [ ] **步骤 1：编写完整 Schema**

 ```python
 from datetime import datetime, date
 from typing import Optional
 from pydantic import BaseModel, field_validator
 from app.schemas.common import DatetimeStr


 # ── RiskAssessmentMethod ──

 class MethodConfig(BaseModel):
     l_levels: list[dict] = []
     s_levels: list[dict] = []
     risk_thresholds: list[dict] = []
     formula: str = "R = L × S"
     l_range: list[float] = [1, 5]
     s_range: list[float] = [1, 5]

 class MethodCreate(BaseModel):
     method_type: str
     name: str
     config: dict = {}

 class MethodResponse(BaseModel):
     id: str
     enterprise_id: str | None
     method_type: str
     name: str
     config: dict
     is_active: bool
     created_at: DatetimeStr
     model_config = {"from_attributes": True}


 # ── RiskZone ──

 class RiskZoneCreate(BaseModel):
     name: str
     description: str | None = None
     sort_order: int = 0
     floor_plan_polygon: dict | None = None

 class RiskZoneUpdate(BaseModel):
     name: str | None = None
     description: str | None = None
     sort_order: int | None = None
     floor_plan_polygon: dict | None = None

 class RiskZoneResponse(BaseModel):
     id: str
     enterprise_id: str
     name: str
     description: str | None
     sort_order: int
     floor_plan_polygon: dict | None
     created_at: DatetimeStr
     object_count: int = 0
     model_config = {"from_attributes": True}


 # ── RiskObject ──

 class RiskObjectCreate(BaseModel):
     zone_id: str | None = None
     name: str
     category: str | None = None
     location: str | None = None
     location_x: float | None = None
     location_y: float | None = None
     description: str | None = None
     image_url: str | None = None
     is_risk_point: bool = False
     sort_order: int = 0

 class RiskObjectUpdate(BaseModel):
     zone_id: str | None = None
     name: str | None = None
     category: str | None = None
     location: str | None = None
     location_x: float | None = None
     location_y: float | None = None
     description: str | None = None
     image_url: str | None = None
     is_risk_point: bool | None = None
     sort_order: int | None = None

 class RiskObjectResponse(BaseModel):
     id: str
     enterprise_id: str
     zone_id: str | None
     name: str
     category: str | None
     location: str | None
     location_x: float | None
     location_y: float | None
     description: str | None
     image_url: str | None
     is_risk_point: bool
     sort_order: int
     created_at: DatetimeStr
     unit_count: int = 0
     model_config = {"from_attributes": True}


 # ── RiskUnit ──

 class RiskUnitCreate(BaseModel):
     object_id: str
     name: str
     unit_type: str | None = None
     description: str | None = None
     location: str | None = None
     sort_order: int = 0

 class RiskUnitUpdate(BaseModel):
     name: str | None = None
     unit_type: str | None = None
     description: str | None = None
     location: str | None = None
     sort_order: int | None = None

 class RiskUnitResponse(BaseModel):
     id: str
     object_id: str
     name: str
     unit_type: str | None
     description: str | None
     location: str | None
     sort_order: int
     created_at: DatetimeStr
     event_count: int = 0
     model_config = {"from_attributes": True}


 # ── RiskEvent ──

 class RiskEventCreate(BaseModel):
     unit_id: str | None = None
     object_id: str | None = None
     accident_type: str
     description: str | None = None
     trigger_conditions: str | None = None
     consequences: str | None = None
     method_type: str = "LS"
     method_params: dict = {}

     @field_validator("unit_id", "object_id")
     @classmethod
     def check_parent(cls, v, info):
         return v

 class RiskEventUpdate(BaseModel):
     accident_type: str | None = None
     description: str | None = None
     trigger_conditions: str | None = None
     consequences: str | None = None
     method_type: str | None = None
     method_params: dict | None = None

 class RiskEventResponse(BaseModel):
     id: str
     unit_id: str | None
     object_id: str | None
     accident_type: str
     description: str | None
     trigger_conditions: str | None
     consequences: str | None
     method_type: str
     method_params: dict
     risk_level: str | None
     risk_score: str | None
     sort_order: int
     created_at: DatetimeStr
     measure_count: int = 0
     model_config = {"from_attributes": True}


 # ── RiskMeasure ──

 class CheckItem(BaseModel):
     name: str
     standard: str = ""
     frequency: str = ""

 class RiskMeasureCreate(BaseModel):
     event_id: str
     measure_category: str
     measure_type: str | None = None
     description: str
     responsible_person: str | None = None
     deadline: date | None = None
     check_items: list[dict] = []
     sort_order: int = 0

 class RiskMeasureUpdate(BaseModel):
     measure_category: str | None = None
     measure_type: str | None = None
     description: str | None = None
     responsible_person: str | None = None
     deadline: date | None = None
     check_items: list[dict] | None = None
     status: str | None = None
     sort_order: int | None = None

 class RiskMeasureResponse(BaseModel):
     id: str
     event_id: str
     measure_category: str
     measure_type: str | None
     description: str
     responsible_person: str | None
     deadline: date | None
     check_items: list[dict]
     status: str
     sort_order: int
     created_at: DatetimeStr
     model_config = {"from_attributes": True}


 # ── 树状层级响应（供前端一次性加载全层级） ──

 class HierarchyEventResponse(BaseModel):
     id: str
     accident_type: str
     description: str | None
     risk_level: str | None
     risk_score: str | None
     method_type: str
     method_params: dict
     measures: list[RiskMeasureResponse] = []
     model_config = {"from_attributes": True}

 class HierarchyUnitResponse(BaseModel):
     id: str
     name: str
     unit_type: str | None
     description: str | None
     events: list[HierarchyEventResponse] = []
     model_config = {"from_attributes": True}

 class HierarchyObjectResponse(BaseModel):
     id: str
     name: str
     category: str | None
     is_risk_point: bool
     units: list[HierarchyUnitResponse] = []
     events: list[HierarchyEventResponse] = []
     model_config = {"from_attributes": True}

 class HierarchyZoneResponse(BaseModel):
     id: str
     name: str
     description: str | None
     objects: list[HierarchyObjectResponse] = []
     model_config = {"from_attributes": True}


 # ── 迁移相关 ──

 class MigrationPreviewItem(BaseModel):
     source_id: str
     source_name: str
     suggested_zone: str = ""
     suggested_object: str = ""
     suggested_events: list[dict] = []

 class MigrationPreviewResponse(BaseModel):
     items: list[MigrationPreviewItem]
     total: int

 class MigrationExecuteRequest(BaseModel):
     mappings: list[dict]
 ```

 - [ ] **步骤 2：Commit**

 ```bash
 git add backend/app/schemas/risk_management.py
 git commit -m "feat: risk management Pydantic schemas — all 6 entities + hierarchy tree"
 ```

 ---

 ## 任务 4：风险计算方法引擎

 **文件：** `backend/app/services/risk_method_engine.py`（新建）

 - [ ] **步骤 1：编写多方法计算引擎**

 ```python
 """风险评估多方法计算引擎。

支持 LS 矩阵、LEC 评价法、煤矿 LS 矩阵、直接判定法。
"""
 from typing import Optional
 from dataclasses import dataclass


 @dataclass
 class RiskResult:
     risk_level: str         # 重大/较大/一般/低
     risk_score: str         # R=20 / D=240 等
     action: str             # 整改建议
     deadline: str           # 整改期限


 def compute_risk(method_type: str, params: dict, config: dict | None = None) -> RiskResult:
     if method_type == "DIRECT":
         level = params.get("risk_level", "一般")
         return RiskResult(risk_level=level, risk_score="-", action=level, deadline="按需")

     thresholds = (config or {}).get("risk_thresholds", [])

     if method_type == "LS":
         l = float(params.get("l", 3))
         s = float(params.get("s", 3))
         r = int(l * s)
         score_str = f"R={r}"

     elif method_type == "LEC":
         l = float(params.get("l", 1))
         e = float(params.get("e", 1))
         c = float(params.get("c", 1))
         r = int(l * e * c)
         score_str = f"D={r}"

     elif method_type == "COAL_LS":
         l = float(params.get("l", 3))
         s = float(params.get("s", 3))
         r = int(l * s)
         score_str = f"R={r}"
         # 煤矿行业特有判定表
         coal_thresholds = [
             {"min": 20, "max": 25, "level": "重大", "action": "立即停产整改", "deadline": "立即"},
             {"min": 15, "max": 19, "level": "较大", "action": "限期停产整改", "deadline": "1个月"},
             {"min": 10, "max": 14, "level": "一般", "action": "限期整改", "deadline": "3个月"},
             {"min": 1, "max": 9, "level": "低", "action": "加强日常管理", "deadline": "持续"},
         ]
         thresholds = coal_thresholds
     else:
         return RiskResult(risk_level="一般", risk_score="-", action="未知方法", deadline="N/A")

     # 查阈值表判定等级
     for t in thresholds:
         if t["min"] <= r <= t["max"]:
             return RiskResult(
                 risk_level=t["level"],
                 risk_score=score_str,
                 action=t.get("action", ""),
                 deadline=t.get("deadline", ""),
             )

     return RiskResult(risk_level="低", risk_score=score_str, action="日常管理", deadline="持续")
 ```

 - [ ] **步骤 2：编写方法配置查询辅助函数**

 ```python
 async def get_active_method(db, enterprise_id: str, method_type: str = "LS") -> dict | None:
     """获取企业或系统级活跃方法配置。"""
     from sqlalchemy import select
     from app.models.risk_management import RiskAssessmentMethod

     # 优先企业级
     result = await db.execute(
         select(RiskAssessmentMethod).where(
             RiskAssessmentMethod.enterprise_id == enterprise_id,
             RiskAssessmentMethod.method_type == method_type,
             RiskAssessmentMethod.is_active == True,
         )
     )
     m = result.scalar_one_or_none()
     if m:
         return m.config

     # 回退系统级
     result = await db.execute(
         select(RiskAssessmentMethod).where(
             RiskAssessmentMethod.enterprise_id.is_(None),
             RiskAssessmentMethod.method_type == method_type,
             RiskAssessmentMethod.is_active == True,
         )
     )
     m = result.scalar_one_or_none()
     return m.config if m else None
 ```

 - [ ] **步骤 3：Commit**

 ```bash
 git add backend/app/services/risk_method_engine.py
 git commit -m "feat: risk method compute engine — LS/LEC/COAL_LS/DIRECT"
 ```

 ---

 ## 任务 5：后端全层级 CRUD 路由

 **文件：** `backend/app/routers/risk_management.py`（新建）

 该文件包含约 30 个端点，覆盖 6 个实体 + 1 个树状全量查询 + 旧数据迁移 API。由于篇幅较长，以下列出所有端点签名和关键逻辑，完整代码在实现时展开。

 - [ ] **步骤 1：编写路由框架和辅助函数**

 ```python
 import json
 from fastapi import APIRouter, Depends, HTTPException, Query
 from sqlalchemy.ext.asyncio import AsyncSession
 from sqlalchemy import select, func
 from app.database import get_db
 from app.dependencies import get_current_user
 from app.models.user import User
 from app.models.enterprise import Enterprise
 from app.models.risk_management import (
     RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure, RiskAssessmentMethod,
 )
 from app.schemas.risk_management import (
     MethodCreate, MethodResponse,
     RiskZoneCreate, RiskZoneUpdate, RiskZoneResponse,
     RiskObjectCreate, RiskObjectUpdate, RiskObjectResponse,
     RiskUnitCreate, RiskUnitUpdate, RiskUnitResponse,
     RiskEventCreate, RiskEventUpdate, RiskEventResponse,
     RiskMeasureCreate, RiskMeasureUpdate, RiskMeasureResponse,
     HierarchyZoneResponse,
     MigrationPreviewResponse, MigrationExecuteRequest,
 )
 from app.schemas.common import ApiResponse
 from app.services.risk_method_engine import compute_risk, get_active_method

 router = APIRouter(prefix="/enterprises/{enterprise_id}/risk-management", tags=["Risk Management"])


 async def _get_enterprise(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
     result = await db.execute(
         select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user_id)
     )
     ent = result.scalar_one_or_none()
     if not ent:
         raise HTTPException(404, "企业不存在")
     return ent
 ```

 - [ ] **步骤 2：Method 端点（2 个）**

 ```python
 @router.get("/methods", response_model=ApiResponse[list[MethodResponse]])
 async def list_methods(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(
         select(RiskAssessmentMethod).where(
             (RiskAssessmentMethod.enterprise_id == enterprise_id) |
             (RiskAssessmentMethod.enterprise_id.is_(None))
         ).where(RiskAssessmentMethod.is_active == True)
     )
     methods = result.scalars().all()
     return ApiResponse(data=[MethodResponse.model_validate(m) for m in methods])
 ```

 - [ ] **步骤 3：Zone 端点（5 个）**

 `GET /zones` — 列表 + 对象计数
 `POST /zones` — 创建
 `GET /zones/{zone_id}` — 单个
 `PUT /zones/{zone_id}` — 更新
 `DELETE /zones/{zone_id}` — 删除

 - [ ] **步骤 4：Object 端点（5 个）**

 `GET /objects?zone_id=` — 列表（可按分区筛选）+ 单元计数
 `POST /objects` — 创建（支持上传图片到 uploads 目录）
 `GET /objects/{object_id}` — 单个
 `PUT /objects/{object_id}` — 更新
 `DELETE /objects/{object_id}` — 删除

 - [ ] **步骤 5：Unit 端点（5 个）**

 `GET /objects/{object_id}/units` — 列表 + 事件计数
 `POST /objects/{object_id}/units` — 创建
 `GET /objects/{object_id}/units/{unit_id}` — 单个
 `PUT /objects/{object_id}/units/{unit_id}` — 更新
 `DELETE /objects/{object_id}/units/{unit_id}` — 删除

 - [ ] **步骤 6：Event 端点（5 个）**

 创建时自动调用 `compute_risk()` 计算等级：

 ```python
 @router.post("/units/{unit_id}/events", response_model=ApiResponse[RiskEventResponse], status_code=201)
 async def create_event(unit_id: str, body: RiskEventCreate, ...):
     # 从企业配置获取方法
     config = await get_active_method(db, enterprise_id, body.method_type)
     result = compute_risk(body.method_type, body.method_params, config)
     event = RiskEvent(
         unit_id=unit_id, method_type=body.method_type,
         method_params=body.method_params,
         risk_level=result.risk_level,
         risk_score=result.risk_score,
         ...
     )
     db.add(event)
     await db.commit()
 ```

 `/GET /units/{unit_id}/events` — 列表
 `/POST /units/{unit_id}/events` — 创建 + 自动评级
 `/GET /events/{event_id}` — 单个
 `/PUT /events/{event_id}` — 更新（自动重算 risk_level）
 `/DELETE /events/{event_id}` — 删除
 `/POST /events/{event_id}/recalc` — 手动重算等级

 - [ ] **步骤 7：Measure 端点（5 个）**

 `GET /events/{event_id}/measures` — 列表
 `POST /events/{event_id}/measures` — 创建
 `GET /events/{event_id}/measures/{measure_id}` — 单个
 `PUT /events/{event_id}/measures/{measure_id}` — 更新（状态变更）
 `DELETE /events/{event_id}/measures/{measure_id}` — 删除

 - [ ] **步骤 8：全层级树状查询端点（1 个）**

 ```python
 @router.get("/hierarchy", response_model=ApiResponse[list[HierarchyZoneResponse]])
 async def get_full_hierarchy(enterprise_id: str, ...):
     """一次性返回企业全部风险管控层级树。"""
     zones_result = await db.execute(
         select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
                          .order_by(RiskZone.sort_order)
     )
     zones = zones_result.scalars().all()
     # SQLAlchemy selectin 预加载关联数据
     return ApiResponse(data=[HierarchyZoneResponse.model_validate(z) for z in zones])
 ```

 - [ ] **步骤 9：Commit**

 ```bash
 git add backend/app/routers/risk_management.py
 git commit -m "feat: risk management CRUD router — ~30 endpoints + hierarchy tree"
 ```

 ---

 ## 任务 6：后端集成 — 上下文构建 + 报告生成适配

 - [ ] **步骤 1：新建 risk_context_builder.py**

 **文件：** `backend/app/services/risk_context_builder.py`（新建）

 ```python
 """风险分级管控上下文构建器。

替代旧的 build_risk_assessment_context()，消费新的五层级结构。
"""
 from sqlalchemy.ext.asyncio import AsyncSession
 from sqlalchemy import select
 from app.models.enterprise import Enterprise
 from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure


 async def build_risk_management_context(enterprise_id: str, db: AsyncSession) -> dict:
     ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
     if not ent:
         raise ValueError("企业不存在")

     zones_result = await db.execute(
         select(RiskZone).where(RiskZone.enterprise_id == enterprise_id).order_by(RiskZone.sort_order)
     )
     zones = zones_result.scalars().all()

     risk_sources_list = []
     for zone in zones:
         for obj in zone.objects:
             for unit in obj.units:
                 for event in unit.events:
                     risk_sources_list.append({
                         "zone": zone.name,
                         "object": obj.name,
                         "unit": unit.name,
                         "accident_type": event.accident_type,
                         "risk_level": event.risk_level,
                         "risk_score": event.risk_score,
                         "description": event.description,
                         "triggers": event.trigger_conditions,
                         "consequences": event.consequences,
                         "measures": [
                             {"category": m.measure_category, "description": m.description}
                             for m in event.measures
                         ],
                     })
             for event in obj.events:
                 risk_sources_list.append({
                     "zone": zone.name,
                     "object": obj.name,
                     "unit": None,
                     "accident_type": event.accident_type,
                     "risk_level": event.risk_level,
                     "risk_score": event.risk_score,
                     "description": event.description,
                     "measures": [
                         {"category": m.measure_category, "description": m.description}
                         for m in event.measures
                     ],
                 })

     return {
         "enterprise": {
             "name": ent.name, "industry": ent.industry, "address": ent.address,
             "employee_count": ent.employee_count, "business_scope": ent.business_scope,
             "building_overview": ent.building_overview,
             "fire_protection_summary": ent.fire_protection_summary,
             "special_equipment_detail": ent.special_equipment_detail,
             "main_equipment_list": ent.main_equipment_list,
             "natural_conditions": ent.natural_conditions,
             "hazardous_chemicals": ent.hazardous_chemicals,
         },
         "risk_sources": risk_sources_list,
         "zone_count": len(zones),
         "total_events": sum(
             len(obj.units) + len([e for u in obj.units for e in u.events]) + len(obj.events)
             for zone in zones for obj in zone.objects
         ),
     }
 ```

 - [ ] **步骤 2：修改 risk_assessment.py 路由**

 **文件：** `backend/app/routers/risk_assessment.py`

 将 `build_risk_assessment_context` 导入改为新的 `build_risk_management_context`：

 ```python
 # 替换：
 # from app.services.risk_assessment_service import build_risk_assessment_context
 # 为：
 from app.services.risk_context_builder import build_risk_management_context
 ```

 `POST /generate` 端点中的数据检查逻辑从 `risk_sources` 改为 `risk_events`：

 ```python
 # 替换 risk_sources 计数：
 event_count = (await db.execute(
     select(RiskEvent).join(RiskUnit).join(RiskObject).join(RiskZone)
     .where(RiskZone.enterprise_id == enterprise_id)
 )).scalars().all()
 if len(event_count) == 0:
     raise HTTPException(400, "请先完成风险分级管控数据录入")
 ```

 - [ ] **步骤 3：修改 generation.py**

 **文件：** `backend/app/routers/generation.py`

 在 `_collect_enterprise_data` 或预案生成上下文构建中，将 `risk_sources` 查询替换为新的层级结构上下文：

 ```python
 # 替换旧的 risk_sources 查询，在构建 enterpise_data 时：
 from app.services.risk_context_builder import build_risk_management_context
 rm_context = await build_risk_management_context(enterprise_id, db)
 enterprise_data["risk_sources"] = rm_context["risk_sources"]
 ```

 - [ ] **步骤 4：修改 enterprises.py**

 **文件：** `backend/app/routers/enterprises.py`

 EnterpriseResponse schema 增加 `risk_method_config` 字段，并在 `_build_response` 中填充。

 **文件：** `backend/app/schemas/enterprise.py`

 ```python
 # EnterpriseResponse 增加：
 risk_method_config: dict | None = None
 ```

 - [ ] **步骤 5：修改 main.py 注册新路由**

 **文件：** `backend/app/main.py`

 ```python
 from app.routers import risk_management
 app.include_router(risk_management.router, prefix="/api/v1")
 ```

 - [ ] **步骤 6：Commit**

 ```bash
 git add backend/app/services/risk_context_builder.py
 git add backend/app/routers/risk_assessment.py backend/app/routers/generation.py
 git add backend/app/routers/enterprises.py backend/app/schemas/enterprise.py
 git add backend/app/main.py
 git commit -m "feat: wire risk management context into report generation & plan generation"
 ```

 ---

 ## 任务 7：前端类型定义 + API 服务层

 - [ ] **步骤 1：编写 TypeScript 类型**

 **文件：** `frontend/src/types/riskManagement.ts`（新建）

 ```typescript
 // ── Method ──
 export type MethodType = "LS" | "LEC" | "COAL_LS" | "DIRECT";

 export interface MethodConfig {
   l_levels: { value: number; label: string; desc: string }[];
   s_levels?: { value: number; label: string; desc: string }[];
   e_levels?: { value: number; label: string }[];
   c_levels?: { value: number; label: string }[];
   risk_thresholds: { min: number; max: number; level: string; action: string; deadline: string }[];
   formula: string;
   l_range: number[];
   s_range: number[];
 }

 export interface RiskAssessmentMethod {
   id: string;
   enterprise_id: string | null;
   method_type: MethodType;
   name: string;
   config: MethodConfig;
   is_active: boolean;
 }

 // ── Zone ──
 export interface RiskZone {
   id: string;
   enterprise_id: string;
   name: string;
   description: string | null;
   sort_order: number;
   floor_plan_polygon: { points: { x: number; y: number }[] } | null;
   created_at: string;
   object_count: number;
 }

 export interface RiskZoneCreate {
   name: string;
   description?: string;
   floor_plan_polygon?: { points: { x: number; y: number }[] };
 }

 // ── Object ──
 export interface RiskObject {
   id: string;
   enterprise_id: string;
   zone_id: string | null;
   name: string;
   category: string | null;
   location: string | null;
   location_x: number | null;
   location_y: number | null;
   description: string | null;
   image_url: string | null;
   is_risk_point: boolean;
   sort_order: number;
   created_at: string;
   unit_count: number;
 }

 export interface RiskObjectCreate {
   zone_id?: string;
   name: string;
   category?: string;
   location?: string;
   location_x?: number;
   location_y?: number;
   description?: string;
   image_url?: string;
   is_risk_point?: boolean;
 }

 // ── Unit ──
 export interface RiskUnit {
   id: string;
   object_id: string;
   name: string;
   unit_type: string | null;
   description: string | null;
   location: string | null;
   sort_order: number;
   created_at: string;
   event_count: number;
 }

 export interface RiskUnitCreate {
   object_id: string;
   name: string;
   unit_type?: string;
   description?: string;
   location?: string;
 }

 // ── Event ──
 export interface RiskEvent {
   id: string;
   unit_id: string | null;
   object_id: string | null;
   accident_type: string;
   description: string | null;
   trigger_conditions: string | null;
   consequences: string | null;
   method_type: MethodType;
   method_params: Record<string, number>;
   risk_level: string | null;
   risk_score: string | null;
   sort_order: number;
   created_at: string;
   measure_count: number;
 }

 export interface RiskEventCreate {
   unit_id?: string;
   object_id?: string;
   accident_type: string;
   description?: string;
   trigger_conditions?: string;
   consequences?: string;
   method_type?: MethodType;
   method_params?: Record<string, number>;
 }

 // ── Measure ──
 export interface CheckItem {
   name: string;
   standard: string;
   frequency: string;
 }

 export interface RiskMeasure {
   id: string;
   event_id: string;
   measure_category: "engineering" | "management" | "ppe" | "emergency";
   measure_type: string | null;
   description: string;
   responsible_person: string | null;
   deadline: string | null;
   check_items: CheckItem[];
   status: "pending" | "implemented" | "expired";
   sort_order: number;
   created_at: string;
 }

 export interface RiskMeasureCreate {
   event_id: string;
   measure_category: string;
   measure_type?: string;
   description: string;
   responsible_person?: string;
   deadline?: string;
   check_items?: CheckItem[];
 }

 // ── Hierarchy (tree) ──
 export interface HierarchyEvent extends RiskEvent {
   measures: RiskMeasure[];
 }

 export interface HierarchyUnit extends RiskUnit {
   events: HierarchyEvent[];
 }

 export interface HierarchyObject extends RiskObject {
   units: HierarchyUnit[];
   events: HierarchyEvent[];
 }

 export interface HierarchyZone extends RiskZone {
   objects: HierarchyObject[];
 }
 ```

 - [ ] **步骤 2：编写 API 服务**

 **文件：** `frontend/src/services/riskManagementService.ts`（新建）

 对应后端每个端点创建函数（约 30 个），使用 `api` 实例调用。示例如下（完整实现时展开所有端点）：

 ```typescript
 import api from "./api";
 import type { ApiResponse } from "@/types/common";
 import type {
   RiskAssessmentMethod, RiskZone, RiskZoneCreate,
   RiskObject, RiskObjectCreate,
   RiskUnit, RiskUnitCreate,
   RiskEvent, RiskEventCreate,
   RiskMeasure, RiskMeasureCreate,
   HierarchyZone,
 } from "@/types/riskManagement";

 const base = (eid: string) => `/enterprises/${eid}/risk-management`;

 // Methods
 export function listMethods(eid: string) {
   return api.get<ApiResponse<RiskAssessmentMethod[]>>(`${base(eid)}/methods`).then(r => r.data.data);
 }

 // Zones
 export function listZones(eid: string) {
   return api.get<ApiResponse<RiskZone[]>>(`${base(eid)}/zones`).then(r => r.data.data);
 }
 export function createZone(eid: string, data: RiskZoneCreate) {
   return api.post<ApiResponse<RiskZone>>(`${base(eid)}/zones`, data).then(r => r.data.data);
 }
 export function updateZone(eid: string, zoneId: string, data: Partial<RiskZoneCreate>) {
   return api.put<ApiResponse<RiskZone>>(`${base(eid)}/zones/${zoneId}`, data).then(r => r.data.data);
 }
 export function deleteZone(eid: string, zoneId: string) {
   return api.delete(`${base(eid)}/zones/${zoneId}`);
 }

 // Objects
 export { /* listObjects, createObject, updateObject, deleteObject */ };
 // Units
 export { /* listUnits, createUnit, updateUnit, deleteUnit */ };
 // Events
 export { /* listEvents, createEvent, updateEvent, deleteEvent, recalcEvent */ };
 // Measures
 export { /* listMeasures, createMeasure, updateMeasure, deleteMeasure */ };
 // Hierarchy
 export function getFullHierarchy(eid: string) {
   return api.get<ApiResponse<HierarchyZone[]>>(`${base(eid)}/hierarchy`).then(r => r.data.data);
 }
 // Upload image for risk point
 export function uploadRiskPointImage(eid: string, file: File) {
   const fd = new FormData();
   fd.append("file", file);
   return api.post<ApiResponse<{ url: string }>>("/api/v1/upload", fd).then(r => r.data.data);
 }
 ```

 - [ ] **步骤 3：编写前端方法计算工具**

 **文件：** `frontend/src/utils/riskMethodEngine.ts`（新建）

 ```typescript
 export interface RiskResult {
   riskLevel: string;
   riskScore: string;
   action: string;
 }

 export function computeRiskLS(l: number, s: number): RiskResult {
   const r = l * s;
   const score = `R=${r}`;
   if (r >= 20) return { riskLevel: "重大", riskScore: score, action: "立即整改" };
   if (r >= 15) return { riskLevel: "较大", riskScore: score, action: "立即或近期整改" };
   if (r >= 9) return { riskLevel: "一般", riskScore: score, action: "2年内治理" };
   return { riskLevel: "低", riskScore: score, action: "日常管理" };
 }

 export function computeRiskLEC(l: number, e: number, c: number): RiskResult {
   const d = Math.round(l * e * c);
   const score = `D=${d}`;
   if (d >= 320) return { riskLevel: "重大", riskScore: score, action: "立即停止作业整改" };
   if (d >= 160) return { riskLevel: "较大", riskScore: score, action: "立即或近期整改" };
   if (d >= 70) return { riskLevel: "一般", riskScore: score, action: "限期整改" };
   return { riskLevel: "低", riskScore: score, action: "日常管理" };
 }

 export const RISK_LEVEL_COLORS: Record<string, string> = {
   重大: "#ff4d4f", 较大: "#fa8c16", 一般: "#fadb14", 低: "#52c41a",
 };

 export const MEASURE_CATEGORY_LABELS: Record<string, string> = {
   engineering: "工程技术", management: "管理措施", ppe: "个体防护", emergency: "应急处置",
 };

 export const ACCIDENT_TYPES = [
   "物体打击", "车辆伤害", "机械伤害", "起重伤害", "触电", "淹溺", "灼烫",
   "火灾", "高处坠落", "坍塌", "锅炉爆炸", "容器爆炸", "其他爆炸",
   "中毒和窒息", "其他伤害",
 ];
 ```

 - [ ] **步骤 4：Commit**

 ```bash
 git add frontend/src/types/riskManagement.ts
 git add frontend/src/services/riskManagementService.ts
 git add frontend/src/utils/riskMethodEngine.ts
 git commit -m "feat: frontend risk management types + services + method engine"
 ```

 ---

 ## 任务 8：前端组件 — 方法配置 + 层级树

 - [ ] **步骤 1：RiskMethodConfigPanel 组件**

 **文件：** `frontend/src/components/enterprise/RiskMethodConfigPanel.tsx`（新建）

 功能：展示企业或系统预置的评估方法列表。每个方法卡片显示名称、公式、阈值表。支持选择激活方法。
 使用 Ant Design `Card`、`Table`、`Tag` 组件。

 - [ ] **步骤 2：RiskHierarchyTree 组件**

 **文件：** `frontend/src/components/enterprise/RiskHierarchyTree.tsx`（新建）

 功能：五层层级树状结构，使用 Ant Design `Tree` 组件。一次性从 `/hierarchy` 端点加载全量数据。

 树节点结构：
 ```
 🏭 区域：储罐区 (3 对象)
   ├─ 📦 对象：1号储罐 [风险点] (2 单元)
   │   ├─ ⚙ 单元：罐体 (1 事件)
   │   │   └─ ⚠ 事件：储罐泄漏 — 重大 R=20 (2 措施)
   │   │       ├─ 🛡 工程：可燃气体报警 — 已实施
   │   │       └─ 🛡 管理：每日巡检 — 待实施
   │   └─ ⚙ 单元：输送泵 (1 事件)
   └─ 📦 对象：装卸平台 (1 单元)
 ```

 树节点右键菜单（或行内操作按钮）提供：添加子节点、编辑、删除、上移/下移。

 - [ ] **步骤 3：Commit**

 ```bash
 git add frontend/src/components/enterprise/RiskMethodConfigPanel.tsx
 git add frontend/src/components/enterprise/RiskHierarchyTree.tsx
 git commit -m "feat: RiskMethodConfigPanel + RiskHierarchyTree components"
 ```

 ---

 ## 任务 9：前端组件 — 各层级表单（5 个）

 - [ ] **步骤 1：RiskZoneForm**

 **文件：** `frontend/src/components/enterprise/RiskZoneForm.tsx`（新建）

 Modal 表单，字段：名称、描述、排序。如有厂区平面图，显示 FloorPlanPicker 供用户圈选多边形区域。

 - [ ] **步骤 2：RiskObjectForm**

 **文件：** `frontend/src/components/enterprise/RiskObjectForm.tsx`（新建）

 Modal 表单，字段：名称、所属分区（Select）、类别、位置、位置坐标（FloorPlanPicker）、描述、图片上传、是否风险点（Switch）。当 `is_risk_point` 为 true 时展开图片上传和详细位置字段。

 - [ ] **步骤 3：RiskUnitForm**

 **文件：** `frontend/src/components/enterprise/RiskUnitForm.tsx`（新建）

 Modal 表单，字段：名称、单元类型（Select：设备/物料/工艺/电气/特种设备/其他）、描述、位置。

 - [ ] **步骤 4：RiskEventForm**

 **文件：** `frontend/src/components/enterprise/RiskEventForm.tsx`（新建）

 Modal 表单，关键设计：**方法参数联动**。

 1. 顶部选择 `method_type`（LS/LEC/煤矿 LS/直接判定）
 2. 根据方法类型动态显示参数输入：
    - LS：L（Select 1-5 含标准描述）+ S（Select 1-5 含标准描述）
    - LEC：L（Select）+ E（Select）+ C（Select）
    - DIRECT：风险等级（Select 手动选择）
 3. 参数选择后实时在前端用 `computeRiskLS/computeRiskLEC` 预览评级结果
 4. 提交时发送 `method_type` + `method_params`，后端自动双重计算

 - [ ] **步骤 5：RiskMeasureForm**

 **文件：** `frontend/src/components/enterprise/RiskMeasureForm.tsx`（新建）

 Modal 表单，字段：措施分类（Select：工程技术/管理措施/个体防护/应急处置）、措施类型（Input）、描述（TextArea）、责任人、期限（DatePicker）、检查项目（动态增删列表：名称+标准+频次）。

 - [ ] **步骤 6：Commit**

 ```bash
 git add frontend/src/components/enterprise/RiskZoneForm.tsx
 git add frontend/src/components/enterprise/RiskObjectForm.tsx
 git add frontend/src/components/enterprise/RiskUnitForm.tsx
 git add frontend/src/components/enterprise/RiskEventForm.tsx
 git add frontend/src/components/enterprise/RiskMeasureForm.tsx
 git commit -m "feat: 5 risk hierarchy form components"
 ```

 ---

 ## 任务 10：前端页面集成 + 旧数据迁移向导

 - [ ] **步骤 1：修改 EnterpriseDetailPage.tsx**

 **文件：** `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`

 将"风险源"Tab 替换为新的分级管控组件。Tab label 改为「风险分级管控」。

 ```tsx
 // Tab items 中新增：
 {
   key: "risk-management",
   label: "风险分级管控",
   children: <RiskManagementTab enterpriseId={id!} floorPlanUrl={enterprise.floor_plan_url} />,
 }
 ```

 `RiskManagementTab` 是新的容器组件，内部包含：
 - 顶部：方法配置面板（Collapse 折叠）
 - 主体：RiskHierarchyTree 层级树
 - 如有未迁移的旧 `risk_sources` 数据，顶部显示 Alert + 「迁移旧数据」按钮

 - [ ] **步骤 2：修改 RiskAssessmentTab.tsx**

 **文件：** `frontend/src/pages/Enterprise/RiskAssessmentTab.tsx`

 将无数据检查从 `risk_sources` 计数改为 `risk_events` 计数。

 - [ ] **步骤 3：RiskMigrationWizard 组件**

 **文件：** `frontend/src/components/enterprise/RiskMigrationWizard.tsx`（新建）

 功能：
 1. 检测旧 `risk_sources` 中 `migrated=false` 的数据
 2. 显示预览列表，AI 建议映射关系（旧风险源名称 → 新分区/对象/事件）
 3. 用户确认映射 → 调用 `/migrate` 端点批量创建新层级数据
 4. 迁移完成后标记旧数据 `migrated=true`

 - [ ] **步骤 4：Commit**

 ```bash
 git add frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx
 git add frontend/src/pages/Enterprise/RiskAssessmentTab.tsx
 git add frontend/src/components/enterprise/RiskMigrationWizard.tsx
 git commit -m "feat: integrate risk management into EnterpriseDetailPage + migration wizard"
 ```

 ---

 ## 任务 11：端到端验证 + 清理

 - [ ] **步骤 1：后端 API 冒烟测试**

 ```bash
 cd backend
 python -c "
 import asyncio
 from app.services.risk_method_engine import compute_risk

 # LS
 r = compute_risk('LS', {'l': 5, 's': 5})
 assert r.risk_level == '重大' and r.risk_score == 'R=25', f'LS failed: {r}'

 # LEC
 r = compute_risk('LEC', {'l': 10, 'e': 6, 'c': 40})
 assert r.risk_level == '重大' and 'D=2400' in r.risk_score, f'LEC failed: {r}'

 # DIRECT
 r = compute_risk('DIRECT', {'risk_level': '重大'})
 assert r.risk_level == '重大' and r.risk_score == '-', f'DIRECT failed: {r}'

 print('All method engine tests passed')
 "
 ```

 - [ ] **步骤 2：旧 risk_sources 端点标记 deprecated**

 **文件：** `backend/app/routers/risk_sources_ext.py`

 在所有旧 CRUD 端点（`POST /risk-sources`、`PUT /risk-sources/{id}`、`DELETE /risk-sources/{id}`）开头添加警告响应头：

 ```python
 from fastapi import Response
 # 在每个端点开头添加：
 response.headers["X-Deprecated"] = "true"
 response.headers["X-Migration-URL"] = f"/api/v1/enterprises/{enterprise_id}/risk-management/migrate"
 ```

 - [ ] **步骤 3：前端构建验证**

 ```bash
 cd frontend
 npm run build
 ```

 - [ ] **步骤 4：Commit**

 ```bash
 git add .
 git commit -m "test: risk method engine unit tests + deprecated old endpoints + build verification"
 ```

 ---

 ## 波及影响汇总

 | 文件 | 影响程度 | 操作 |
 |------|:--:|------|
 | [enterprise.py (models)](/C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/models/enterprise.py) | 低 | 新增 2 字段（risk_method_config + migrated） |
 | [risk_sources_ext.py](/C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/routers/risk_sources_ext.py) | 低 | 旧端点标记 deprecated，保留可读 |
 | [risk_assessment.py](/C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/routers/risk_assessment.py) | 中 | 上下文构建器和数据检查替换 |
 | [generation.py](/C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/routers/generation.py) | 中 | 预案生成上下文从 flat 改为层级 |
 | [risk_assessment_service.py](/C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/services/risk_assessment_service.py) | 低 | 保留（旧方法），新增 risk_context_builder 替代 |
 | [main.py](/C:/Users/55061/Documents/数字化预案自动生成 2/backend/app/main.py) | 低 | 注册新路由 |
 | [RiskSourceForm.tsx](/C:/Users/55061/Documents/数字化预案自动生成 2/frontend/src/components/enterprise/RiskSourceForm.tsx) | 低 | 保留可读，废弃引用 |
 | [RiskAssessmentTab.tsx](/C:/Users/55061/Documents/数字化预案自动生成 2/frontend/src/pages/Enterprise/RiskAssessmentTab.tsx) | 中 | 数据检查逻辑适配 |
 | [EnterpriseDetailPage.tsx](/C:/Users/55061/Documents/数字化预案自动生成 2/frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx) | 中 | Tab 替换 |
 | [riskSourceService.ts](/C:/Users/55061/Documents/数字化预案自动生成 2/frontend/src/services/riskSourceService.ts) | 低 | 保留可读 |
 | [riskSource.ts (types)](/C:/Users/55061/Documents/数字化预案自动生成 2/frontend/src/types/riskSource.ts) | 低 | 保留可读 |
 | [riskMatrix.ts](/C:/Users/55061/Documents/数字化预案自动生成 2/frontend/src/utils/riskMatrix.ts) | 低 | 保留（新方法引擎在 riskMethodEngine.ts） |

 **无影响文件**（确认不需要变更）：
 - 所有 `models/` 下非 enterprise/risk_management 的文件
 - 所有 `schemas/` 下非 enterprise/risk_management 的文件
 - 所有非 risk/enterprise/generation 的 `routers/`
 - 所有前端非 Enterprise 目录的 pages
 - 移动端（m.html / mobile screens）— 暂不在本次改造范围内

 ---

 ## 风险与注意事项

 1. **旧数据迁移不自动执行**：旧 `risk_sources` 数据保留不动，由用户通过迁移向导手动迁移，避免数据丢失风险。
 2. **数据库迁移建议在低峰期执行**：6 张新表的创建无锁操作，但建议先备份。
 3. **前端树状组件性能**：对于超过 200 个节点的大型企业，Tree 组件需要虚拟滚动。目前先不做，后续按需添加。
 4. **事件 parent 约束**：数据库层 `ck_event_parent` 确保事件必须挂在 unit 或 object 上（二者互斥）。
 5. **方法配置 JSONB 结构版本**：scheme 不包含 version 字段，后续如有 breaking change 需手动迁移。

 ---

 **计划完成。两种执行方式：**

 **1. 子代理驱动（推荐）** — 调度 11 个任务并行执行，每个任务都经过代码审查

 **2. 内联执行** — 在当前会话中逐任务执行，设有检查点

 选哪种方式？
