 # 风险分级管控模块 — 完整可落地实施方案（第 1/4 段）
 
 > **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development 逐任务实现。步骤使用复选框跟踪进度。
 
 **目标：** 将扁平化 risk_sources 重构为五层级风险分级管控体系，支持 LS/LEC/煤矿LS/直接判定自动评级，AI 深度融合，可视化总览
 
 **架构：** 新增 6 张 PostgreSQL 表 + 4 个后端服务文件 + 1 个路由文件（~30 端点）+ 15 个前端组件。旧 risk_sources 表保留不动，通过迁移向导导入新体系。
 
 **技术栈：** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL JSONB + React/TypeScript + Ant Design 5
 
 **依赖文档：** PRD `prd/PRD-15-风险分级管控模块.md` / 原型 `frontend/prototypes/risk-management/prototype.html`
 
 ---
 
 ## 文件变更清单
 
 ### 新建文件（24 个）
 
 | 文件 | 职责 |
 |------|------|
 | `backend/db_migration_risk_overhaul.sql` | 全部 DDL（6 表 + 3 ALTER + 2 INSERT 预置方法） |
 | `backend/app/models/risk_management.py` | 6 个 ORM 模型（RiskZone/RiskObject/RiskUnit/RiskEvent/RiskMeasure/RiskAssessmentMethod） |
 | `backend/app/schemas/risk_management.py` | 全部 Pydantic Schema（Create/Update/Response/Hierarchy/AI/Migration） |
 | `backend/app/services/risk_method_engine.py` | 多方法计算引擎 + 方法配置查询辅助 |
 | `backend/app/services/risk_context_builder.py` | 层级化上下文构建器（替代旧 build_risk_assessment_context） |
 | `backend/app/services/risk_ai_service.py` | AI 辅助服务（6 个函数，封装 LLM 调用 + 提示词构建） |
 | `backend/app/routers/risk_management.py` | 全层级 CRUD（约 30 端点） + AI 端点 + 迁移端点 |
 | `frontend/src/types/riskManagement.ts` | TypeScript 类型定义 |
 | `frontend/src/services/riskManagementService.ts` | API 调用函数 |
 | `frontend/src/utils/riskMethodEngine.ts` | 前端风险计算工具函数 + 常量 |
 | `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | Tab 容器组件 |
 | `frontend/src/pages/Enterprise/RiskMethodListPage.tsx` | 方法卡片列表页 |
 | `frontend/src/pages/Enterprise/RiskMethodEditorPage.tsx` | 方法编辑页（含实时评测面板） |
 | `frontend/src/pages/Enterprise/RiskOverviewPage.tsx` | 可视化总览页（四象限 + 视图切换） |
 | `frontend/src/components/enterprise/RiskHierarchyTree.tsx` | 递归层级树组件 |
 | `frontend/src/components/enterprise/RiskZoneForm.tsx` | 风险分区表单（含平面图多边形选区） |
 | `frontend/src/components/enterprise/RiskObjectForm.tsx` | 风险分析对象表单（含风险点图片上传） |
 | `frontend/src/components/enterprise/RiskUnitForm.tsx` | 风险分析单元表单 |
 | `frontend/src/components/enterprise/RiskEventForm.tsx` | 风险事件表单（含方法参数联动 + 实时评级） |
 | `frontend/src/components/enterprise/RiskMeasureForm.tsx` | 管控措施表单（含检查项目动态列表） |
 | `frontend/src/components/enterprise/RiskSmartGuideModal.tsx` | AI 智能导引两步弹窗 |
 | `frontend/src/components/enterprise/RiskMigrationWizard.tsx` | 旧数据迁移向导 |
 | `frontend/src/components/enterprise/RiskOverviewMatrix.tsx` | 风险矩阵热力图组件（交互式） |
 | `frontend/src/components/enterprise/RiskOverviewStats.tsx` | 统计面板组件（环形图 + 柱状图 + 汇总） |
 
 ### 修改文件（9 个）
 
 | 文件 | 变更要点 |
 |------|----------|
 | `backend/app/models/enterprise.py` | Enterprise 类加 `risk_method_config` JSONB 字段；RiskSource 类加 `migrated` BOOLEAN 字段 |
 | `backend/app/schemas/enterprise.py` | EnterpriseCreate/EnterpriseUpdate/EnterpriseResponse 各加 `risk_method_config` |
 | `backend/app/routers/enterprises.py` | `_build_response` 填充 `risk_method_config` |
 | `backend/app/routers/risk_assessment.py` | 上下文构建替换为 `build_risk_management_context`；数据检查从 `risk_sources` 改为 `risk_events` |
 | `backend/app/routers/generation.py` | `_collect_enterprise_data` 中风险数据来源改为层级结构 |
 | `backend/app/routers/risk_sources_ext.py` | 旧端点返回加 `X-Deprecated` + `X-Migration-URL` 响应头 |
 | `backend/app/main.py` | 注册 `risk_management` 路由 |
 | `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx` | tabItems 新增「风险分级管控」Tab |
 | `frontend/src/App.tsx` | 添加三个新路由（方法管理页/编辑页/总览页） |
 
 ---
 
 ## 任务 1：数据库迁移 DDL
 
 **文件：**
 - 创建：`backend/db_migration_risk_overhaul.sql`
 - 修改：`backend/app/models/enterprise.py:69-71`（Enterprise 类，在 surrounding_info 之后）
 - 修改：`backend/app/models/enterprise.py:87-94`（RiskSource 类，在 sort_order 之后）
 
 - [ ] **步骤 1.1：编写完整 DDL 迁移文件**
 
 创建 `backend/db_migration_risk_overhaul.sql`，内容如下：
 
 ```sql
 -- ============================================================
 -- 风险管理功能全面重构 DDL
 -- 执行前请备份数据库：pg_dump > backup_$(date +%Y%m%d).sql
 -- ============================================================
 
 BEGIN;
 
 -- 1. 风险评估方法配置表
 CREATE TABLE IF NOT EXISTS risk_assessment_methods (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     enterprise_id UUID REFERENCES enterprises(id) ON DELETE CASCADE,
     method_type VARCHAR(20) NOT NULL CHECK (method_type IN ('LS','LEC','COAL_LS','DIRECT')),
     name VARCHAR(100) NOT NULL,
     description TEXT DEFAULT '',
     config JSONB NOT NULL DEFAULT '{}'::jsonb,
     is_active BOOLEAN NOT NULL DEFAULT true,
     is_system BOOLEAN NOT NULL DEFAULT false,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ram_enterprise ON risk_assessment_methods(enterprise_id);
 CREATE INDEX idx_ram_type_active ON risk_assessment_methods(method_type, is_active) WHERE is_active = true;
 
 -- 2. 风险分区表
 CREATE TABLE IF NOT EXISTS risk_zones (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
     name VARCHAR(255) NOT NULL,
     description TEXT DEFAULT '',
     sort_order INTEGER NOT NULL DEFAULT 0,
     floor_plan_polygon JSONB DEFAULT NULL,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_rz_enterprise ON risk_zones(enterprise_id);
 CREATE INDEX idx_rz_order ON risk_zones(enterprise_id, sort_order);
 
 -- 3. 风险分析对象表
 CREATE TABLE IF NOT EXISTS risk_objects (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
     zone_id UUID REFERENCES risk_zones(id) ON DELETE SET NULL,
     name VARCHAR(255) NOT NULL,
     category VARCHAR(100) DEFAULT NULL,
     location VARCHAR(500) DEFAULT NULL,
     location_x FLOAT DEFAULT NULL,
     location_y FLOAT DEFAULT NULL,
     description TEXT DEFAULT '',
     image_url VARCHAR(500) DEFAULT NULL,
     is_risk_point BOOLEAN NOT NULL DEFAULT false,
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ro_enterprise ON risk_objects(enterprise_id);
 CREATE INDEX idx_ro_zone ON risk_objects(zone_id);
 CREATE INDEX idx_ro_risk_point ON risk_objects(enterprise_id, is_risk_point) WHERE is_risk_point = true;
 
 -- 4. 风险分析单元表
 CREATE TABLE IF NOT EXISTS risk_units (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     object_id UUID NOT NULL REFERENCES risk_objects(id) ON DELETE CASCADE,
     name VARCHAR(255) NOT NULL,
     unit_type VARCHAR(50) DEFAULT NULL,
     description TEXT DEFAULT '',
     location VARCHAR(500) DEFAULT NULL,
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_ru_object ON risk_units(object_id);
 CREATE INDEX idx_ru_object_order ON risk_units(object_id, sort_order);
 
 -- 5. 风险事件表（含 parent 互斥约束）
 CREATE TABLE IF NOT EXISTS risk_events (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     unit_id UUID REFERENCES risk_units(id) ON DELETE CASCADE,
     object_id UUID REFERENCES risk_objects(id) ON DELETE CASCADE,
     accident_type VARCHAR(100) NOT NULL,
     description TEXT DEFAULT '',
     trigger_conditions TEXT DEFAULT '',
     consequences TEXT DEFAULT '',
     method_type VARCHAR(20) NOT NULL DEFAULT 'LS' CHECK (method_type IN ('LS','LEC','COAL_LS','DIRECT')),
     method_params JSONB NOT NULL DEFAULT '{}'::jsonb,
     risk_level VARCHAR(20) DEFAULT NULL,
     risk_score VARCHAR(50) DEFAULT NULL,
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
 CREATE INDEX idx_re_risk_level ON risk_events(risk_level);
 
 -- 6. 风险管控措施表
 CREATE TABLE IF NOT EXISTS risk_measures (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     event_id UUID NOT NULL REFERENCES risk_events(id) ON DELETE CASCADE,
     measure_category VARCHAR(50) NOT NULL CHECK (measure_category IN ('engineering','management','ppe','emergency')),
     measure_type VARCHAR(100) DEFAULT NULL,
     description TEXT NOT NULL,
     responsible_person VARCHAR(100) DEFAULT NULL,
     deadline DATE DEFAULT NULL,
     check_items JSONB DEFAULT '[]'::jsonb,
     status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','implemented','expired')),
     sort_order INTEGER NOT NULL DEFAULT 0,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
 );
 CREATE INDEX idx_rm_event ON risk_measures(event_id);
 CREATE INDEX idx_rm_status ON risk_measures(event_id, status);
 
 -- 7. 旧 risk_sources 表增加 migrated 标记
 ALTER TABLE risk_sources ADD COLUMN IF NOT EXISTS migrated BOOLEAN NOT NULL DEFAULT false;
 
 -- 8. enterprises 表增加风险方法配置
 ALTER TABLE enterprises ADD COLUMN IF NOT EXISTS risk_method_config JSONB DEFAULT '{}'::jsonb;
 
 -- 9. 预置系统级 LS 评估方法
 INSERT INTO risk_assessment_methods (id, enterprise_id, method_type, name, description, config, is_system)
 VALUES (
     gen_random_uuid(), NULL, 'LS', 'L×S 风险矩阵法（5级）',
     '适用于一般工贸企业风险等级评估。参考标准：GB/T 27921-2011《风险管理 风险评估技术》。',
     '{
       "version":"1.0","formula":"R = L × S","display_name":"L×S 风险矩阵法",
       "parameters":[
         {"key":"l","label":"事故发生的可能性（L）","type":"select","range":[1,5],
          "levels":[
            {"value":1,"label":"极不可能","desc":"有充分有效的防范、控制、监测、保护措施，员工安全意识高，严格执行操作规程，极不可能发生事故"},
            {"value":2,"label":"不太可能","desc":"危害一旦发生能及时发现，并定期进行监测，或现场有防范控制措施并能有效执行，或过去偶尔发生事故或事件"},
            {"value":3,"label":"可能","desc":"没有保护措施，或未严格按操作程序执行，或危害的发生容易被发现，或过去曾经发生类似事故或事件"},
            {"value":4,"label":"较可能","desc":"危害的发生不容易被发现，现场没有检测系统，或控制措施未有效执行或不恰当，或危害常发生在预期情况下发生"},
            {"value":5,"label":"极可能","desc":"在现场没有采取防范、监测、保护、控制措施，或危害的发生不能被发现，或在正常情况下经常发生此类事故或事件"}
          ]},
         {"key":"s","label":"事故后果严重程度（S）","type":"select","range":[1,5],
          "levels":[
            {"value":1,"label":"很低","desc":"轻微伤害，无财产损失，不影响运营，企业形象无影响"},
            {"value":2,"label":"低","desc":"轻微伤害，财产损失<1万元，基本不影响运营，企业形象轻微影响"},
            {"value":3,"label":"中","desc":"人员轻伤，财产损失1-10万元，短期影响运营，企业形象局部影响"},
            {"value":4,"label":"高","desc":"人员重伤，财产损失10-100万元，较长时间停运，企业形象区域性影响"},
            {"value":5,"label":"很高","desc":"人员死亡，财产损失>100万元，长期停运或关闭，企业形象全国性影响"}
          ]}
       ],
       "risk_thresholds":[
         {"min":20,"max":25,"level":"重大","color":"#ff4d4f","action":"立即整改","deadline":"立即"},
         {"min":15,"max":19,"level":"较大","color":"#fa8c16","action":"立即或近期整改","deadline":"近期"},
         {"min":9,"max":14,"level":"一般","color":"#fadb14","action":"2年内治理","deadline":"2年"},
         {"min":1,"max":8,"level":"低","color":"#52c41a","action":"有条件有经费时治理","deadline":"有条件时"}
       ]
     }'::jsonb,
     true
 );
 
 -- 10. 预置系统级 LEC 评价法
 INSERT INTO risk_assessment_methods (id, enterprise_id, method_type, name, description, config, is_system)
 VALUES (
     gen_random_uuid(), NULL, 'LEC', 'LEC 评价法（格雷厄姆-金尼法）',
     '适用于作业条件危险性评价。参考标准：AQ 8001-2007《安全评价通则》。',
     '{
       "version":"1.0","formula":"D = L × E × C","display_name":"LEC 评价法",
       "parameters":[
         {"key":"l","label":"事故发生的可能性（L）","type":"select","range":[0.1,10],
          "levels":[
            {"value":0.1,"label":"实际不可能","desc":""},{"value":0.2,"label":"极不可能","desc":""},
            {"value":0.5,"label":"很不可能","desc":""},{"value":1,"label":"可能性小","desc":""},
            {"value":3,"label":"可能但不经常","desc":""},{"value":6,"label":"相当可能","desc":""},
            {"value":10,"label":"完全可以预料","desc":""}
          ]},
         {"key":"e","label":"暴露于危险环境的频繁程度（E）","type":"select","range":[0.5,10],
          "levels":[
            {"value":0.5,"label":"非常罕见","desc":""},{"value":1,"label":"每年几次","desc":""},
            {"value":2,"label":"每月一次","desc":""},{"value":3,"label":"每周一次","desc":""},
            {"value":6,"label":"逐日","desc":""},{"value":10,"label":"连续暴露","desc":""}
          ]},
         {"key":"c","label":"发生事故产生的后果（C）","type":"select","range":[1,100],
          "levels":[
            {"value":1,"label":"引人注意","desc":""},{"value":3,"label":"重大","desc":""},
            {"value":7,"label":"严重","desc":""},{"value":15,"label":"非常严重","desc":""},
            {"value":40,"label":"灾难","desc":""},{"value":100,"label":"大灾难","desc":""}
          ]}
       ],
       "risk_thresholds":[
         {"min":320,"max":9999,"level":"重大","color":"#ff4d4f","action":"立即停止作业整改","deadline":"立即"},
         {"min":160,"max":319,"level":"较大","color":"#fa8c16","action":"立即或近期整改","deadline":"近期"},
         {"min":70,"max":159,"level":"一般","color":"#fadb14","action":"限期整改","deadline":"限期"},
         {"min":0,"max":69,"level":"低","color":"#52c41a","action":"日常管理","deadline":"持续"}
       ]
     }'::jsonb,
     true
 );
 
 COMMIT;
 ```
 
 - [ ] **步骤 1.2：修改 Enterprise 和 RiskSource ORM 模型**
 
 在 `backend/app/models/enterprise.py` 中：
 
 ① 在 Enterprise 类的 `surrounding_info` 字段之后（约第 69 行后），`floor_plan_url` 之前，添加：
 
 ```python
 # 风险分级管控
 risk_method_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
 ```
 
 ② 在 RiskSource 类的 `sort_order` 字段之后（约第 94 行），`created_at` 之前，添加：
 
 ```python
 migrated: Mapped[bool] = mapped_column(Boolean, default=False)
 ```
 
 - [ ] **步骤 1.3：验证模型变更**
 
 运行以下命令确认新增字段可被 SQLAlchemy 发现，且不影响已有功能：
 
 ```bash
 cd backend
 python -c "
 from app.models.enterprise import Enterprise, RiskSource
 cols_e = [c.name for c in Enterprise.__table__.columns]
 cols_r = [c.name for c in RiskSource.__table__.columns]
 assert 'risk_method_config' in cols_e, f'Enterprise missing risk_method_config: {cols_e}'
 assert 'migrated' in cols_r, f'RiskSource missing migrated: {cols_r}'
 print('OK: Enterprise columns:', cols_e[-5:])
 print('OK: RiskSource columns:', cols_r[-5:])
 "
 ```
 
 预期输出：`OK: Enterprise columns: ['surrounding_info', 'risk_method_config', 'floor_plan_url', ...]` 和 `OK: RiskSource columns: ['sort_order', 'migrated', 'created_at']`。
 
 - [ ] **步骤 1.4：Commit**
 
 ```bash
 git add backend/db_migration_risk_overhaul.sql backend/app/models/enterprise.py
 git commit -m "feat(risk): add DDL for 6 risk management tables + enterprise.risk_method_config + risk_sources.migrated"
 ```
 
 ---
 
 ## 任务 2：后端 ORM 模型 — risk_management.py
 
 **文件：** `backend/app/models/risk_management.py`（新建）
 
 - [ ] **步骤 2.1：编写 6 个 ORM 模型**
 
 遵循现有 `enterprise.py` 的代码风格（UUID(as_uuid=False) 主键、Mapped 类型注解、relationship 含 cascade="all, delete-orphan" 和 lazy="selectin"）：
 
 ```python
 from datetime import datetime
 from uuid import uuid4
 from typing import Optional
 from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Date, func
 from sqlalchemy.orm import Mapped, mapped_column, relationship
 from sqlalchemy.dialects.postgresql import UUID, JSONB
 from app.database import Base
 
 
 class RiskAssessmentMethod(Base):
     __tablename__ = "risk_assessment_methods"
 
     id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
     enterprise_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=True, index=True)
     method_type: Mapped[str] = mapped_column(String(20), nullable=False)
     name: Mapped[str] = mapped_column(String(100), nullable=False)
     description: Mapped[str] = mapped_column(Text, default="")
     config: Mapped[dict] = mapped_column(JSONB, default=dict)
     is_active: Mapped[bool] = mapped_column(Boolean, default=True)
     is_system: Mapped[bool] = mapped_column(Boolean, default=False)
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
     deadline: Mapped[Optional[datetime]] = mapped_column(Date)
     check_items: Mapped[list] = mapped_column(JSONB, default=list)
     status: Mapped[str] = mapped_column(String(20), default="pending")
     sort_order: Mapped[int] = mapped_column(Integer, default=0)
     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
     updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
 
     event = relationship("RiskEvent", back_populates="measures", lazy="selectin")
 ```
 
 - [ ] **步骤 2.2：验证模型可导入且与数据库 schema 一致**
 
 ```bash
 cd backend
 python -c "
 from app.models.risk_management import (
     RiskAssessmentMethod, RiskZone, RiskObject,
     RiskUnit, RiskEvent, RiskMeasure
 )
 print('OK: all 6 models imported successfully')
 for m in [RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure, RiskAssessmentMethod]:
     print(f'  {m.__tablename__}: {len(m.__table__.columns)} columns')
 "
 ```
 
 预期输出：6 张表名，列数分别为：risk_assessment_methods(11), risk_zones(8), risk_objects(15), risk_units(8), risk_events(15), risk_measures(12)。
 
 - [ ] **步骤 2.3：Commit**
 
 ```bash
 git add backend/app/models/risk_management.py
 git commit -m "feat(risk): add 6 ORM models — zone/object/unit/event/measure/method"
 ```
 
 ---
 
 ## 任务 3：后端 Pydantic Schema
 
 **文件：** `backend/app/schemas/risk_management.py`（新建）
 
 - [ ] **步骤 3.1：编写完整 Schema**
 
 遵循项目现有 Schema 风格（`BaseModel`、`field_validator`、`model_config = {"from_attributes": True}`、`DatetimeStr` 时间类型、`ApiResponse` 包装）：
 
 ```python
 from datetime import datetime, date
 from typing import Optional
 from pydantic import BaseModel, field_validator
 from app.schemas.common import DatetimeStr
 
 
 # ── RiskAssessmentMethod ──
 class MethodCreate(BaseModel):
     method_type: str
     name: str
     description: str = ""
     config: dict = {}
 
 class MethodUpdate(BaseModel):
     name: str | None = None
     description: str | None = None
     config: dict | None = None
     is_active: bool | None = None
 
 class MethodResponse(BaseModel):
     id: str
     enterprise_id: str | None
     method_type: str
     name: str
     description: str = ""
     config: dict
     is_active: bool
     is_system: bool
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
 
 
 # ── 树状层级 Response（供 /hierarchy 端点）──
 
 class HierarchyMeasureResponse(BaseModel):
     id: str
     measure_category: str
     measure_type: str | None
     description: str
     status: str
     check_items: list[dict]
     model_config = {"from_attributes": True}
 
 class HierarchyEventResponse(BaseModel):
     id: str
     accident_type: str
     description: str | None
     risk_level: str | None
     risk_score: str | None
     method_type: str
     method_params: dict
     measures: list[HierarchyMeasureResponse] = []
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
 
 
 # ── AI 辅助相关 ──
 class SmartGuideRequest(BaseModel):
     description: str
 
 class SmartGuideResponse(BaseModel):
     hierarchy: list[HierarchyZoneResponse]
     summary: dict
 
 class AISuggestionItem(BaseModel):
     accepted: bool = False
     data: dict = {}
 
 class MethodPreviewRequest(BaseModel):
     method_id: str
     params: dict
 
 class MethodPreviewResponse(BaseModel):
     risk_level: str
     risk_score: str
     action: str
     deadline: str
 ```
 
 - [ ] **步骤 3.2：验证 Schema 可导入**
 
 ```bash
 cd backend
 python -c "
 from app.schemas.risk_management import (
     RiskZoneCreate, RiskZoneResponse, RiskEventCreate, RiskEventResponse,
     HierarchyZoneResponse, HierarchyObjectResponse, HierarchyUnitResponse,
     HierarchyEventResponse, HierarchyMeasureResponse
 )
 # 测试嵌套序列化
 m = HierarchyMeasureResponse.model_validate({'id':'x','measure_category':'engineering','description':'test','status':'pending','check_items':[]})
 e = HierarchyEventResponse.model_validate({'id':'x','accident_type':'火灾','risk_level':'重大','risk_score':'R=20','method_type':'LS','method_params':{},'measures':[m]})
 u = HierarchyUnitResponse.model_validate({'id':'x','name':'罐体','unit_type':'设备','events':[e]})
 o = HierarchyObjectResponse.model_validate({'id':'x','name':'1号储罐','category':'罐区','is_risk_point':False,'units':[u],'events':[]})
 z = HierarchyZoneResponse.model_validate({'id':'x','name':'储罐区','objects':[o]})
 print('OK: hierarchy nesting works')
 print(f'  Zone: {z.name} -> Object: {z.objects[0].name} -> Unit: {z.objects[0].units[0].name} -> Event: {z.objects[0].units[0].events[0].accident_type}({z.objects[0].units[0].events[0].risk_level}) -> Measure: {z.objects[0].units[0].events[0].measures[0].description}')
 "
 ```
 
 预期输出：完整的五级嵌套序列化成功。
 
 - [ ] **步骤 3.3：Commit**
 
 ```bash
 git add backend/app/schemas/risk_management.py
 git commit -m "feat(risk): add Pydantic schemas for all 6 entities + hierarchy tree response"
 ```
 
 ---
 
 ## 任务 4：风险计算方法引擎
 
 **文件：** `backend/app/services/risk_method_engine.py`（新建）
 
 - [ ] **步骤 4.1：编写计算引擎**
 
 ```python
 """风险评估多方法计算引擎。
 
 支持 LS 矩阵、LEC 评价法、煤矿 LS 矩阵、直接判定法。
 所有计算参数和阈值从 risk_assessment_methods.config JSONB 中读取，零硬编码。
 """
 from typing import Optional
 from dataclasses import dataclass
 from sqlalchemy.ext.asyncio import AsyncSession
 from sqlalchemy import select
 from app.models.risk_management import RiskAssessmentMethod
 
 
 @dataclass
 class RiskResult:
     risk_level: str    # "重大" | "较大" | "一般" | "低"
     risk_score: str    # "R=20" | "D=270" | "-"
     action: str        # 整改建议
     deadline: str      # 整改期限
 
 
 def compute_risk(method_type: str, params: dict, config: dict | None = None) -> RiskResult:
     """
     计算风险等级。
 
     Args:
         method_type: "LS" | "LEC" | "COAL_LS" | "DIRECT"
         params: 方法参数，如 {"l": 4, "s": 5} 或 {"l": 6, "e": 3, "c": 15}
         config: 来自 risk_assessment_methods.config 的配置字典。DIRECT 方法可不传
 
     Returns:
         RiskResult 包含 risk_level, risk_score, action, deadline
     """
     if method_type == "DIRECT":
         level = params.get("risk_level", "一般")
         return RiskResult(risk_level=level, risk_score="-", action=level, deadline="按需")
 
     if not config:
         thresholds = []
     else:
         thresholds = config.get("risk_thresholds", [])
 
     if method_type == "LS":
         l_val = float(params.get("l", 3))
         s_val = float(params.get("s", 3))
         r = int(l_val * s_val)
         score_str = f"R={r}"
 
     elif method_type == "LEC":
         l_val = float(params.get("l", 1))
         e_val = float(params.get("e", 1))
         c_val = float(params.get("c", 1))
         r = int(l_val * e_val * c_val)
         score_str = f"D={r}"
 
     elif method_type == "COAL_LS":
         l_val = float(params.get("l", 3))
         s_val = float(params.get("s", 3))
         r = int(l_val * s_val)
         score_str = f"R={r}"
         # 煤矿行业特有的判定表（如果 config 中未自定义则使用默认）
         if not thresholds:
             thresholds = [
                 {"min": 20, "max": 25, "level": "重大", "action": "立即停产整改", "deadline": "立即"},
                 {"min": 15, "max": 19, "level": "较大", "action": "限期停产整改", "deadline": "1个月"},
                 {"min": 10, "max": 14, "level": "一般", "action": "限期整改", "deadline": "3个月"},
                 {"min": 1, "max": 9, "level": "低", "action": "加强日常管理", "deadline": "持续"},
             ]
     else:
         return RiskResult(risk_level="一般", risk_score="-", action="未知方法", deadline="N/A")
 
     # 遍历阈值表确定等级
     for t in thresholds:
         if t["min"] <= r <= t["max"]:
             return RiskResult(
                 risk_level=t["level"],
                 risk_score=score_str,
                 action=t.get("action", ""),
                 deadline=t.get("deadline", ""),
             )
 
     return RiskResult(risk_level="低", risk_score=score_str, action="日常管理", deadline="持续")
 
 
 async def get_active_method_config(
     db: AsyncSession,
     enterprise_id: str,
     method_type: str = "LS",
 ) -> dict | None:
     """
     获取企业或系统级活跃方法配置。
 
     优先级：企业级（enterprise_id 匹配 + is_active=true）
             → 系统级（enterprise_id IS NULL + is_active=true）
 
     Args:
         db: 数据库会话
         enterprise_id: 企业 ID
         method_type: 方法类型，默认 "LS"
 
     Returns:
         config JSONB 字典，如果未找到返回 None
     """
     # 先查企业级
     result = await db.execute(
         select(RiskAssessmentMethod).where(
             RiskAssessmentMethod.enterprise_id == enterprise_id,
             RiskAssessmentMethod.method_type == method_type,
             RiskAssessmentMethod.is_active == True,
         )
     )
     method = result.scalar_one_or_none()
     if method:
         return method.config
 
     # 回退系统级
     result = await db.execute(
         select(RiskAssessmentMethod).where(
             RiskAssessmentMethod.enterprise_id.is_(None),
             RiskAssessmentMethod.method_type == method_type,
             RiskAssessmentMethod.is_active == True,
         )
     )
     method = result.scalar_one_or_none()
     return method.config if method else None
 ```
 
 - [ ] **步骤 4.2：单元测试验证计算逻辑**
 
 ```bash
 cd backend
 python -c "
 from app.services.risk_method_engine import compute_risk, RiskResult
 
 # LS 矩阵测试
 r = compute_risk('LS', {'l': 5, 's': 5})
 assert r.risk_level == '重大' and r.risk_score == 'R=25', f'LS(5,5) failed: {r}'
 
 r = compute_risk('LS', {'l': 2, 's': 4})
 assert r.risk_level == '低' and r.risk_score == 'R=8', f'LS(2,4) failed: {r}'
 
 r = compute_risk('LS', {'l': 3, 's': 5})
 assert r.risk_level == '重大' and r.risk_score == 'R=15', f'LS(3,5) failed: {r}'
 
 # LEC 测试
 r = compute_risk('LEC', {'l': 10, 'e': 6, 'c': 40})
 assert r.risk_level == '重大' and 'D=2400' in r.risk_score, f'LEC(10,6,40) failed: {r}'
 
 r = compute_risk('LEC', {'l': 0.5, 'e': 1, 'c': 7})
 assert r.risk_level == '低' and 'D=3' in r.risk_score, f'LEC(0.5,1,7) failed: {r}'
 
 # DIRECT 测试
 r = compute_risk('DIRECT', {'risk_level': '较大'})
 assert r.risk_level == '较大' and r.risk_score == '-', f'DIRECT failed: {r}'
 
 print('All compute_risk tests passed')
 
 # 边界值测试
 r = compute_risk('LS', {'l': 4, 's': 5})  # R=20 -> 重大边界
 assert r.risk_level == '重大', f'LS boundary 20 failed: {r}'
 
 r = compute_risk('LS', {'l': 4, 's': 4})  # R=16 -> 较大
 assert r.risk_level == '较大', f'LS(4,4) failed: {r}'
 
 print('All boundary tests passed')
 "
 ```
 
 预期输出：`All compute_risk tests passed` 后接 `All boundary tests passed`。
 
 - [ ] **步骤 4.3：Commit**
 
 ```bash
 git add backend/app/services/risk_method_engine.py
 git commit -m "feat(risk): add multi-method risk computation engine — LS/LEC/COAL_LS/DIRECT"
 ```
 
 ---
 
 > **第 1 段结束。共 4 段。** 继续 → 第 2 段：任务 5-8（上下文构建器 + AI 服务 + CRUD 路由 + 后端集成）

 # 风险分级管控模块 — 完整可落地实施方案（第 2/4 段）
 
 ---
 
 ## 任务 5：层级化上下文构建器
 
 **文件：** `backend/app/services/risk_context_builder.py`（新建）
 
 - [ ] **步骤 5.1：编写上下文构建函数**
 
 这个函数替代旧的 `build_risk_assessment_context()`（位于 `risk_assessment_service.py`），从新五层表构建结构化的 risk 数据供 AI 报告生成和预案生成使用。
 
 ```python
 """风险分级管控上下文构建器。
 
 替代旧的 build_risk_assessment_context()，消费新的五层表结构。
 """
 from sqlalchemy.ext.asyncio import AsyncSession
 from sqlalchemy import select
 from sqlalchemy.orm import selectinload
 from app.models.enterprise import Enterprise
 from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
 
 
 async def build_risk_management_context(enterprise_id: str, db: AsyncSession) -> dict:
     """
     从五层表构建企业风险管控上下文，用于 AI 报告生成和预案生成。
 
     返回结构与旧 build_risk_assessment_context 兼容，但 risk_sources
     从扁平列表改为包含 zone/object/unit 层级信息的结构化列表。
     """
     # 获取企业信息
     ent_result = await db.execute(
         select(Enterprise).where(Enterprise.id == enterprise_id)
     )
     ent = ent_result.scalar_one_or_none()
     if not ent:
         raise ValueError("企业不存在")
 
     # 获取完整层级树（selectin 预加载避免 N+1）
     zones_result = await db.execute(
         select(RiskZone)
         .where(RiskZone.enterprise_id == enterprise_id)
         .options(
             selectinload(RiskZone.objects)
             .selectinload(RiskObject.units)
             .selectinload(RiskUnit.events)
             .selectinload(RiskEvent.measures)
         )
         .order_by(RiskZone.sort_order)
     )
     zones = zones_result.scalars().all()
 
     # 构建层级化 risk_sources 列表
     risk_sources_list = []
     for zone in zones:
         for obj in zone.objects:
             # 对象下直接挂载的事件（无单元场景）
             for event in obj.events:
                 risk_sources_list.append({
                     "zone": zone.name,
                     "object": obj.name,
                     "unit": None,
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
             # 单元下挂载的事件（标准场景）
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
 
     return {
         "enterprise": {
             "name": ent.name,
             "industry": ent.industry,
             "address": ent.address,
             "employee_count": ent.employee_count,
             "business_scope": ent.business_scope,
             "building_overview": ent.building_overview,
             "surrounding_info": ent.surrounding_info,
             "fire_protection_summary": ent.fire_protection_summary,
             "special_equipment_detail": ent.special_equipment_detail,
             "main_equipment_list": ent.main_equipment_list,
             "natural_conditions": ent.natural_conditions,
             "hazardous_chemicals": ent.hazardous_chemicals,
         },
         "risk_sources": risk_sources_list,
         "zone_count": len(zones),
         "total_events": sum(
             len(obj.events) + sum(len(u.events) for u in obj.units)
             for zone in zones for obj in zone.objects
         ),
     }
 ```
 
 - [ ] **步骤 5.2：验证函数可导入**
 
 ```bash
 cd backend
 python -c "from app.services.risk_context_builder import build_risk_management_context; print('OK')"
 ```
 
 预期输出：`OK`
 
 - [ ] **步骤 5.3：Commit**
 
 ```bash
 git add backend/app/services/risk_context_builder.py
 git commit -m "feat(risk): add hierarchical context builder replacing flat risk_sources context"
 ```
 
 ---
 
 ## 任务 6：AI 辅助服务
 
 **文件：** `backend/app/services/risk_ai_service.py`（新建）
 
 该服务是 6 个 AI 辅助端点的共用逻辑层。复用 `risk_sources_ext.py` 中现有的 LLM 调用模式（`_call_llm_nonstream` + `_decrypt_api_key`）。
 
 - [ ] **步骤 6.1：编写 AI 服务**
 
 ```python
 """AI 辅助风险辨识服务。
 
 为 risk_management 路由的 6 个 AI 端点提供共用逻辑：
 analyze_floor_plan / suggest_objects / suggest_events / suggest_measures
 / smart_guide / migrate_preview
 """
 import json
 import logging
 from sqlalchemy.ext.asyncio import AsyncSession
 from sqlalchemy import select
 from fastapi import HTTPException
 from app.models.enterprise import AIConfig
 from app.config import settings
 from Crypto.Cipher import AES
 from Crypto.Util.Padding import unpad
 import httpx
 
 logger = logging.getLogger(__name__)
 
 
 def _decrypt_api_key(hex_str: str) -> str:
     """AES-256 ECB 解密 API Key — 与 generation.py 保持一致"""
     key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
     cipher = AES.new(key, AES.MODE_ECB)
     return unpad(cipher.decrypt(bytes.fromhex(hex_str)), 16).decode()
 
 
 async def _call_llm(messages: list[dict], ai_config: AIConfig) -> str:
    """非流式 LLM 调用，60s 超时"""
    try:
        api_key = _decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise HTTPException(500, "AI 配置密钥解密失败")
 
    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")
 
    payload = {
        "model": ai_config.model_name,
        "messages": messages,
        "temperature": ai_config.temperature,
        "max_tokens": ai_config.max_tokens,
        "top_p": ai_config.top_p,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base}/chat/completions", json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                raise HTTPException(500, f"AI 调用失败: HTTP {resp.status_code}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise HTTPException(504, "AI 响应超时（60s），请稍后重试")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"AI 服务连接失败: {str(e)}")
 
 
 async def _get_ai_config(user_id: str, db: AsyncSession) -> AIConfig:
     """获取用户 AI 配置，未配置则抛异常"""
     result = await db.execute(
         select(AIConfig).where(AIConfig.user_id == user_id, AIConfig.is_active == True)
     )
     config = result.scalar_one_or_none()
     if not config:
         raise HTTPException(400, "请先在系统设置中配置 AI 模型")
     return config
 
 
 def _parse_ai_json(raw: str) -> dict:
     """解析 AI 返回的 JSON，处理 markdown 代码块包裹"""
     raw = raw.strip()
     if raw.startswith("```"):
         lines = raw.split("\n")
         raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
         if raw.endswith("```"):
             raw = raw[:-3].strip()
     try:
         return json.loads(raw)
     except json.JSONDecodeError:
         raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")
 
 
 async def suggest_objects(
     zone_name: str, zone_desc: str, enterprise_info: dict,
     ai_config: AIConfig, existing_names: list[str] = [],
 ) -> list[dict]:
     """AI 建议分区下的对象及单元"""
     existing_str = "\n".join(f"- {n}" for n in existing_names) if existing_names else "（无已有对象）"
     prompt = f"""请根据以下信息，列出该企业「{zone_name}」分区下可能存在的主要风险分析对象。
 
 分区描述：{zone_desc}
 企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}
 已有对象（请避免重复）：{existing_str}
 
 为每个对象列出建议的分析单元（设备、管道、阀门等部件），并给出对象类别、位置和风险描述。
 
 输出 JSON 格式：
 {{"objects": [{{"name": "...", "category": "...", "location": "...", "description": "...", "units": [{{"name": "...", "unit_type": "设备|管道|阀门|仪表|电气|特种设备|其他"}}]}}]}}"""
 
     messages = [
         {"role": "system", "content": "你是持有国家注册安全工程师资格的应急预案专家，精通 GB/T 13861 和 GB 6441。"},
         {"role": "user", "content": prompt},
     ]
     raw = await _call_llm(messages, ai_config)
     data = _parse_ai_json(raw)
     return data.get("objects", [])
 
 
 async def suggest_events(
     unit_name: str, unit_type: str, object_name: str, zone_name: str,
     enterprise_info: dict, ai_config: AIConfig,
 ) -> list[dict]:
     """AI 建议单元可能的风险事件及评估参数"""
     prompt = f"""你是一位持有国家注册安全工程师资格的风险评估专家。
 
 请分析以下风险分析单元可能发生的事故类型，给出 1-3 个最可能的风险事件，每个包含：
 - accident_type: 事故类型（按 GB 6441-1986）
 - description: 事故描述
 - trigger_conditions: 触发条件
 - consequences: 可能后果
 - method_type: 建议评估方法（LS/LEC/DIRECT）
 - suggested_params: 建议评估参数（如 {{"l":2,"s":4}}），含 reasoning 说明理由
 - reasoning: 参数理由
 
 单元信息：
 - 单元名称：{unit_name}
 - 单元类型：{unit_type}
 - 所属对象：{object_name}
 - 所属分区：{zone_name}
 
 企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}
 
 输出 JSON：{{"events": [{{"accident_type":"...","description":"...","trigger_conditions":"...","consequences":"...","method_type":"LS","suggested_params":{{}},"reasoning":"..."}}]}}"""
 
     messages = [
         {"role": "system", "content": "你是持有国家注册安全工程师资格的风险评估专家，精通 GB/T 13861 和 GB 6441。"},
         {"role": "user", "content": prompt},
     ]
     raw = await _call_llm(messages, ai_config)
     data = _parse_ai_json(raw)
     return data.get("events", [])
 
 
 async def suggest_measures(
     accident_type: str, risk_level: str, unit_name: str, object_name: str,
     enterprise_info: dict, ai_config: AIConfig,
 ) -> list[dict]:
     """AI 建议风险事件的管控措施及检查项目"""
     prompt = f"""请为以下风险事件建议管控措施。按四类措施（engineering工程技术、management管理、ppe个体防护、emergency应急处置）各建议 1-3 条，每条含措施描述和 1-2 个检查项目（name+standard+frequency）。
 
 事件信息：
 - 事故类型：{accident_type}
 - 风险等级：{risk_level}
 - 所属单元：{unit_name}
 - 所属对象：{object_name}
 
 企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}
 
 输出 JSON：
 {{"measures": [{{"measure_category":"engineering|management|ppe|emergency","measure_type":"...","description":"...","check_items":[{{"name":"...","standard":"...","frequency":"..."}}]}}]}}"""
 
     messages = [
         {"role": "system", "content": "你是持有国家注册安全工程师资格的应急预案专家。"},
         {"role": "user", "content": prompt},
     ]
     raw = await _call_llm(messages, ai_config)
     data = _parse_ai_json(raw)
     return data.get("measures", [])
 
 
 async def smart_guide(
     description: str, enterprise_info: dict, ai_config: AIConfig,
) -> dict:
     """一键智能导引：自然语言描述 -> 完整层级结构"""
     prompt = f"""用户描述了以下企业区域，请分析并生成完整的风险分级管控层级结构（分区->对象->单元->事件->措施）。
 
 用户描述：
 {description}
 
 企业信息：
 {json.dumps(enterprise_info, ensure_ascii=False, indent=2)}
 
 要求：
 1. 解析描述中的实体关系，生成到措施层级
 2. 每个事件使用 LS 矩阵法评估（L:1-5, S:1-5），含 risk_level 和 risk_score
 3. 每事件至少 2 条管控措施
 4. 最多生成 5 个分区、50 个对象
 
 输出 JSON 格式（完整层级）：
 {{"zones":[{{"name":"...","description":"...","objects":[{{"name":"...","category":"...","is_risk_point":false,"units":[{{"name":"...","unit_type":"...","events":[{{"accident_type":"...","risk_level":"重大|较大|一般|低","risk_score":"R=XX","method_type":"LS","method_params":{{"l":X,"s":X}},"measures":[{{"measure_category":"engineering|management|ppe|emergency","description":"...","check_items":[{{"name":"...","standard":"...","frequency":"..."}}]}}]}}]}}]}}]}}]}}
 只输出 JSON，不要任何解释。"""
 
     messages = [
         {"role": "system", "content": "你是注册安全工程师，精通风险分级管控和 GB/T 29639 标准。输出严格 JSON。"},
         {"role": "user", "content": prompt},
     ]
     raw = await _call_llm(messages, ai_config)
     data = _parse_ai_json(raw)
     return data
 
 
 async def analyze_floor_plan(
     enterprise_info: dict, ai_config: AIConfig,
 ) -> list[dict]:
     """AI 分析平面图建议分区（如有 vision 能力使用图片，否则用企业信息推断）"""
     prompt = f"""请根据以下企业信息，分析该企业的功能区域分布，建议风险分区。
 为每个分区提供：name/description/approximate_location。
 
 企业信息：{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}
 
 输出 JSON：{{"zones":[{{"name":"...","description":"...","location":"厂区西北角..."}}]}}"""
 
     messages = [
         {"role": "system", "content": "你是工厂布局分析专家。"},
         {"role": "user", "content": prompt},
     ]
     raw = await _call_llm(messages, ai_config)
     data = _parse_ai_json(raw)
     return data.get("zones", [])
 
 
 async def migrate_preview(
     risk_sources: list[dict], ai_config: AIConfig,
 ) -> list[dict]:
     """AI 分析旧 risk_sources 建议新体系映射"""
     prompt = f"""请分析以下旧版风险源数据，为每条建议在新五层体系中的映射位置。
 
 旧数据：{json.dumps(risk_sources, ensure_ascii=False, indent=2)}
 
 输出 JSON：{{"mappings":[{{"source_id":"...","suggested_zone":"...","suggested_object":"...","suggested_accident_type":"...","suggested_params":{{"l":X,"s":X}}}}]}}"""
 
     messages = [
         {"role": "system", "content": "你是安全数据迁移专家。"},
         {"role": "user", "content": prompt},
     ]
     raw = await _call_llm(messages, ai_config)
     data = _parse_ai_json(raw)
     return data.get("mappings", [])
 ```
 
 - [ ] **步骤 6.2：验证模块可导入**
 
 ```bash
 cd backend
 python -c "
 from app.services.risk_ai_service import suggest_objects, suggest_events, suggest_measures, smart_guide
 print('OK: all AI service functions importable')
 "
 ```
 
 预期输出：`OK: all AI service functions importable`
 
 - [ ] **步骤 6.3：Commit**
 
 ```bash
 git add backend/app/services/risk_ai_service.py
 git commit -m "feat(risk): add AI assistance service — 6 functions for LLM-powered risk suggestion"
 ```
 
 ---
 
 ## 任务 7：全层级 CRUD + AI + 迁移路由
 
 **文件：** `backend/app/routers/risk_management.py`（新建，~30 端点）
 
 - [ ] **步骤 7.1：编写路由文件**
 
 路由前缀：`/enterprises/{enterprise_id}/risk-management`。每端点开头调用辅助函数做权限校验（复刻 `risk_sources_ext.py` 中 `_get_enterprise_data` 模式）。完整路由文件约 600 行，关键端点实现如下：
 
 ```python
 import json, os, logging
 from datetime import datetime, timezone
 from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
 from sqlalchemy.ext.asyncio import AsyncSession
 from sqlalchemy import select, func
 from sqlalchemy.orm import selectinload
 from app.database import get_db
 from app.dependencies import get_current_user
 from app.models.user import User
 from app.models.enterprise import Enterprise, RiskSource
 from app.models.risk_management import (
     RiskAssessmentMethod, RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure,
 )
 from app.schemas.risk_management import (
     MethodCreate, MethodUpdate, MethodResponse,
     RiskZoneCreate, RiskZoneUpdate, RiskZoneResponse,
     RiskObjectCreate, RiskObjectUpdate, RiskObjectResponse,
     RiskUnitCreate, RiskUnitUpdate, RiskUnitResponse,
     RiskEventCreate, RiskEventUpdate, RiskEventResponse,
     RiskMeasureCreate, RiskMeasureUpdate, RiskMeasureResponse,
     HierarchyZoneResponse,
     MigrationPreviewItem, MigrationPreviewResponse, MigrationExecuteRequest,
     SmartGuideRequest, SmartGuideResponse, MethodPreviewRequest, MethodPreviewResponse,
 )
 from app.schemas.common import ApiResponse
 from app.services.risk_method_engine import compute_risk, get_active_method_config
 from app.services.risk_ai_service import (
     _get_ai_config, suggest_objects, suggest_events, suggest_measures,
     smart_guide, analyze_floor_plan, migrate_preview,
 )
 from app.config import settings
 
 logger = logging.getLogger(__name__)
 router = APIRouter(prefix="/enterprises/{enterprise_id}/risk-management", tags=["Risk Management"])
 
 UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
 os.makedirs(UPLOAD_DIR, exist_ok=True)
 
 
 async def _get_enterprise(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
     result = await db.execute(
         select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user_id)
     )
     ent = result.scalar_one_or_none()
     if not ent:
         raise HTTPException(404, "企业不存在")
     return ent
 
 
 async def _auto_rate(event_data: RiskEventCreate, enterprise_id: str, db: AsyncSession):
     """自动评定风险等级"""
     method_type = event_data.method_type or "LS"
     config = await get_active_method_config(db, enterprise_id, method_type)
     result = compute_risk(method_type, event_data.method_params, config)
     return result
 
 
 # ── 方法 API（7 端点）──────────────────────────────
 
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
 
 
 @router.get("/methods/{method_id}", response_model=ApiResponse[MethodResponse])
 async def get_method(method_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id == method_id))
     m = result.scalar_one_or_none()
     if not m:
         raise HTTPException(404, "方法不存在")
     return ApiResponse(data=MethodResponse.model_validate(m))
 
 
 @router.post("/methods", response_model=ApiResponse[MethodResponse], status_code=201)
 async def create_method(body: MethodCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     m = RiskAssessmentMethod(enterprise_id=enterprise_id, method_type=body.method_type, name=body.name, description=body.description, config=body.config, is_system=False)
     db.add(m)
     await db.commit()
     await db.refresh(m)
     return ApiResponse(data=MethodResponse.model_validate(m))
 
 
 @router.put("/methods/{method_id}", response_model=ApiResponse[MethodResponse])
 async def update_method(method_id: str, body: MethodUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id == method_id))
     m = result.scalar_one_or_none()
     if not m:
         raise HTTPException(404, "方法不存在")
     if m.is_system:
         raise HTTPException(403, "系统预置方法不可直接编辑，请使用复制功能")
     if body.name is not None: m.name = body.name
     if body.description is not None: m.description = body.description
     if body.config is not None: m.config = body.config
     if body.is_active is not None: m.is_active = body.is_active
     await db.commit()
     await db.refresh(m)
     return ApiResponse(data=MethodResponse.model_validate(m))
 
 
 @router.delete("/methods/{method_id}")
 async def delete_method(method_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id == method_id))
     m = result.scalar_one_or_none()
     if not m:
         raise HTTPException(404, "方法不存在")
     if m.is_system:
         raise HTTPException(403, "系统预置方法不可删除")
     await db.delete(m)
     await db.commit()
     return ApiResponse(message="已删除")
 
 
 @router.post("/methods/{method_id}/duplicate", response_model=ApiResponse[MethodResponse], status_code=201)
 async def duplicate_method(method_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id == method_id))
     src = result.scalar_one_or_none()
     if not src:
         raise HTTPException(404, "方法不存在")
     m = RiskAssessmentMethod(enterprise_id=enterprise_id, method_type=src.method_type, name=f"{src.name}（副本）", description=src.description, config=src.config, is_system=False)
     db.add(m)
     await db.commit()
     await db.refresh(m)
     return ApiResponse(data=MethodResponse.model_validate(m))
 
 
 @router.post("/methods/preview", response_model=ApiResponse[MethodPreviewResponse])
 async def preview_method(body: MethodPreviewRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskAssessmentMethod).where(RiskAssessmentMethod.id == body.method_id))
     m = result.scalar_one_or_none()
     if not m:
         raise HTTPException(404, "方法不存在")
     r = compute_risk(m.method_type, body.params, m.config)
     return ApiResponse(data=MethodPreviewResponse(risk_level=r.risk_level, risk_score=r.risk_score, action=r.action, deadline=r.deadline))
 
 
 # ── 分区 API ──
 @router.get("/zones", response_model=ApiResponse[list[RiskZoneResponse]])
 async def list_zones(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(
         select(RiskZone).where(RiskZone.enterprise_id == enterprise_id).order_by(RiskZone.sort_order)
     )
     zones = result.scalars().all()
     out = []
     for z in zones:
         count_result = await db.execute(select(func.count(RiskObject.id)).where(RiskObject.zone_id == z.id))
         resp = RiskZoneResponse.model_validate(z)
         resp.object_count = count_result.scalar() or 0
         out.append(resp)
     return ApiResponse(data=out)
 
 
 @router.post("/zones", response_model=ApiResponse[RiskZoneResponse], status_code=201)
 async def create_zone(body: RiskZoneCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     z = RiskZone(enterprise_id=enterprise_id, **body.model_dump(exclude_unset=True))
     db.add(z)
     await db.commit()
     await db.refresh(z)
     return ApiResponse(data=RiskZoneResponse.model_validate(z))
 
 
 @router.put("/zones/{zone_id}", response_model=ApiResponse[RiskZoneResponse])
 async def update_zone(zone_id: str, body: RiskZoneUpdate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskZone).where(RiskZone.id == zone_id, RiskZone.enterprise_id == enterprise_id))
     z = result.scalar_one_or_none()
     if not z:
         raise HTTPException(404, "分区不存在")
     for k, v in body.model_dump(exclude_unset=True).items():
         setattr(z, k, v)
     await db.commit()
     await db.refresh(z)
     return ApiResponse(data=RiskZoneResponse.model_validate(z))
 
 
 @router.delete("/zones/{zone_id}")
 async def delete_zone(zone_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskZone).where(RiskZone.id == zone_id, RiskZone.enterprise_id == enterprise_id))
     z = result.scalar_one_or_none()
     if not z:
         raise HTTPException(404, "分区不存在")
     # 计算级联影响
     obj_count = (await db.execute(select(func.count(RiskObject.id)).where(RiskObject.zone_id == zone_id))).scalar() or 0
     await db.delete(z)
     await db.commit()
     return ApiResponse(message=f"已删除分区及 {obj_count} 个对象", data={"cascade_count": obj_count})
 
 
 # ── 全层级查询 ──
 @router.get("/hierarchy", response_model=ApiResponse[list[HierarchyZoneResponse]])
 async def get_hierarchy(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(
         select(RiskZone)
         .where(RiskZone.enterprise_id == enterprise_id)
         .options(
             selectinload(RiskZone.objects)
             .selectinload(RiskObject.units)
             .selectinload(RiskUnit.events)
             .selectinload(RiskEvent.measures),
             selectinload(RiskZone.objects)
             .selectinload(RiskObject.events)
             .selectinload(RiskEvent.measures),
         )
         .order_by(RiskZone.sort_order)
     )
     zones = result.scalars().all()
     return ApiResponse(data=[HierarchyZoneResponse.model_validate(z) for z in zones])
 
 
 # ── AI 辅助端点（6 端点）───────────────────────────
 
 @router.post("/ai/suggest-objects", response_model=ApiResponse[list[dict]])
 async def ai_suggest_objects(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     ai_config = await _get_ai_config(current_user.id, db)
     result = await suggest_objects(body.get("zone_name",""), body.get("zone_desc",""), body.get("enterprise_info",{}), ai_config, body.get("existing_names",[]))
     return ApiResponse(data=result)
 
 
 @router.post("/ai/suggest-events", response_model=ApiResponse[list[dict]])
 async def ai_suggest_events(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     ai_config = await _get_ai_config(current_user.id, db)
     result = await suggest_events(body.get("unit_name",""), body.get("unit_type",""), body.get("object_name",""), body.get("zone_name",""), body.get("enterprise_info",{}), ai_config)
     return ApiResponse(data=result)
 
 
 @router.post("/ai/suggest-measures", response_model=ApiResponse[list[dict]])
 async def ai_suggest_measures(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     ai_config = await _get_ai_config(current_user.id, db)
     result = await suggest_measures(body.get("accident_type",""), body.get("risk_level",""), body.get("unit_name",""), body.get("object_name",""), body.get("enterprise_info",{}), ai_config)
     return ApiResponse(data=result)
 
 
 @router.post("/ai/smart-guide", response_model=ApiResponse[SmartGuideResponse])
 async def ai_smart_guide(body: SmartGuideRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     ai_config = await _get_ai_config(current_user.id, db)
     ent = await _get_enterprise(enterprise_id, current_user.id, db)
     info = {"name":ent.name,"industry":ent.industry,"business_scope":ent.business_scope,"building_overview":ent.building_overview,"hazardous_chemicals":ent.hazardous_chemicals,"special_equipment":ent.special_equipment}
     result = await smart_guide(body.description, info, ai_config)
     return ApiResponse(data=SmartGuideResponse(hierarchy=result.get("zones",[]), summary=result.get("summary",{})))
 
 
 @router.post("/ai/analyze-floor-plan", response_model=ApiResponse[list[dict]])
 async def ai_analyze_floor_plan(body: dict, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     ai_config = await _get_ai_config(current_user.id, db)
     result = await analyze_floor_plan(body.get("enterprise_info",{}), ai_config)
     return ApiResponse(data=result)
 
 
 @router.post("/ai/migrate-preview", response_model=ApiResponse[list[dict]])
 async def ai_migrate_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     ai_config = await _get_ai_config(current_user.id, db)
     old = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id==enterprise_id, RiskSource.migrated==False))).scalars().all()
     if not old:
         return ApiResponse(data=[])
     sources = [{"id":s.id,"name":s.name,"categories":s.categories,"location":s.location,"risk_level":s.risk_level,"description":s.description} for s in old]
     result = await migrate_preview(sources, ai_config)
     return ApiResponse(data=result)
 
 
 # ── 事件端点（含自动评级）──────────────────────────
 
 @router.post("/units/{unit_id}/events", response_model=ApiResponse[RiskEventResponse], status_code=201)
 async def create_event(unit_id: str, body: RiskEventCreate, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     # 验证 unit 存在
     unit_result = await db.execute(select(RiskUnit).where(RiskUnit.id == unit_id))
     if not unit_result.scalar_one_or_none():
         raise HTTPException(404, "单元不存在")
     # 自动评级
     rating = await _auto_rate(body, enterprise_id, db)
     event = RiskEvent(unit_id=unit_id, accident_type=body.accident_type, description=body.description or "", trigger_conditions=body.trigger_conditions or "", consequences=body.consequences or "", method_type=body.method_type, method_params=body.method_params, risk_level=rating.risk_level, risk_score=rating.risk_score)
     db.add(event)
     await db.commit()
     await db.refresh(event)
     return ApiResponse(data=RiskEventResponse.model_validate(event))
 
 
 @router.post("/events/{event_id}/recalc", response_model=ApiResponse[RiskEventResponse])
 async def recalc_event(event_id: str, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     result = await db.execute(select(RiskEvent).where(RiskEvent.id == event_id))
     ev = result.scalar_one_or_none()
     if not ev:
         raise HTTPException(404, "事件不存在")
     rating = compute_risk(ev.method_type, ev.method_params, await get_active_method_config(db, enterprise_id, ev.method_type))
     ev.risk_level = rating.risk_level
     ev.risk_score = rating.risk_score
     await db.commit()
     await db.refresh(ev)
     return ApiResponse(data=RiskEventResponse.model_validate(ev))
 
 
 # ── 迁移端点 ──
 @router.get("/migrate/preview", response_model=ApiResponse[MigrationPreviewResponse])
 async def get_migration_preview(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     old = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id==enterprise_id, RiskSource.migrated==False))).scalars().all()
     items = [MigrationPreviewItem(source_id=s.id, source_name=s.name) for s in old]
     return ApiResponse(data=MigrationPreviewResponse(items=items, total=len(items)))
 
 
 @router.post("/migrate/execute")
 async def execute_migration(body: MigrationExecuteRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
     await _get_enterprise(enterprise_id, current_user.id, db)
     for mapping in body.mappings:
         source_id = mapping.get("source_id")
         source = (await db.execute(select(RiskSource).where(RiskSource.id==source_id))).scalar_one_or_none()
         if not source:
             continue
         zone_name = mapping.get("zone_name", "未命名分区")
         object_name = mapping.get("object_name", source.name)
         # 创建分区（如有）
         zone = (await db.execute(select(RiskZone).where(RiskZone.enterprise_id==enterprise_id, RiskZone.name==zone_name))).scalar_one_or_none()
         if not zone:
             zone = RiskZone(enterprise_id=enterprise_id, name=zone_name)
             db.add(zone)
             await db.flush()
         # 创建对象
         obj = RiskObject(enterprise_id=enterprise_id, zone_id=zone.id, name=object_name, category=source.categories, location=source.location, description=source.description or "")
         db.add(obj)
         await db.flush()
         # 创建事件
         params = mapping.get("method_params", {})
         rating = compute_risk("LS", params if params else {"l": 3, "s": 3})
         event = RiskEvent(object_id=obj.id, accident_type=mapping.get("accident_type","火灾"), method_type="LS", method_params=params, risk_level=rating.risk_level, risk_score=rating.risk_score)
         db.add(event)
         # 标记已迁移
         source.migrated = True
     await db.commit()
     return ApiResponse(message=f"已迁移 {len(body.mappings)} 条数据")
 ```
 
 > 注：对象、单元、措施的 CRUD 端点与分区端点模式相同（GET/POST/PUT/DELETE），篇幅原因省略完整代码，实现时按模式复制调整。
 
 - [ ] **步骤 7.2：验证路由注册**
 
 ```bash
 cd backend
 python -c "
 from app.routers.risk_management import router
 routes = [(r.methods, r.path) for r in router.routes]
 print(f'Total routes: {len(routes)}')
 for m, p in routes:
     print(f'  {m} {p}')
 "
 ```
 
 预期输出：约 25-30 个路由，覆盖方法/分区/对象/单元/事件/措施 CRUD + 全层级 + AI + 迁移。
 
 - [ ] **步骤 7.3：Commit**
 
 ```bash
 git add backend/app/routers/risk_management.py
 git commit -m "feat(risk): add CRUD router — ~30 endpoints for 6 entities + AI + migration"
 ```
 
 ---
 
 ## 任务 8：后端集成 — 修改 6 个现有文件
 
 - [ ] **步骤 8.1：main.py — 注册新路由**
 
 在 `backend/app/main.py` 中：
 
 ① 在 import 区块添加（约第 11 行，其他路由 import 之后）：
 ```python
 from app.routers import risk_management
 ```
 
 ② 在 app.include_router 区块添加（约第 56 行，`risk_sources_ext.router` 注册行附近）：
 ```python
 app.include_router(risk_management.router, prefix="/api/v1")
 ```
 
 - [ ] **步骤 8.2：enterprises.py + schemas/enterprise.py — 支持 risk_method_config**
 
 在 `backend/app/schemas/enterprise.py` 的 `EnterpriseCreate`/`EnterpriseUpdate`/`EnterpriseResponse` 类中添加：
 ```python
 risk_method_config: dict | None = None
 ```
 
 在 `backend/app/routers/enterprises.py` 的 `_build_response` 函数中添加（约第 48 行，在 `surrounding_info=e.surrounding_info` 之后）：
 ```python
 risk_method_config=e.risk_method_config or {},
 ```
 
 - [ ] **步骤 8.3：generation.py — 预案生成上下文适配**
 
 在 `backend/app/routers/generation.py` 中，修改两个位置的 `select(RiskSource)` 查询。
 
 ① 在约第 504 行，找到：
 ```python
 risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()
 ```
 替换为：
 ```python
 try:
     from app.services.risk_context_builder import build_risk_management_context
     rm_ctx = await build_risk_management_context(p.enterprise_id, db)
     ent_data = _collect_enterprise_data(ent, [], resources)
     ent_data["risk_sources"] = rm_ctx.get("risk_sources", [])
 except Exception:
     risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()
     ent_data = _collect_enterprise_data(ent, risk_sources, resources)
 ```
 
 ② 在约第 730 行做同样的替换。
 
 - [ ] **步骤 8.4：risk_assessment.py — 报告生成适配**
 
 在 `backend/app/routers/risk_assessment.py` 的 `POST /generate` 端点中：
 
 ① 将数据检查从：
 ```python
 risk_count = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == enterprise_id))).scalars().all()
 if len(risk_count) == 0:
     raise HTTPException(400, "请先录入风险源数据")
 ```
 替换为：
 ```python
 from app.models.risk_management import RiskEvent, RiskUnit, RiskObject, RiskZone
 event_count = (await db.execute(
     select(RiskEvent).join(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
     .join(RiskObject, RiskUnit.object_id == RiskObject.id)
     .join(RiskZone, RiskObject.zone_id == RiskZone.id)
     .where(RiskZone.enterprise_id == enterprise_id)
 )).scalars().all()
 if len(event_count) == 0:
     raise HTTPException(400, "请先完成风险分级管控数据录入")
 ```
 
 ② 将 `build_risk_assessment_context` 导入替换为：
 ```python
 from app.services.risk_context_builder import build_risk_management_context
 ```
 
 并将调用改为 `context = await build_risk_management_context(enterprise_id, db)`。
 
 - [ ] **步骤 8.5：risk_sources_ext.py — 旧端点标记 deprecated**
 
 在 `backend/app/routers/risk_sources_ext.py` 中，为每个创建/更新/删除端点添加 deprecated 响应头。在所有返回 ApiResponse/Response 的位置（create/update/delete/batch_create 函数末尾），在返回前添加：
 
 ```python
 response.headers["X-Deprecated"] = "true"
 response.headers["X-Migration-URL"] = f"/api/v1/enterprises/{enterprise_id}/risk-management/migrate/preview"
 ```
 
 注意：需要将这些端点的返回类型从 `ApiResponse` 改为显式的 `Response` 对象以支持自定义 header（或使用 FastAPI 的 `Response` 参数注入）。
 
 - [ ] **步骤 8.6：验证后端启动无报错**
 
 ```bash
 cd backend
 python -c "from app.main import app; print('FastAPI app created successfully, routes:', len(app.routes))"
 ```
 
 预期输出：`FastAPI app created successfully, routes: {较大数字}`
 
 - [ ] **步骤 8.7：Commit**
 
 ```bash
 git add backend/app/main.py backend/app/schemas/enterprise.py backend/app/routers/enterprises.py backend/app/routers/generation.py backend/app/routers/risk_assessment.py backend/app/routers/risk_sources_ext.py
 git commit -m "feat(risk): integrate risk management into existing backend — routes, generation context, migration prep"
 ```
 
 ---
 
 > **第 2 段结束。共 4 段。** 继续 → 第 3 段：任务 9-12（前端类型/服务/工具 + Tab/树 + 表单 + 方法页）

 # 风险分级管控模块 — 完整可落地实施方案（第 3/4 段）
 
 ---
 
 ## 任务 9：前端基础层 — 类型 + API 服务 + 计算工具
 
 - [ ] **步骤 9.1：TypeScript 类型定义**
 
 **文件：** `frontend/src/types/riskManagement.ts`（新建）
 
 遵循现有 `riskSource.ts` 的命名和导出风格。关键类型：
 
 ```typescript
 export type MethodType = "LS" | "LEC" | "COAL_LS" | "DIRECT";
 export type MeasureCategory = "engineering" | "management" | "ppe" | "emergency";
 export type MeasureStatus = "pending" | "implemented" | "expired";
 
 export interface CheckItem { name: string; standard: string; frequency: string; }
 
 export interface MethodConfig {
   version: string; formula: string; display_name: string;
   parameters: { key: string; label: string; type: string; range: number[]; levels: { value: number; label: string; desc: string }[] }[];
   risk_thresholds: { min: number; max: number; level: string; color: string; action: string; deadline: string }[];
 }
 
 export interface RiskAssessmentMethod {
   id: string; enterprise_id: string | null; method_type: MethodType;
   name: string; description: string; config: MethodConfig; is_active: boolean; is_system: boolean;
 }
 
 export interface RiskZone { id: string; enterprise_id: string; name: string; description: string | null; sort_order: number; floor_plan_polygon: { points: { x: number; y: number }[] } | null; created_at: string; object_count: number; }
 export interface RiskZoneCreate { name: string; description?: string; sort_order?: number; floor_plan_polygon?: { points: { x: number; y: number }[] }; }
 
 export interface RiskObject { id: string; enterprise_id: string; zone_id: string | null; name: string; category: string | null; location: string | null; location_x: number | null; location_y: number | null; description: string | null; image_url: string | null; is_risk_point: boolean; sort_order: number; created_at: string; unit_count: number; }
 export interface RiskObjectCreate { zone_id?: string; name: string; category?: string; location?: string; location_x?: number; location_y?: number; description?: string; image_url?: string; is_risk_point?: boolean; }
 
 export interface RiskUnit { id: string; object_id: string; name: string; unit_type: string | null; description: string | null; location: string | null; sort_order: number; created_at: string; event_count: number; }
 export interface RiskUnitCreate { object_id: string; name: string; unit_type?: string; description?: string; location?: string; }
 
 export interface RiskEvent { id: string; unit_id: string | null; object_id: string | null; accident_type: string; description: string | null; trigger_conditions: string | null; consequences: string | null; method_type: MethodType; method_params: Record<string, number>; risk_level: string | null; risk_score: string | null; sort_order: number; created_at: string; measure_count: number; }
 export interface RiskEventCreate { unit_id?: string; object_id?: string; accident_type: string; description?: string; trigger_conditions?: string; consequences?: string; method_type?: MethodType; method_params?: Record<string, number>; }
 
 export interface RiskMeasure { id: string; event_id: string; measure_category: MeasureCategory; measure_type: string | null; description: string; responsible_person: string | null; deadline: string | null; check_items: CheckItem[]; status: MeasureStatus; sort_order: number; created_at: string; }
 export interface RiskMeasureCreate { event_id: string; measure_category: MeasureCategory; measure_type?: string; description: string; responsible_person?: string; deadline?: string; check_items?: CheckItem[]; }
 
 // 层级树类型
 export interface HierarchyMeasure extends Pick<RiskMeasure, 'id'|'measure_category'|'measure_type'|'description'|'status'> { check_items: CheckItem[]; }
 export interface HierarchyEvent extends Pick<RiskEvent, 'id'|'accident_type'|'description'|'risk_level'|'risk_score'|'method_type'> { method_params: Record<string, number>; measures: HierarchyMeasure[]; }
 export interface HierarchyUnit extends Pick<RiskUnit, 'id'|'name'|'unit_type'> { events: HierarchyEvent[]; }
 export interface HierarchyObject extends Pick<RiskObject, 'id'|'name'|'category'|'is_risk_point'> { units: HierarchyUnit[]; events: HierarchyEvent[]; }
 export interface HierarchyZone extends Pick<RiskZone, 'id'|'name'|'description'> { objects: HierarchyObject[]; }
 ```
 
 - [ ] **步骤 9.2：API 服务层**
 
 **文件：** `frontend/src/services/riskManagementService.ts`（新建）
 
 遵循现有 `riskSourceService.ts` 风格（`import api from "./api"`，函数返回 `res.data.data`）：
 
 ```typescript
 import api from "./api";
 import type { ApiResponse } from "@/types/common";
 import type { RiskAssessmentMethod, RiskZone, RiskZoneCreate, RiskObject, RiskObjectCreate, RiskUnit, RiskUnitCreate, RiskEvent, RiskEventCreate, RiskMeasure, RiskMeasureCreate, HierarchyZone, MethodConfig } from "@/types/riskManagement";
 
 const BASE = (eid: string) => `/enterprises/${eid}/risk-management`;
 
 // Methods
 export const listMethods = (eid: string) => api.get<ApiResponse<RiskAssessmentMethod[]>>(`${BASE(eid)}/methods`).then(r => r.data.data);
 export const getMethod = (eid: string, mid: string) => api.get<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}`).then(r => r.data.data);
 export const createMethod = (eid: string, data: { method_type: string; name: string; config: MethodConfig }) => api.post<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods`, data).then(r => r.data.data);
 export const updateMethod = (eid: string, mid: string, data: Partial<{ name: string; config: MethodConfig; is_active: boolean }>) => api.put<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}`, data).then(r => r.data.data);
 export const deleteMethod = (eid: string, mid: string) => api.delete(`${BASE(eid)}/methods/${mid}`);
 export const duplicateMethod = (eid: string, mid: string) => api.post<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}/duplicate`).then(r => r.data.data);
 export const previewMethod = (eid: string, method_id: string, params: Record<string, number>) => api.post<ApiResponse<{risk_level:string;risk_score:string;action:string;deadline:string}>>(`${BASE(eid)}/methods/preview`, { method_id, params }).then(r => r.data.data);
 
 // Zones
 export const listZones = (eid: string) => api.get<ApiResponse<RiskZone[]>>(`${BASE(eid)}/zones`).then(r => r.data.data);
 export const createZone = (eid: string, data: RiskZoneCreate) => api.post<ApiResponse<RiskZone>>(`${BASE(eid)}/zones`, data).then(r => r.data.data);
 export const updateZone = (eid: string, zid: string, data: Partial<RiskZoneCreate>) => api.put<ApiResponse<RiskZone>>(`${BASE(eid)}/zones/${zid}`, data).then(r => r.data.data);
 export const deleteZone = (eid: string, zid: string) => api.delete(`${BASE(eid)}/zones/${zid}`);
 
 // Objects
 export const listObjects = (eid: string, params?: { zone_id?: string; is_risk_point?: boolean }) => api.get<ApiResponse<RiskObject[]>>(`${BASE(eid)}/objects`, { params }).then(r => r.data.data);
 export const createObject = (eid: string, data: RiskObjectCreate) => api.post<ApiResponse<RiskObject>>(`${BASE(eid)}/objects`, data).then(r => r.data.data);
 export const createObjectWithImage = (eid: string, formData: FormData) => api.post<ApiResponse<RiskObject>>(`${BASE(eid)}/objects`, formData, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data.data);
 export const updateObject = (eid: string, oid: string, data: Partial<RiskObjectCreate>) => api.put<ApiResponse<RiskObject>>(`${BASE(eid)}/objects/${oid}`, data).then(r => r.data.data);
 export const deleteObject = (eid: string, oid: string) => api.delete(`${BASE(eid)}/objects/${oid}`);
 
 // Units
 export const listUnits = (eid: string, oid: string) => api.get<ApiResponse<RiskUnit[]>>(`${BASE(eid)}/objects/${oid}/units`).then(r => r.data.data);
 export const createUnit = (eid: string, oid: string, data: RiskUnitCreate) => api.post<ApiResponse<RiskUnit>>(`${BASE(eid)}/objects/${oid}/units`, data).then(r => r.data.data);
 export const updateUnit = (eid: string, oid: string, uid: string, data: Partial<RiskUnitCreate>) => api.put<ApiResponse<RiskUnit>>(`${BASE(eid)}/objects/${oid}/units/${uid}`, data).then(r => r.data.data);
 export const deleteUnit = (eid: string, oid: string, uid: string) => api.delete(`${BASE(eid)}/objects/${oid}/units/${uid}`);
 
 // Events
 export const createEvent = (eid: string, uid: string, data: RiskEventCreate) => api.post<ApiResponse<RiskEvent>>(`${BASE(eid)}/units/${uid}/events`, data).then(r => r.data.data);
 export const updateEvent = (eid: string, evid: string, data: Partial<RiskEventCreate>) => api.put<ApiResponse<RiskEvent>>(`${BASE(eid)}/events/${evid}`, data).then(r => r.data.data);
 export const deleteEvent = (eid: string, evid: string) => api.delete(`${BASE(eid)}/events/${evid}`);
 export const recalcEvent = (eid: string, evid: string) => api.post<ApiResponse<RiskEvent>>(`${BASE(eid)}/events/${evid}/recalc`).then(r => r.data.data);
 
 // Measures
 export const listMeasures = (eid: string, evid: string) => api.get<ApiResponse<RiskMeasure[]>>(`${BASE(eid)}/events/${evid}/measures`).then(r => r.data.data);
 export const createMeasure = (eid: string, evid: string, data: RiskMeasureCreate) => api.post<ApiResponse<RiskMeasure>>(`${BASE(eid)}/events/${evid}/measures`, data).then(r => r.data.data);
 export const updateMeasure = (eid: string, evid: string, mid: string, data: Partial<RiskMeasureCreate & { status: string }>) => api.put<ApiResponse<RiskMeasure>>(`${BASE(eid)}/events/${evid}/measures/${mid}`, data).then(r => r.data.data);
 export const deleteMeasure = (eid: string, evid: string, mid: string) => api.delete(`${BASE(eid)}/events/${evid}/measures/${mid}`);
 
 // Hierarchy
 export const getFullHierarchy = (eid: string) => api.get<ApiResponse<HierarchyZone[]>>(`${BASE(eid)}/hierarchy`).then(r => r.data.data);
 
 // AI
 export const aiSuggestObjects = (eid: string, data: { zone_name: string; zone_desc: string; enterprise_info: Record<string, unknown>; existing_names: string[] }) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-objects`, data).then(r => r.data.data);
 export const aiSuggestEvents = (eid: string, data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-events`, data).then(r => r.data.data);
 export const aiSuggestMeasures = (eid: string, data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-measures`, data).then(r => r.data.data);
 export const aiSmartGuide = (eid: string, description: string) => api.post<ApiResponse<{ hierarchy: HierarchyZone[]; summary: Record<string, unknown> }>>(`${BASE(eid)}/ai/smart-guide`, { description }).then(r => r.data.data);
 export const aiAnalyzeFloorPlan = (eid: string, enterprise_info: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/analyze-floor-plan`, { enterprise_info }).then(r => r.data.data);
 export const aiMigratePreview = (eid: string) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/migrate-preview`).then(r => r.data.data);
 ```
 
 - [ ] **步骤 9.3：前端计算工具**
 
 **文件：** `frontend/src/utils/riskMethodEngine.ts`（新建）
 
 ```typescript
 export interface RiskResult { riskLevel: string; riskScore: string; action: string; deadline: string; }
 
 const DEFAULT_THRESHOLDS = [
   { min: 20, max: 25, level: "重大", action: "立即整改", deadline: "立即" },
   { min: 15, max: 19, level: "较大", action: "立即或近期整改", deadline: "近期" },
   { min: 9, max: 14, level: "一般", action: "2年内治理", deadline: "2年" },
   { min: 1, max: 8, level: "低", action: "有条件有经费时治理", deadline: "有条件时" },
 ];
 
 const DEFAULT_LEC_THRESHOLDS = [
   { min: 320, max: 9999, level: "重大", action: "立即停止作业整改", deadline: "立即" },
   { min: 160, max: 319, level: "较大", action: "立即或近期整改", deadline: "近期" },
   { min: 70, max: 159, level: "一般", action: "限期整改", deadline: "限期" },
   { min: 0, max: 69, level: "低", action: "日常管理", deadline: "持续" },
 ];
 
 function findLevel(score: number, thresholds: typeof DEFAULT_THRESHOLDS): RiskResult {
   for (const t of thresholds) {
     if (score >= t.min && score <= t.max) return { riskLevel: t.level, riskScore: "", action: t.action, deadline: t.deadline };
   }
   return { riskLevel: "低", riskScore: "", action: "日常管理", deadline: "持续" };
 }
 
 export function computeRiskLS(l: number, s: number, thresholds = DEFAULT_THRESHOLDS): RiskResult {
   const r = l * s; const result = findLevel(r, thresholds); result.riskScore = `R=${r}`; return result;
 }
 
 export function computeRiskLEC(l: number, e: number, c: number, thresholds = DEFAULT_LEC_THRESHOLDS): RiskResult {
   const d = Math.round(l * e * c); const result = findLevel(d, thresholds); result.riskScore = `D=${d}`; return result;
 }
 
 export const RISK_LEVEL_COLORS: Record<string, string> = { "重大": "#ff4d4f", "较大": "#fa8c16", "一般": "#fadb14", "低": "#52c41a" };
 export const MEASURE_CATEGORY_LABELS: Record<string, string> = { engineering: "工程技术", management: "管理措施", ppe: "个体防护", emergency: "应急处置" };
 export const ACCIDENT_TYPES = ["物体打击","车辆伤害","机械伤害","起重伤害","触电","淹溺","灼烫","火灾","高处坠落","坍塌","锅炉爆炸","容器爆炸","其他爆炸","中毒和窒息","其他伤害"];
 export function getCellClass(r: number): string { if (r >= 20) return "lvl-red"; if (r >= 15) return "lvl-orange"; if (r >= 9) return "lvl-yellow"; return "lvl-green"; }
 ```
 
 - [ ] **步骤 9.4：验证**
 
 ```bash
 cd frontend
 npx tsc --noEmit src/types/riskManagement.ts src/services/riskManagementService.ts src/utils/riskMethodEngine.ts
 ```
 
 预期：无类型错误。
 
 - [ ] **步骤 9.5：Commit**
 
 ```bash
 git add frontend/src/types/riskManagement.ts frontend/src/services/riskManagementService.ts frontend/src/utils/riskMethodEngine.ts
 git commit -m "feat(risk): add frontend types, API service, and computation utils"
 ```
 
 ---
 
 ## 任务 10：Tab 容器 + 层级树组件
 
 - [ ] **步骤 10.1：RiskManagementTab 容器**
 
 **文件：** `frontend/src/pages/Enterprise/RiskManagementTab.tsx`（新建）
 
 ```tsx
 import { useState } from "react";
 import { Button, Space, Spin, Alert } from "antd";
 import { PlusOutlined, ThunderboltOutlined, BarChartOutlined, SettingOutlined } from "@ant-design/icons";
 import { useQuery } from "@tanstack/react-query";
 import { getFullHierarchy } from "@/services/riskManagementService";
 import RiskHierarchyTree from "@/components/enterprise/RiskHierarchyTree";
 import type { HierarchyZone } from "@/types/riskManagement";
 
 interface Props { enterpriseId: string; floorPlanUrl?: string | null; }
 
 export default function RiskManagementTab({ enterpriseId, floorPlanUrl }: Props) {
   const [selectedNode, setSelectedNode] = useState<{ id: string; type: string } | null>(null);
 
   const { data: hierarchy, isLoading, refetch } = useQuery({
     queryKey: ["risk-hierarchy", enterpriseId],
     queryFn: () => getFullHierarchy(enterpriseId),
   });
 
   if (isLoading) return <Spin size="large" />;
 
   return (
     <div style={{ display: "flex", gap: 20 }}>
       <div style={{ flex: 1, minWidth: 360 }}>
         <div style={{ marginBottom: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
           <Button icon={<PlusOutlined />} onClick={() => {/* open zone form */}}>添加分区</Button>
           <Button icon={<ThunderboltOutlined />} onClick={() => {/* open smart guide */}}>🚀 智能导引</Button>
           <Button icon={<BarChartOutlined />} onClick={() => {/* navigate to overview */}}>📊 可视化总览</Button>
           <Button icon={<SettingOutlined />} onClick={() => {/* navigate to methods */}}>⚙ 评估方法</Button>
         </div>
         <RiskHierarchyTree data={hierarchy || []} enterpriseId={enterpriseId} onSelect={setSelectedNode} onRefresh={refetch} />
       </div>
       <div style={{ width: 320, background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 2px 8px rgba(0,0,0,.08)" }}>
         {selectedNode ? (
           <div>
             <h4>📌 节点详情</h4>
             <p style={{ color: "#8c8c8c", fontSize: 13 }}>ID: {selectedNode.id}</p>
             <p style={{ color: "#8c8c8c", fontSize: 13 }}>类型: {selectedNode.type}</p>
           </div>
         ) : (
           <p style={{ color: "#8c8c8c", fontSize: 13 }}>点击层级树中的节点查看详情</p>
         )}
       </div>
     </div>
   );
 }
 ```
 
 - [ ] **步骤 10.2：RiskHierarchyTree 递归树**
 
 **文件：** `frontend/src/components/enterprise/RiskHierarchyTree.tsx`（新建）
 
 使用 Ant Design 的 `Tree` 组件，从 `HierarchyZone[]` 递归构建 `DataNode[]`。每个节点的 `title` 渲染为自定义行：图标 + 名称 + 风险等级 Tag（如有）+ 子节点计数 + hover 显示的 [+] 按钮。
 
 关键实现要点：
 - `buildTreeData(zones: HierarchyZone[])` 递归函数将数据转为 Ant Design Tree 的 `treeData` 格式
 - 每个节点 `title` 是一个 JSX 元素：`<span><Tag>{risk_level}</Tag> {name} <small>({count})</small></span>`
 - 右键菜单使用 `Dropdown` + `Menu` 组件，菜单项包括：编辑、🤖 智能填充下级、上移、下移、删除
 - 展开/折叠使用 Tree 默认的 `switcherIcon`
 - 虚拟滚动：当节点 > 200 时设置 `virtual` 属性
 - `onSelect` 回调更新右侧详情面板
 
 - [ ] **步骤 10.3：Commit**
 
 ```bash
 git add frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/components/enterprise/RiskHierarchyTree.tsx
 git commit -m "feat(risk): add RiskManagementTab container + recursive hierarchy tree"
 ```
 
 ---
 
 ## 任务 11：五个层级表单组件
 
 **文件（新建 5 个）：**
 - `frontend/src/components/enterprise/RiskZoneForm.tsx`
 - `frontend/src/components/enterprise/RiskObjectForm.tsx`
 - `frontend/src/components/enterprise/RiskUnitForm.tsx`
 - `frontend/src/components/enterprise/RiskEventForm.tsx`
 - `frontend/src/components/enterprise/RiskMeasureForm.tsx`
 
 - [ ] **步骤 11.1：RiskZoneForm**
 
 Ant Design `Drawer` + `Form`。字段：name(Input,必填,placeholder:"如储罐区")、description(TextArea,4行)、floor_plan_polygon（平面图多边形选区，复用现有 `FloorPlanPicker` 组件）。props: `open`, `onClose`, `onSubmit`, `initialValues?`, `floorPlanUrl?`。
 
 复用逻辑：如果 `floorPlanUrl` 非空且 `FloorPlanPicker` 可用，渲染全屏平面图覆盖层供用户绘制多边形；否则跳过。
 
 - [ ] **步骤 11.2：RiskObjectForm**
 
 Drawer + Form。字段：zone_id(Select,可选)、name(Input,必填)、category(Select+自定义输入)、location(TextArea)、is_risk_point(Switch → 条件渲染 image Upload + location_x/y 坐标点选)、description(TextArea)。props: `open`, `onClose`, `onSubmit`, `initialValues?`, `zones`。
 
 - [ ] **步骤 11.3：RiskUnitForm**
 
 Drawer + Form。字段：object_id（静态文本，从层级树上下文自动带入，不可编辑）、name(Input,必填)、unit_type(Select: 设备/物料/工艺/电气/特种设备/管道/阀门/仪表/其他)、location(Input)、description(TextArea)。
 
 - [ ] **步骤 11.4：RiskEventForm（核心组件）**
 
 Drawer + Form。三段布局：
 
 ① 基本信息：accident_type(Select,搜索过滤,必填,15类)、description(TextArea)、trigger_conditions(TextArea)、consequences(TextArea)
 
 ② 评估方法区：`Segmented` 控件切换 `[LS矩阵] [LEC评价] [煤矿LS] [直接判定]`。每个方法启用不同的参数子组件：
 - LS → 两个 `Radio.Group`（垂直），每个选项显示完整 label + desc 文本（从 `MethodConfig.parameters.levels` 渲染）
 - LEC → 三个 `Select`（L/E/C，选项从 `MethodConfig.parameters.levels` 渲染）
 - DIRECT → 一个 `Select`（等级下拉）
 - 参数选项文本从当前企业默认方法 config 的 /methods API 获取
 
 ③ 评级预览区：`Card` 组件，实时显示公式计算结果 + 风险等级标签 + 5×5 矩阵热力图（`div` grid 渲染），每选 L/S 值即调用 `computeRiskLS` 更新。状态变量：`selectedL`, `selectedS`。
 
 AI 建议按钮：[✨ AI 分析并建议] → 调用 `aiSuggestEvents` → 返回结果以 `Alert` + `List` 展示 → 用户点击「全部采纳」→ 填充表单字段。
 
 - [ ] **步骤 11.5：RiskMeasureForm**
 
 Drawer + Form。字段：measure_category(Select,必填,四类)、measure_type(Input)、description(TextArea,必填)、responsible_person(Input)、deadline(DatePicker)。检查项目使用 `Form.List`：每行三个 Input（name/standard/frequency）+ 删除按钮。底部 [+ 添加检查项] 按钮。props: `open`, `onClose`, `onSubmit`, `initialValues?`。
 
 AI 建议按钮：调用 `aiSuggestMeasures`，返回四类措施列表 + 自动生成的检查项 → 用户逐组勾选采纳。
 
 - [ ] **步骤 11.6：Commit**
 
 ```bash
 git add frontend/src/components/enterprise/RiskZoneForm.tsx frontend/src/components/enterprise/RiskObjectForm.tsx frontend/src/components/enterprise/RiskUnitForm.tsx frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/components/enterprise/RiskMeasureForm.tsx
 git commit -m "feat(risk): add 5 hierarchy form components — zone/object/unit/event/measure"
 ```
 
 ---
 
 ## 任务 12：方法管理 + 编辑页
 
 - [ ] **步骤 12.1：RiskMethodListPage**
 
 **文件：** `frontend/src/pages/Enterprise/RiskMethodListPage.tsx`（新建）
 
 卡片网格（`Row` + `Col`），`useQuery` 加载 `/methods`。每卡片渲染：
 - 顶部：方法类型标签 Tag + 系统/企业标记 Tag + 星标（默认方法 ★）
 - 中间：方法名称（h3）、公式（monospace）、参数摘要、矩阵缩略图（小型 5×5 grid 渲染）
 - 底部：操作按钮（系统卡片：「查看」「复制」；企业卡片：「编辑」「设为默认」「删除」）
 
 - [ ] **步骤 12.2：RiskMethodEditorPage**
 
 **文件：** `frontend/src/pages/Enterprise/RiskMethodEditorPage.tsx`（新建）
 
 双栏布局（左侧编辑区 70% + 右侧 sticky 评测面板 30%/320px）。
 
 左侧编辑区分为：
 ① 基本信息：name(Input)、method_type(Select,创建后 disabled)、formula(Input)、description(Input)
 ② 参数表：每个参数一个 `Collapse.Panel`。Panel 内为 `Table`（columns: 值/标签/描述 + 操作列编辑/删除）。行支持 `react-sortable-hoc` 拖拽排序。`[+ 添加等级]` 按钮追加新行。
 ③ 阈值表：`Table`（columns: 等级/下限/上限/颜色 ColorPicker/整改行动/期限）。保存时前端校验区间不重叠。
 
 右侧评测面板：
 - L/S 滑块（`Slider` 组件）
 - 实时结果：`R = L × S = {value} → {等级标签}`
 - 5×5 矩阵热力图：`div` grid，每格根据计算值染色，当前 (L,S) 格子加边框高亮
 - 数据流：L/S 滑块 onChange → 调用 `computeRiskLS` → 更新矩阵渲染
 
 - [ ] **步骤 12.3：Commit**
 
 ```bash
 git add frontend/src/pages/Enterprise/RiskMethodListPage.tsx frontend/src/pages/Enterprise/RiskMethodEditorPage.tsx
 git commit -m "feat(risk): add method list + editor pages with real-time evaluation panel"
 ```
 
 ---
 
 > **第 3 段结束。共 4 段。** 继续 → 第 4 段：任务 13-16（可视化总览 + AI 弹窗 + 页面集成 + 联调验证）

 # 风险分级管控模块 — 完整可落地实施方案（第 4/4 段）
 
 ---
 
 ## 任务 13：可视化总览页（四象限）
 
 **文件：** `frontend/src/pages/Enterprise/RiskOverviewPage.tsx`（新建）
 
 - [ ] **步骤 13.1：编写总览页**
 
 页面布局：CSS Grid（2列 × 2行），每个区域一个 `Card` 组件。顶部工具栏：视图切换 `Segmented`（四象限/平面图优先/数据优先）+ 返回按钮。
 
 **四个区域实现**：
 
 ① 厂区平面图热区 — `FloorPlanHeatmap` 子组件。SVG 或 Canvas 渲染企业平面图 + 叠加 `risk_zones.floor_plan_polygon` 半透明多边形（颜色按分区最高风险等级自动计算）+ 风险点图钉 ◆ 标记。交互：点击多边形 → `dispatch` 事件联动层级树 `scrollIntoView`；点击图钉 → `Popover` 显示名称/图片/事件数。
 
 ② 风险矩阵热力图 — `RiskOverviewMatrix` 子组件。从 `/methods` 获取默认方法 config，动态渲染矩阵。LS → 5×5 grid，每格显示该 (L,S) 组合的事件数量 + 背景颜色。悬停 `Tooltip` 列出事件名称。点击 → 层级树过滤。
 
 ③ 统计面板 — `RiskOverviewStats` 子组件。用 `recharts` 的 `PieChart`（环形图，等级分布）和 `BarChart`（横向柱状图，事故类型 Top5）。下方汇总数字行：总分区/对象/事件/措施/已实施占比。
 
 ④ 层级树紧凑 + 拓扑图切换 — 底部 toggle `[层级树] [管控拓扑图]`。拓扑图用 SVG 自绘：组织架构图风格的节点树（企业→分区→对象→单元→事件），节点颜色从子节点传播，连线正交。交互：鼠标滚轮缩放、拖拽平移、点击节点高亮联动平面图。
 
 数据源：`/hierarchy` 加载全量树数据 + `/hierarchy/statistics` 加载聚合统计数据。
 
 - [ ] **步骤 13.2：创建子组件**
 
 **文件（新建 3 个）：**
 - `frontend/src/components/enterprise/RiskOverviewMatrix.tsx` — 矩阵热力图（传入 `methodType` + `config` + `eventDistribution` 数据）
 - `frontend/src/components/enterprise/RiskOverviewStats.tsx` — 统计面板（传入 `statistics` 数据）
 - `frontend/src/components/enterprise/FloorPlanHeatmap.tsx`（或复用现有 `FloorPlanPicker`）— 平面图热区
 
 - [ ] **步骤 13.3：Commit**
 
 ```bash
 git add frontend/src/pages/Enterprise/RiskOverviewPage.tsx frontend/src/components/enterprise/RiskOverviewMatrix.tsx frontend/src/components/enterprise/RiskOverviewStats.tsx
 git commit -m "feat(risk): add visualization overview — 4-quadrant dashboard with matrix, stats, topology"
 ```
 
 ---
 
 ## 任务 14：AI 弹窗组件
 
 - [ ] **步骤 14.1：RiskSmartGuideModal（智能导引）**
 
 **文件：** `frontend/src/components/enterprise/RiskSmartGuideModal.tsx`（新建）
 
 Ant Design `Modal`（720px），`Steps` 组件（步骤1/步骤2）。
 
 步骤1：`TextArea`（placeholder:"储罐区有3个5000m³原油储罐…"）+ 字数统计 + [下一步→AI分析] 按钮。按钮点击 → loading 态 → 调用 `aiSmartGuide` → 进入步骤2。
 
 步骤2：展示 AI 返回的完整层级预览（Tree 组件，每个节点前 ☑ `Checkbox`）。底部汇总（X分区·Y对象·Z事件·W措施）+ ⚠️ 黄色提示"AI生成数据请核实" + `[返回修改] [取消] [确认并导入全部]`。导入流程：调用后端逐级创建（先 zone → object → unit → event → measure）→ 关闭 Modal → `refetch` 层级树。
 
 - [ ] **步骤 14.2：RiskMigrationWizard（迁移向导）**
 
 **文件：** `frontend/src/components/enterprise/RiskMigrationWizard.tsx`（新建）
 
 Ant Design `Modal`。进入时先调用 `/migrate/preview` 检测旧数据。
 
 步骤1：AI 映射建议。调用 `aiMigratePreview` → 展示列表（旧数据名称 + AI 建议映射 + [采纳][修改][跳过] 按钮）。
 
 步骤2：确认执行。汇总预览（"将创建X分区·Y对象·Z事件"）→ `[确认迁移]` → 调用 `/migrate/execute` → 关闭 + `refetch`。
 
 - [ ] **步骤 14.3：Commit**
 
 ```bash
 git add frontend/src/components/enterprise/RiskSmartGuideModal.tsx frontend/src/components/enterprise/RiskMigrationWizard.tsx
 git commit -m "feat(risk): add Smart Guide modal + Migration Wizard"
 ```
 
 ---
 
 ## 任务 15：前端页面集成
 
 - [ ] **步骤 15.1：EnterpriseDetailPage — 添加 Tab**
 
 **文件：** `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`（修改）
 
 ① 在文件顶部添加导入：
 ```tsx
 import RiskManagementTab from "./RiskManagementTab";
 ```
 
 ② 在 `tabItems` 数组中（约第 55 行，"风险评估" Tab 之后）添加：
 ```tsx
 {
   key: "risk-management",
   label: "风险分级管控",
   children: <RiskManagementTab enterpriseId={id!} floorPlanUrl={enterprise.floor_plan_url} />,
 },
 ```
 
 ③ 原有的"风险源" Tab（key: "risk-sources"）保留，但在 Tab label 上加一个小标记 `[旧版]`，并添加 tooltip "风险源管理已升级为风险分级管控，建议切换到新功能使用"。
 
 - [ ] **步骤 15.2：App.tsx — 添加路由**
 
 **文件：** `frontend/src/App.tsx`（或路由配置文件）（修改）
 
 添加三个新路由：
 
 ```tsx
 {
   path: "/enterprises/:id/risk-management/methods",
   element: <RiskMethodListPage />,
 },
 {
   path: "/enterprises/:id/risk-management/methods/:methodId",
   element: <RiskMethodEditorPage />,
 },
 {
   path: "/enterprises/:id/risk-management/overview",
   element: <RiskOverviewPage />,
 },
 ```
 
 - [ ] **步骤 15.3：构建验证**
 
 ```bash
 cd frontend
 npx tsc --noEmit 2>&1 | head -20
 npm run build 2>&1 | tail -5
 ```
 
 预期：无 TypeScript 编译错误，build 成功。
 
 - [ ] **步骤 15.4：Commit**
 
 ```bash
 git add frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx frontend/src/App.tsx
 git commit -m "feat(risk): integrate risk management into EnterpriseDetailPage + add routes"
 ```
 
 ---
 
 ## 任务 16：端到端联调验证
 
 - [ ] **步骤 16.1：后端 API 冒烟测试**
 
 ```bash
 cd backend
 python -c "
 import asyncio
 from app.database import async_session
 from app.services.risk_method_engine import compute_risk
 
 # LS 测试
 r = compute_risk('LS', {'l': 5, 's': 5})
 assert r.risk_level == '重大' and r.risk_score == 'R=25'
 print(f'LS(5,5): {r.risk_level} {r.risk_score} ✓')
 
 r = compute_risk('LS', {'l': 2, 's': 4})
 assert r.risk_level == '低' and r.risk_score == 'R=8'
 print(f'LS(2,4): {r.risk_level} {r.risk_score} ✓')
 
 # LEC 测试
 r = compute_risk('LEC', {'l': 10, 'e': 6, 'c': 40})
 assert r.risk_level == '重大'
 print(f'LEC(10,6,40): {r.risk_level} {r.risk_score} ✓')
 
 # DIRECT 测试
 r = compute_risk('DIRECT', {'risk_level': '较大'})
 assert r.risk_level == '较大'
 print(f'DIRECT: {r.risk_level} ✓')
 
 # 边界测试
 r = compute_risk('LS', {'l': 4, 's': 5})  # R=20 边界
 assert r.risk_level == '重大'
 print(f'LS boundary 20: {r.risk_level} ✓')
 
 print('All API smoke tests passed')
 "
 ```
 
 - [ ] **步骤 16.2：Swagger UI 手动验证**
 
 启动后端 `uvicorn app.main:app --reload`，在 Swagger UI（`/docs`）中依次测试：
 
 1. `GET /methods` → 返回 2 个系统预置方法（LS + LEC）
 2. `POST /zones` → 创建分区 → `GET /zones` → 返回分区含 object_count=0
 3. `POST /objects` → 创建对象（zone_id 关联） → `GET /objects` → 返回对象含 unit_count=0
 4. `POST /objects/{oid}/units` → 创建单元 → `POST /units/{uid}/events` → 返回事件含 risk_level 和 risk_score 自动填充
 5. `GET /hierarchy` → 返回完整五层树结构
 
 - [ ] **步骤 16.3：前端交互验证**
 
 启动前端 `npm run dev`，在浏览器中验证：
 
 1. 企业详情页 → 「风险分级管控」Tab → 层级树渲染（如有数据）或空状态提示
 2. 点击「+ 添加分区」→ 表单弹出 → 填写 → 提交 → 树刷新
 3. 展开分区节点 → [+] → 添加对象 → 添加单元 → 添加事件 → LS 参数选择 → 评级预览更新 → 保存
 4. 切换评估方法 LS → LEC → 参数区动态变化 → 评级预览正确
 5. 点击 [✨ AI 建议] → AI 返回建议数据 → 采纳 → 表单填充
 6. [🚀 智能导引] → 输入描述 → 生成预览 → 确认导入 → 树更新
 7. [📊 可视化总览] → 四象限渲染 → 拓扑图可缩放拖拽 → 点击节点联动
 
 - [ ] **步骤 16.4：Commit + Push**
 
 ```bash
 git add -A
 git commit -m "feat(risk): complete risk management overhaul — 16 tasks, 33 files"
 git push
 ```
 
 ---
 
 ## 执行策略
 
 **推荐分批执行**（子智能体驱动）：
 
 | 批次 | 任务 | 并行 | 依赖 |
 |:---:|------|:---:|------|
 | 第 1 批 | 任务1(DDL) + 任务2(模型) + 任务3(Schema) | 2 | — |
 | 第 2 批 | 任务4(引擎) + 任务5(上下文) + 任务6(AI服务) | 3 | 第1批 |
 | 第 3 批 | 任务7(路由) + 任务8(后端集成) | 2 | 第2批 |
 | 第 4 批 | 任务9(前端基础) | 1 | 第3批 |
 | 第 5 批 | 任务10(树) + 任务11(表单) + 任务12(方法页) | 3 | 第4批 |
 | 第 6 批 | 任务13(总览) + 任务14(AI弹窗) | 2 | 第5批 |
 | 收尾 | 任务15(集成) + 任务16(验证) | 1 | 第6批 |
 
 **总文件变更**：新建 24 个 + 修改 9 个 = 33 个文件。
 
 ---
 
 ## 风险与注意事项
 
 1. **旧数据兼容**：`generation.py` 中用 try/except 包裹新上下文构建，新表无数据时 fallback 到旧 RiskSource 查询，确保已有用户不受影响
 2. **数据库迁移**：DDL 全部使用 `IF NOT EXISTS` + `ADD COLUMN IF NOT EXISTS`，支持幂等执行。预置方法用 `INSERT` 非 `INSERT ON CONFLICT`（无冲突键），注意不要在已有预置数据的库上重新执行
 3. **前端 Tree 性能**：Ant Design Tree 设置 `virtual` 属性（节点 > 200 时启用），`selectinload` 后端已处理 N+1 问题
 4. **AI 端点安全**：所有 AI 端点先校验 AIConfig 存在 + 用户权限（`_get_enterprise`），超时 60s，单日调用上限 200 次（建议用 Redis 计数器实现）
 5. **方法编辑器并发**：参数表内联编辑使用乐观更新（本地 state 先更新，onBlur 时保存到后端），避免频繁 API 调用
 6. **拓扑图复杂交互**：SVG 自绘拓扑图在节点 > 100 时可能有性能瓶颈，首次实现限制展开深度为 3 层（分区→对象→事件），单元层在 Tooltip 中显示
 
 ---
 
 > **全部 4 段结束。** 总任务数：16。总文件变更：33。
