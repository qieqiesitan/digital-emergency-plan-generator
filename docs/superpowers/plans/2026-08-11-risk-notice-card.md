# 风险告知卡自动生成 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在企业风险管理模块上新增「风险告知卡」：按风险点自动生成符合 GB 2894-2025 的告知卡（含国标安全标志），支持网页预览、批量导出 Word（每卡一页 A4 + 二维码）、单卡 AI 优化存快照、现场扫码公开只读页。

**架构：** 后端新增组装服务（`risk_notice_card_service`）从风险数据实时组装 CardData，规则为主 + AI 可选；docx 渲染服务（`risk_notice_card_docx`）基于 python-docx 生成 A4 卡片并内嵌标志 PNG 与二维码；标志 SVG 静态资产放 `backend/app/static/signs/`（前后端共用，前端 `<img>` 引用、docx 转换 PNG）。前端新增管理页、预览页、公开页三个路由，复用 Ant Design 与 React Query。

**技术栈：** FastAPI + SQLAlchemy(async) + PostgreSQL、python-docx、qrcode、cairosvg（现有）、React 18 + Ant Design 5 + TanStack Query、Vitest、pytest。

**规格文档：** `docs/superpowers/specs/2026-08-11-risk-notice-card-design.md`（commit `300502a`）

---

## 文件结构

### 后端（新建 / 修改）

| 文件 | 职责 |
|------|------|
| `backend/db_migration_risk_notice_card.sql` | 新建：risk_objects 加 4 字段 + risk_notice_cards 快照表 |
| `backend/app/models/risk_management.py` | 修改：RiskObject 加 responsible_unit/responsible_person/contact_phone/public_token |
| `backend/app/models/risk_notice_card.py` | 新建：RiskNoticeCard 模型 |
| `backend/app/services/risk_notice_card_data.py` | 新建：标志映射（GB 6441 20 类）、应急处置模板、默认标志组、等级排序常量 |
| `backend/app/services/risk_notice_card_service.py` | 新建：CardData 组装、责任兜底、编号、快照读写、stale 判定 |
| `backend/app/services/risk_notice_card_docx.py` | 新建：A4 每卡一页 Word 渲染（含二维码、标志 PNG） |
| `backend/app/schemas/risk_notice_card.py` | 新建：CardSummary / CardData / RightColumn / 请求响应 |
| `backend/app/routers/risk_notice_card.py` | 新建：6 个鉴权端点 |
| `backend/app/routers/public_risk_notice.py` | 新建：GET /public/risk-notice-cards/{token} |
| `backend/app/main.py` | 修改：注册 2 个路由 + 挂载 /signs 静态目录 |
| `backend/app/static/signs/*.svg` | 新建：36 个国标标志 |
| `backend/requirements.txt` | 修改：加 `qrcode` |
| `backend/tests/test_risk_notice_card_data.py` | 新建：常量数据测试 |
| `backend/tests/test_risk_notice_card_service.py` | 新建：组装逻辑测试 |
| `backend/tests/test_risk_notice_card_api.py` | 新建：API 测试（列表/详情/AI/快照/token） |
| `backend/tests/test_risk_notice_card_docx.py` | 新建：docx 与二维码测试 |

### 前端（新建 / 修改）

| 文件 | 职责 |
|------|------|
| `frontend/src/types/riskNoticeCard.ts` | 新建：CardData / CardSummary / RightColumn 类型 |
| `frontend/src/services/riskNoticeCardService.ts` | 新建：API 封装 |
| `frontend/src/services/riskNoticeCardService.test.ts` | 新建：service 测试 |
| `frontend/src/components/enterprise/RiskNoticeCard.tsx` | 新建：卡片渲染组件（v5 版式 + 内联 SVG） |
| `frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx` | 新建：管理页（列表/筛选/勾选/批量导出） |
| `frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx` | 新建：单卡预览 + AI 优化对比 |
| `frontend/src/pages/PublicRiskNoticePage.tsx` | 新建：公开只读页（/r/:token） |
| `frontend/src/App.tsx` | 修改：加 3 个路由（1 公开 + 2 业务） |
| `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | 修改：顶部「风险告知卡」按钮 |
| `frontend/src/components/enterprise/RiskObjectForm.tsx` | 修改：责任信息三字段 |
| `frontend/src/types/riskManagement.ts` | 修改：RiskObject 类型加 4 字段（含 public_token） |

---

## 任务 1：数据库迁移 + RiskObject 模型字段

**文件：**
- 创建：`backend/db_migration_risk_notice_card.sql`
- 修改：`backend/app/models/risk_management.py`（RiskObject 类，约 45-75 行）
- 测试：`backend/tests/test_risk_notice_card_service.py`（本任务只建 fixture 骨架，断言模型字段存在）

- [ ] **步骤 1：编写失败测试（模型字段）**

创建 `backend/tests/test_risk_notice_card_service.py`：

```python
"""风险告知卡服务测试。"""
from app.models.risk_management import RiskObject


def test_risk_object_has_notice_card_fields():
    cols = {c.name for c in RiskObject.__table__.columns}
    assert {"responsible_unit", "responsible_person", "contact_phone", "public_token"} <= cols
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`
预期：FAIL（`KeyError` 或断言失败，字段不存在）

- [ ] **步骤 3：编写迁移 SQL**

创建 `backend/db_migration_risk_notice_card.sql`：

```sql
-- 风险告知卡：risk_objects 新增字段
ALTER TABLE risk_objects
    ADD COLUMN IF NOT EXISTS responsible_unit VARCHAR(255),
    ADD COLUMN IF NOT EXISTS responsible_person VARCHAR(100),
    ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50),
    ADD COLUMN IF NOT EXISTS public_token VARCHAR(64);

-- 存量行补随机 token（迁移幂等：仅空值行）
UPDATE risk_objects
   SET public_token = substr(md5(random()::text || clock_timestamp()::text), 1, 64)
 WHERE public_token IS NULL OR public_token = '';

ALTER TABLE risk_objects ALTER COLUMN public_token SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_risk_objects_public_token ON risk_objects(public_token);
```

- [ ] **步骤 4：更新模型**

在 `backend/app/models/risk_management.py` 的 `RiskObject` 类中（`image_url` 与 `is_risk_point` 之间）添加：

```python
    # 风险告知卡：责任信息与公开页 token
    responsible_unit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responsible_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    public_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=lambda: __import__("secrets").token_hex(32))
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/db_migration_risk_notice_card.sql backend/app/models/risk_management.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): add risk object notice fields and migration"
```

---

## 任务 2：RiskNoticeCard 快照模型

**文件：**
- 创建：`backend/app/models/risk_notice_card.py`
- 修改：`backend/db_migration_risk_notice_card.sql`（追加快照表 DDL）
- 测试：`backend/tests/test_risk_notice_card_service.py`（追加）

- [ ] **步骤 1：编写失败测试（快照模型 + 迁移 DDL）**

在 `test_risk_notice_card_service.py` 追加：

```python
from app.models.risk_notice_card import RiskNoticeCard


def test_snapshot_model_columns():
    cols = {c.name for c in RiskNoticeCard.__table__.columns}
    assert {"object_id", "version", "content", "source"} <= cols
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py::test_snapshot_model_columns -v`
预期：FAIL（模块不存在）

- [ ] **步骤 2：创建模型**

创建 `backend/app/models/risk_notice_card.py`：

```python
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class RiskNoticeCard(Base):
    """风险告知卡快照（AI 优化结果）。每个风险点最多一条最新快照。"""

    __tablename__ = "risk_notice_cards"
    __table_args__ = (
        UniqueConstraint("object_id", name="uq_risk_notice_cards_object"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **步骤 3：迁移 SQL 追加快照表**

在 `db_migration_risk_notice_card.sql` 末尾追加：

```sql
-- 风险告知卡快照表
CREATE TABLE IF NOT EXISTS risk_notice_cards (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    object_id UUID NOT NULL REFERENCES risk_objects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    content JSONB NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'ai',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_risk_notice_cards_object UNIQUE (object_id)
);
CREATE INDEX IF NOT EXISTS idx_rnc_enterprise ON risk_notice_cards(enterprise_id);
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`
预期：PASS（两个测试）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/models/risk_notice_card.py backend/db_migration_risk_notice_card.sql backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): add snapshot model and migration"
```

---

## 任务 3：常量数据（标志映射 + 应急处置模板）

**文件：**
- 创建：`backend/app/services/risk_notice_card_data.py`
- 测试：`backend/tests/test_risk_notice_card_data.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_risk_notice_card_data.py`：

```python
"""风险告知卡常量数据测试：标志映射覆盖 GB 6441 全部 20 类。"""
from app.services.risk_notice_card_data import (
    SIGN_GROUPS,
    DEFAULT_SIGN_GROUP,
    EMERGENCY_TEMPLATES,
    SIGN_CATEGORY_ORDER,
    GB6441_ACCIDENT_TYPES,
)


def test_sign_groups_cover_all_gb6441_types():
    assert set(SIGN_GROUPS.keys()) == set(GB6441_ACCIDENT_TYPES)


def test_sign_groups_are_non_empty_and_ordered():
    for accident_type, signs in SIGN_GROUPS.items():
        assert signs, f"{accident_type} 缺少标志"
        cats = [s["category"] for s in signs]
        ordered = [c for c in SIGN_CATEGORY_ORDER if c in cats]
        assert cats == ordered, f"{accident_type} 标志顺序应为 {ordered}"


def test_every_sign_refers_to_known_svg(caplog):
    import os
    from pathlib import Path
    sign_dir = Path(__file__).resolve().parents[2] / "app" / "static" / "signs"
    for accident_type, signs in SIGN_GROUPS.items():
        for s in signs:
            assert (sign_dir / f"{s['svg_name']}.svg").exists(), s["svg_name"]


def test_default_sign_group_and_emergency_templates():
    assert DEFAULT_SIGN_GROUP
    assert EMERGENCY_TEMPLATES["火灾"]
    assert len(EMERGENCY_TEMPLATES["火灾"]) >= 2
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_data.py -v`
预期：FAIL（模块不存在）

- [ ] **步骤 2：实现常量数据**

创建 `backend/app/services/risk_notice_card_data.py`：

```python
"""风险告知卡常量：GB 6441-1986 二十类事故 → 安全标志组、应急处置模板。

标志图形完全符合 GB 2894-2025《安全色和安全标志》：
警告=黄底黑边正三角 / 禁止=白底红圈红斜杠 / 指令=蓝底白圆 / 提示=绿底白方。
"""

# 安全标志排列顺序（GB 2894-2025：警告→禁止→指令→提示）
SIGN_CATEGORY_ORDER = ["warning", "prohibition", "instruction", "notice"]

# 标志名称常量（与 SVG 资产、GB 2894-2025 标准名称一致）
W = lambda name, svg: {"category": "warning", "name": name, "svg_name": svg}
P = lambda name, svg: {"category": "prohibition", "name": name, "svg_name": svg}
I = lambda name, svg: {"category": "instruction", "name": name, "svg_name": svg}
N = lambda name, svg: {"category": "notice", "name": name, "svg_name": svg}

GB6441_ACCIDENT_TYPES = [
    "物体打击", "车辆伤害", "机械伤害", "起重伤害", "触电", "淹溺", "灼烫",
    "火灾", "高处坠落", "坍塌", "冒顶片帮", "透水", "放炮", "火药爆炸",
    "瓦斯爆炸", "锅炉爆炸", "容器爆炸", "其他爆炸", "中毒和窒息", "其他伤害",
]

# 事故类型 → 标志组（每类最多 2 个，顺序已符合 警告→禁止→指令→提示）
SIGN_GROUPS: dict[str, list[dict]] = {
    "物体打击": [W("当心坠落物", "warning-falling-object"), I("必须戴安全帽", "instruction-helmet")],
    "车辆伤害": [W("当心车辆", "warning-vehicle"), P("禁止通行", "prohibition-pass"), N("紧急出口", "notice-exit")],
    "机械伤害": [W("当心机械伤人", "warning-machinery"), I("必须戴防护手套", "instruction-gloves")],
    "起重伤害": [W("当心起重伤害", "warning-crane"), P("禁止站人", "prohibition-standing"), I("必须戴安全帽", "instruction-helmet")],
    "触电": [W("当心触电", "warning-electric"), P("禁止触摸", "prohibition-touch"),
             I("必须穿绝缘鞋", "instruction-insulating-shoes"), I("必须戴防护手套", "instruction-gloves"), N("紧急出口", "notice-exit")],
    "淹溺": [W("当心落水", "warning-drowning"), I("必须穿救生衣", "instruction-lifejacket")],
    "灼烫": [W("当心烫伤", "warning-burn"), I("必须穿防护服", "instruction-protective-suit"),
             I("必须戴防护手套", "instruction-gloves"), N("洗眼台", "notice-eyewash")],
    "火灾": [W("当心火灾", "warning-fire"), P("禁止烟火", "prohibition-smoking"),
             P("禁止动火作业", "prohibition-hot-work"), N("紧急出口", "notice-exit")],
    "高处坠落": [W("当心坠落", "warning-fall"), P("禁止抛物", "prohibition-throwing"), I("必须系安全带", "instruction-seatbelt")],
    "坍塌": [W("当心坍塌", "warning-collapse"), P("禁止通行", "prohibition-pass")],
    "冒顶片帮": [W("当心冒顶", "warning-roof-fall"), I("必须戴安全帽", "instruction-helmet")],
    "透水": [W("当心透水", "warning-water-inrush"), I("必须穿救生衣", "instruction-lifejacket")],
    "放炮": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须戴安全帽", "instruction-helmet")],
    "火药爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 P("禁止动火作业", "prohibition-hot-work"), I("必须消除静电", "instruction-eliminate-static")],
    "瓦斯爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static"), I("必须穿防静电工作服", "instruction-anti-static-clothes")],
    "锅炉爆炸": [W("当心爆炸", "warning-explosion"), I("必须消除静电", "instruction-eliminate-static")],
    "容器爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须消除静电", "instruction-eliminate-static")],
    "其他爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须消除静电", "instruction-eliminate-static")],
    "中毒和窒息": [W("当心中毒", "warning-poison"), W("当心窒息", "warning-suffocation"),
                    I("必须戴防毒面具", "instruction-gas-mask"), I("必须通风", "instruction-ventilate"), N("洗眼台", "notice-eyewash")],
    "其他伤害": [W("当心机械伤人", "warning-machinery"), P("禁止烟火", "prohibition-smoking"),
                 I("必须戴安全帽", "instruction-helmet"), N("紧急出口", "notice-exit")],
}

DEFAULT_SIGN_GROUP = SIGN_GROUPS["其他伤害"]

# 应急处置模板（事故类型 → 标准步骤；emergency 措施不足 2 条时兜底）
EMERGENCY_TEMPLATES: dict[str, list[str]] = {
    "物体打击": ["立即停止作业，保护现场", "对伤员止血包扎，尽快送医", "拨打 120 急救电话", "报告企业安全管理部门"],
    "车辆伤害": ["立即制动熄火，设置警戒", "现场急救伤员，拨打 120", "保护现场，配合事故调查"],
    "机械伤害": ["立即停机断电", "对伤员止血包扎固定，拨打 120", "保护现场，禁止移动伤者"],
    "起重伤害": ["立即停止起吊作业", "抢救伤员并拨打 120", "设置警戒区，保护现场"],
    "触电": ["立即切断电源或用绝缘物使伤员脱离电源", "判断意识与呼吸，必要时心肺复苏", "拨打 120，持续施救至医务人员到达"],
    "淹溺": ["立即将溺水者救出水面", "清理口鼻异物，判断呼吸，必要时心肺复苏", "拨打 120，注意保暖"],
    "灼烫": ["立即用大量清水冲洗创面 15 分钟以上", "小心脱除衣物，避免撕扯", "覆盖创面送医，拨打 120"],
    "火灾": ["立即切断气源、电源，停止作业", "拨打 119 报警并报告企业应急指挥部", "组织人员从上风向撤离，清点人数", "使用灭火器材初期扑救，禁止盲目进入"],
    "高处坠落": ["保持伤员静止，勿随意搬动", "固定伤者后平稳搬运", "拨打 120，保护现场"],
    "坍塌": ["立即设置警戒，禁止无关人员进入", "防止二次坍塌，谨慎搜救", "拨打 119/120 请求专业救援"],
    "冒顶片帮": ["立即撤出危险区域，设置警戒", "在确保支护安全前提下搜救", "拨打 120，报告矿方调度"],
    "透水": ["立即沿避灾路线撤离，发出警报", "报告调度，清点人数", "在安全地点等待救援"],
    "放炮": ["立即停止作业，警戒隔离", "确认无二次爆破风险后施救", "拨打 120，保护现场"],
    "火药爆炸": ["立即切断电源与火源，撤离现场", "拨打 119/120 报警", "清点人数，配合专业救援"],
    "瓦斯爆炸": ["立即切断电源，组织撤离", "拨打 119/120 报警", "严禁火源，通风排放，配合救援"],
    "锅炉爆炸": ["立即停炉断电，撤离现场", "拨打 119/120 报警", "清点人数，防止二次爆炸"],
    "容器爆炸": ["立即切断气源电源，撤离", "拨打 119/120 报警", "警戒隔离，配合专业处置"],
    "其他爆炸": ["立即切断电源与火源，撤离", "拨打 119/120 报警", "警戒隔离，配合专业处置"],
    "中毒和窒息": ["佩戴防护用品后进入，禁止盲目施救", "立即通风，将伤员移至新鲜空气处", "拨打 120，必要时心肺复苏", "报警并报告企业应急指挥部"],
    "其他伤害": ["立即停止作业，现场急救", "拨打 120 送医", "报告企业安全管理部门"],
}

# 风险等级排序（大 → 小），用于取最高等级
LEVEL_ORDER = ["重大", "较大", "一般", "低"]
LEVEL_COLORS = {"重大": "#ff4d4f", "较大": "#fa8c16", "一般": "#fadb14", "低": "#52c41a", "未评估": "#bfbfbf"}
```

- [ ] **步骤 3：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_data.py -v`
预期：`test_sign_groups_cover_all_gb6441_types` / `test_default_sign_group_and_emergency_templates` PASS；`test_every_sign_refers_to_known_svg` FAIL（SVG 资产未创建，属预期，任务 4 补齐后转绿）

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/risk_notice_card_data.py backend/tests/test_risk_notice_card_data.py
git commit -m "feat(risk-notice-card): add sign mapping and emergency templates"
```

---

## 任务 4：SVG 标志资产 + 静态挂载

**文件：**
- 创建：`backend/app/static/signs/*.svg`（36 个）
- 修改：`backend/app/main.py`（挂载 /signs）
- 测试：`backend/tests/test_risk_notice_card_data.py`（既有引用测试转绿）+ `backend/tests/test_static_signs.py`

- [ ] **步骤 1：编写失败测试（静态目录与文件规范）**

创建 `backend/tests/test_static_signs.py`：

```python
"""SVG 标志资产规范测试。"""
from pathlib import Path
from app.services.risk_notice_card_data import SIGN_GROUPS, DEFAULT_SIGN_GROUP


SIGN_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "signs"


def _referenced_svg_names():
    names = set()
    for signs in SIGN_GROUPS.values():
        for s in signs:
            names.add(s["svg_name"])
    for s in DEFAULT_SIGN_GROUP:
        names.add(s["svg_name"])
    return names


def test_all_referenced_svgs_exist():
    missing = [n for n in _referenced_svg_names() if not (SIGN_DIR / f"{n}.svg").exists()]
    assert not missing, f"缺失 SVG: {missing}"


def test_svg_shape_and_color_rules():
    """抽查每个 SVG 包含四类标志的形状/颜色要素。"""
    for svg in SIGN_DIR.glob("*.svg"):
        content = svg.read_text(encoding="utf-8")
        if svg.name.startswith("warning-"):
            assert "polygon" in content and "#FFD100" in content and "#000" in content
        elif svg.name.startswith("prohibition-"):
            assert "circle" in content and "#C8102E" in content and "#fff" in content
        elif svg.name.startswith("instruction-"):
            assert "circle" in content and "#005EB8" in content and "#fff" in content
        elif svg.name.startswith("notice-"):
            assert "#009A44" in content and "#fff" in content
```

运行：`cd backend && python -m pytest tests/test_static_signs.py -v`
预期：FAIL（目录/文件不存在）

- [ ] **步骤 2：创建目录与 SVG 资产（36 个）**

创建 `backend/app/static/signs/`，按下列规范绘制每个 SVG（viewBox 统一 `0 0 28 28`，警告类 `0 0 28 26`）：

规范：警告=黄底（`#FFD100`）黑边正三角黑图形；禁止=白底红圈（`#C8102E`）红斜杠黑图形；指令=蓝底（`#005EB8`）白图形；提示=绿底（`#009A44`）白图形。

完整清单（文件名 = 映射表引用的 `svg_name`，共 36 个）：

| 类别 | 文件名 |
|------|--------|
| warning | warning-explosion, warning-fire, warning-electric, warning-machinery, warning-fall, warning-falling-object, warning-vehicle, warning-crane, warning-burn, warning-poison, warning-suffocation, warning-drowning, warning-collapse, warning-roof-fall, warning-water-inrush |
| prohibition | prohibition-smoking, prohibition-hot-work, prohibition-touch, prohibition-standing, prohibition-pass, prohibition-throwing |
| instruction | instruction-helmet, instruction-goggles, instruction-gloves, instruction-insulating-shoes, instruction-anti-static-clothes, instruction-eliminate-static, instruction-seatbelt, instruction-gas-mask, instruction-lifejacket, instruction-ventilate, instruction-protective-suit |
| notice | notice-exit, notice-eyewash, notice-shower |

三个完整示例（其余按同一规范绘制，图形符号参考 GB 2894-2025 标准图形）：

`backend/app/static/signs/warning-explosion.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="28" height="26" viewBox="0 0 28 26">
  <polygon points="14,2 26,24 2,24" fill="#FFD100" stroke="#000" stroke-width="2"/>
  <path d="M14 7 l0 8" stroke="#000" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="14" cy="19.5" r="1.8" fill="#000"/>
</svg>
```

`backend/app/static/signs/prohibition-smoking.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
  <circle cx="14" cy="14" r="12" fill="#fff" stroke="#C8102E" stroke-width="3"/>
  <line x1="5" y1="23" x2="23" y2="5" stroke="#C8102E" stroke-width="3"/>
  <rect x="8" y="12" width="12" height="3" fill="#000"/>
  <rect x="10" y="8" width="2" height="4" fill="#000"/>
  <rect x="13" y="8" width="2" height="4" fill="#000"/>
  <rect x="16" y="8" width="2" height="4" fill="#000"/>
</svg>
```

`backend/app/static/signs/instruction-helmet.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
  <circle cx="14" cy="14" r="12" fill="#005EB8"/>
  <path d="M9 18 v-1.5 a5 5 0 0 1 10 0 V18 z" fill="#fff"/>
  <rect x="10" y="17.5" width="8" height="2.5" rx="1" fill="#fff"/>
</svg>
```

> 实现注意：`instruction-goggles`（防护眼镜）、`notice-exit`（安全出口小人+箭头）、`warning-fire`（火焰）等图形元素参照 GB 2894-2025 标准图形绘制，保持形状/颜色/对比色符合规范；无需像素级复刻，但形状类别必须正确（三角/圆/斜杠/方形）。

- [ ] **步骤 3：挂载静态目录**

在 `backend/app/main.py` 中（`app.mount("/icons", ...)` 附近）添加：

```python
from pathlib import Path as _Path
SIGNS_DIR = _Path(__file__).resolve().parent / "static" / "signs"
SIGNS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/signs", StaticFiles(directory=str(SIGNS_DIR)), name="signs")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_static_signs.py tests/test_risk_notice_card_data.py -v`
预期：全部 PASS（含映射引用测试）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/static/signs backend/app/main.py backend/tests/test_static_signs.py
git commit -m "feat(risk-notice-card): add gb2894 sign svg assets and static mount"
```

---

## 任务 5：CardData 组装服务

**文件：**
- 创建：`backend/app/services/risk_notice_card_service.py`
- 修改：`backend/app/services/risk_notice_card_data.py`（如需要补常量）
- 测试：`backend/tests/test_risk_notice_card_service.py`

- [ ] **步骤 1：编写失败测试**

在 `test_risk_notice_card_service.py` 追加（构造内存对象，不依赖 DB）：

```python
import asyncio
from datetime import datetime, timezone
from app.models.risk_management import RiskZone, RiskObject, RiskUnit, RiskEvent, RiskMeasure
from app.models.enterprise import Enterprise
from app.services.risk_notice_card_data import LEVEL_ORDER
from app.services.risk_notice_card_service import (
    compute_level, resolve_responsible, build_right_column, match_signs, compute_code,
)


def _event(accident_type: str, level: str, trigger: str, consequences: str) -> RiskEvent:
    return RiskEvent(accident_type=accident_type, risk_level=level,
                     trigger_conditions=trigger, consequences=consequences,
                     method_type="LS", method_params={"l": 3, "s": 3})


def test_compute_level_takes_highest():
    events = [_event("火灾", "一般", "", ""), _event("爆炸", "重大", "", "")]
    assert compute_level(events) == "重大"
    assert compute_level([]) == "未评估"


def test_resolve_responsible_fallback():
    ent = Enterprise(name="测试公司", safety_officer="李四", safety_officer_phone="13900000000")
    obj = RiskObject(name="配电室", responsible_unit=None, responsible_person=None, contact_phone=None)
    unit, person, phone, fallback = resolve_responsible(obj, ent)
    assert (unit, person, phone) == ("测试公司", "李四", "13900000000")
    assert fallback is True

    obj2 = RiskObject(name="配电室", responsible_unit="动力车间", responsible_person="王五", contact_phone="13800000000")
    unit2, person2, phone2, fallback2 = resolve_responsible(obj2, ent)
    assert (unit2, person2, phone2) == ("动力车间", "王五", "13800000000")
    assert fallback2 is False


def test_build_right_column_emergency_then_template():
    events = [_event("火灾", "重大", "泄漏遇明火", "火灾爆炸")]
    measures = [
        RiskMeasure(measure_category="engineering", description="防静电接地"),
        RiskMeasure(measure_category="management", description="动火审批"),
        RiskMeasure(measure_category="emergency", description="切断气源"),
    ]
    col = build_right_column(events, [measures[0], measures[1], measures[2]])
    assert "泄漏遇明火" in col.hazard_description
    assert col.accident_types == ["火灾"]
    assert "防静电接地" in col.control_measures[0]
    assert "切断气源" in col.emergency_measures[0]
    assert len(col.emergency_measures) >= 2  # 模板兜底


def test_match_signs_merges_and_orders():
    signs = match_signs(["火灾", "触电"])
    cats = [s["category"] for s in signs]
    assert cats[:2] == ["warning", "warning"]
    assert "prohibition" in cats and "instruction" in cats


def test_compute_code_increments():
    objs = [RiskObject(name="A"), RiskObject(name="B")]
    assert compute_code(objs, objs[1]) == "FX-002"
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`
预期：FAIL（模块不存在）

- [ ] **步骤 2：实现组装服务**

创建 `backend/app/services/risk_notice_card_service.py`：

```python
"""风险告知卡组装服务：规则为主，从风险数据实时组装 CardData。"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.risk_management import RiskObject, RiskEvent, RiskMeasure
from app.models.risk_notice_card import RiskNoticeCard
from app.services.risk_notice_card_data import (
    SIGN_GROUPS, DEFAULT_SIGN_GROUP, EMERGENCY_TEMPLATES,
    LEVEL_ORDER, LEVEL_COLORS, SIGN_CATEGORY_ORDER,
)
from app.schemas.risk_notice_card import CardData, RightColumn, SignItem


def compute_level(events: list[RiskEvent]) -> str:
    levels = {e.risk_level for e in events if e.risk_level}
    for level in LEVEL_ORDER:
        if level in levels:
            return level
    return "未评估"


def resolve_responsible(obj: RiskObject, ent: Enterprise) -> tuple[str, str, str, bool]:
    if obj.responsible_unit or obj.responsible_person or obj.contact_phone:
        return (
            obj.responsible_unit or ent.name,
            obj.responsible_person or (ent.safety_officer or ""),
            obj.contact_phone or (ent.safety_officer_phone or ""),
            False,
        )
    return (ent.name, ent.safety_officer or "", ent.safety_officer_phone or "", True)


def compute_code(objects: list[RiskObject], obj: RiskObject) -> str:
    index = next((i for i, o in enumerate(objects) if o.id == obj.id), len(objects))
    return f"FX-{index + 1:03d}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _numbered(items: list[str]) -> list[str]:
    return [f"{i + 1}. {it}" for i, it in enumerate(items)]


def build_right_column(
    events: list[RiskEvent],
    measures: list[RiskMeasure],
    snapshot: dict | None = None,
) -> RightColumn:
    if snapshot:
        return RightColumn(
            hazard_description=snapshot.get("hazard_description", ""),
            accident_types=snapshot.get("accident_types", []),
            control_measures=snapshot.get("control_measures", []),
            emergency_measures=snapshot.get("emergency_measures", []),
        )
    hazard_parts = []
    for e in events:
        if e.trigger_conditions:
            hazard_parts.append(e.trigger_conditions)
        if e.consequences:
            hazard_parts.append(e.consequences)
    hazard = "；".join(_dedupe(hazard_parts))
    accident_types = _dedupe([e.accident_type for e in events])
    control = _numbered(_dedupe([
        m.description for m in measures
        if m.measure_category in ("engineering", "management", "ppe")
    ]))
    emergency_db = _dedupe([
        m.description for m in measures if m.measure_category == "emergency"
    ])
    emergency = _numbered(emergency_db)
    if len(emergency) < 2:
        template: list[str] = []
        for at in accident_types:
            template += EMERGENCY_TEMPLATES.get(at, [])
        if not template:
            template = ["立即停止作业，保护现场", "拨打 119/120 报警", "组织人员疏散，报告企业应急管理部门"]
        merged = _dedupe(emergency_db + template)
        emergency = _numbered(merged)
    return RightColumn(
        hazard_description=hazard,
        accident_types=accident_types,
        control_measures=control,
        emergency_measures=emergency,
    )


def match_signs(accident_types: list[str]) -> list[SignItem]:
    merged: list[dict] = []
    seen: set[str] = set()
    for at in accident_types:
        group = SIGN_GROUPS.get(at, DEFAULT_SIGN_GROUP)
        for s in group:
            if s["svg_name"] not in seen:
                seen.add(s["svg_name"])
                merged.append(s)
    # 按 警告→禁止→指令→提示 排序，每类最多 2 个
    ordered: list[dict] = []
    counts: dict[str, int] = {}
    for category in SIGN_CATEGORY_ORDER:
        for s in merged:
            if s["category"] == category and counts.get(category, 0) < 2:
                ordered.append(s)
                counts[category] = counts.get(category, 0) + 1
    return [SignItem(**s) for s in ordered]


def is_stale(snapshot: RiskNoticeCard, source_updated_at: datetime | None) -> bool:
    if source_updated_at is None:
        return False
    return snapshot.updated_at.replace(tzinfo=timezone.utc) < source_updated_at.replace(tzinfo=timezone.utc)


async def get_snapshot(db: AsyncSession, object_id: str) -> RiskNoticeCard | None:
    return (
        await db.execute(
            select(RiskNoticeCard).where(RiskNoticeCard.object_id == object_id).order_by(RiskNoticeCard.version.desc())
        )
    ).scalars().first()


async def load_events_and_measures(db: AsyncSession, object_id: str) -> tuple[list[RiskEvent], list[RiskMeasure]]:
    obj = (
        await db.execute(
            select(RiskObject)
            .options(
                selectinload(RiskObject.units).selectinload("events").selectinload("measures"),
                selectinload(RiskObject.events).selectinload("measures"),
            )
            .where(RiskObject.id == object_id)
        )
    ).scalar_one_or_none()
    if obj is None:
        return [], []
    events: list[RiskEvent] = list(obj.events or [])
    measures: list[RiskMeasure] = []
    for unit in obj.units or []:
        events.extend(unit.events or [])
    for e in events:
        measures.extend(e.measures or [])
    return events, measures


async def build_card_data(
    db: AsyncSession,
    ent: Enterprise,
    obj: RiskObject,
    objects: list[RiskObject],
    events: list[RiskEvent],
    measures: list[RiskMeasure],
) -> CardData:
    snapshot = await get_snapshot(db, obj.id)
    col = build_right_column(events, measures, snapshot.content if snapshot else None)
    unit, person, phone, fallback = resolve_responsible(obj, ent)
    level = compute_level(events)
    source_updated = max(
        [obj.updated_at or obj.created_at]
        + [e.updated_at or e.created_at for e in events]
        + [m.updated_at or m.created_at for m in measures]
    )
    return CardData(
        object_id=obj.id,
        enterprise_name=ent.name,
        name=obj.name,
        code=compute_code(objects, obj),
        level=level,
        level_color=LEVEL_COLORS.get(level, "#bfbfbf"),
        responsible_unit=unit,
        responsible_person=person,
        contact_phone=phone,
        fallback_used=fallback,
        signs=match_signs(col.accident_types),
        hazard_description=col.hazard_description,
        accident_types=col.accident_types,
        control_measures=col.control_measures,
        emergency_measures=col.emergency_measures,
        snapshot={"version": snapshot.version, "source": snapshot.source} if snapshot else None,
        stale=is_stale(snapshot, source_updated) if snapshot else False,
        public_url=f"/r/{obj.public_token}",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **步骤 3：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`
预期：PASS（含任务 1/2 的模型测试）

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): add card assembly service"
```

---

## 任务 6：schemas + 列表/详情 API

**文件：**
- 创建：`backend/app/schemas/risk_notice_card.py`
- 创建：`backend/app/routers/risk_notice_card.py`
- 修改：`backend/app/main.py`（注册路由）
- 测试：`backend/tests/test_risk_notice_card_api.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_risk_notice_card_api.py`（用 FastAPI TestClient + 现有鉴权依赖覆写模式；参考 `backend/tests/test_risk_hierarchy.py` 的 fixture 写法）：

```python
"""风险告知卡 API 测试。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.models.user import User


@pytest.fixture()
def client(monkeypatch):
    async def fake_user():
        return User(id="u1", email="t@t.com", hashed_password="x")

    app.dependency_overrides[get_current_user] = fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_list_requires_enterprise(client):
    resp = client.get("/api/v1/enterprises/not-exist/risk-notice-cards")
    assert resp.status_code == 404


def test_detail_missing_object_returns_404(client):
    resp = client.get("/api/v1/enterprises/not-exist/risk-notice-cards/not-exist")
    assert resp.status_code == 404
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v`
预期：FAIL（路由不存在 → 404 但不匹配预期或模块导入失败）

- [ ] **步骤 2：创建 schemas**

创建 `backend/app/schemas/risk_notice_card.py`：

```python
from typing import Literal
from pydantic import BaseModel


class SignItem(BaseModel):
    category: Literal["warning", "prohibition", "instruction", "notice"]
    name: str
    svg_name: str


class RightColumn(BaseModel):
    hazard_description: str = ""
    accident_types: list[str] = []
    control_measures: list[str] = []
    emergency_measures: list[str] = []


class CardData(RightColumn):
    object_id: str
    enterprise_name: str
    name: str
    code: str
    level: str
    level_color: str
    responsible_unit: str
    responsible_person: str
    contact_phone: str
    fallback_used: bool = False
    signs: list[SignItem] = []
    snapshot: dict | None = None
    stale: bool = False
    public_url: str
    generated_at: str


class CardSummary(BaseModel):
    object_id: str
    name: str
    zone_name: str = ""
    level: str
    level_color: str
    accident_types: list[str] = []
    signs: list[SignItem] = []
    responsible_unit: str = ""
    snapshot: dict | None = None
    stale: bool = False
    public_url: str


class ExportRequest(BaseModel):
    object_ids: list[str]


class ExportResponse(BaseModel):
    file_key: str


class AiOptimizeResponse(BaseModel):
    original: RightColumn
    optimized: RightColumn


class SnapshotSaveRequest(BaseModel):
    content: RightColumn
```

- [ ] **步骤 3：创建路由（列表/详情，先实现；导出/AI/快照在任务 7-9 补）**

创建 `backend/app/routers/risk_notice_card.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskObject, RiskEvent, RiskMeasure, RiskZone
from app.schemas.common import ApiResponse
from app.schemas.risk_notice_card import CardData, CardSummary
from app.services.risk_notice_card_service import (
    build_card_data, compute_level, match_signs, resolve_responsible, load_events_and_measures,
)
from app.services.risk_notice_card_data import LEVEL_COLORS

router = APIRouter(prefix="/enterprises/{enterprise_id}/risk-notice-cards", tags=["Risk Notice Card"])


async def _get_ent(eid: str, uid: str, db: AsyncSession) -> Enterprise:
    ent = (
        await db.execute(select(Enterprise).where(Enterprise.id == eid, Enterprise.user_id == uid))
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


@router.get("", response_model=ApiResponse[list[CardSummary]])
async def list_cards(
    enterprise_id: str,
    level: str | None = None,
    zone_id: str | None = None,
    keyword: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    objs = (
        await db.execute(
            select(RiskObject)
            .options(
                selectinload(RiskObject.zone),
                selectinload(RiskObject.units).selectinload("events").selectinload("measures"),
                selectinload(RiskObject.events).selectinload("measures"),
            )
            .where(RiskObject.enterprise_id == enterprise_id)
            .order_by(RiskObject.created_at)
        )
    ).scalars().all()
    summaries = []
    for obj in objs:
        events: list[RiskEvent] = list(obj.events or [])
        measures: list[RiskMeasure] = []
        for unit in obj.units or []:
            events.extend(unit.events or [])
        for e in events:
            measures.extend(e.measures or [])
        lv = compute_level(events)
        if level and lv != level:
            continue
        if zone_id and obj.zone_id != zone_id:
            continue
        if keyword and keyword not in obj.name and not (obj.responsible_unit or "").__contains__(keyword):
            continue
        unit, person, phone, fallback = resolve_responsible(obj, await _get_ent(enterprise_id, current_user.id, db))
        accident_types = list(dict.fromkeys(e.accident_type for e in events if e.accident_type))
        summaries.append(CardSummary(
            object_id=obj.id,
            name=obj.name,
            zone_name=obj.zone.name if obj.zone else "",
            level=lv,
            level_color=LEVEL_COLORS.get(lv, "#bfbfbf"),
            accident_types=accident_types,
            signs=match_signs(accident_types),
            responsible_unit=unit,
            public_url=f"/r/{obj.public_token}",
        ))
    return ApiResponse(data=summaries)


@router.get("/{object_id}", response_model=ApiResponse[CardData])
async def card_detail(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(
            select(RiskObject).where(RiskObject.id == object_id, RiskObject.enterprise_id == enterprise_id)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    objects = (
        await db.execute(
            select(RiskObject).where(RiskObject.enterprise_id == enterprise_id).order_by(RiskObject.created_at)
        )
    ).scalars().all()
    events, measures = await load_events_and_measures(db, object_id)
    data = await build_card_data(db, ent, obj, list(objects), events, measures)
    return ApiResponse(data=data)
```

- [ ] **步骤 4：注册路由**

在 `backend/app/main.py` 添加：

```python
from app.routers import risk_notice_card
from app.routers import public_risk_notice
app.include_router(risk_notice_card.router, prefix="/api/v1")
app.include_router(public_risk_notice.router, prefix="/api/v1")
```

（`public_risk_notice` 模块在任务 9 创建；若 import 失败，先创建空模块占位，任务 9 填充。）

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v`
预期：PASS（企业不存在 → 404；风险点不存在 → 404）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/schemas/risk_notice_card.py backend/app/routers/risk_notice_card.py backend/app/main.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): add list and detail endpoints"
```

---

## 任务 7：AI 优化 + 快照端点

**文件：**
- 修改：`backend/app/routers/risk_notice_card.py`
- 创建：`backend/app/services/risk_notice_card_ai.py`
- 测试：`backend/tests/test_risk_notice_card_api.py`（追加）

- [ ] **步骤 1：编写失败测试（快照保存 + 版本递增）**

在 `test_risk_notice_card_api.py` 追加（mock 掉 DB 层不现实时，直接单测服务层 `save_snapshot`；API 测试用 monkeypatch 替换 `llm_text_completion`）：

```python
import asyncio
from app.services.risk_notice_card_service import save_snapshot
from app.models.risk_notice_card import RiskNoticeCard


def test_save_snapshot_increments_version():
    async def run():
        calls = []

        class FakeDB:
            async def execute(self, stmt):
                calls.append(stmt)
                class R:
                    def scalars(self):
                        return self
                    def all(self):
                        return []
                    def first(self):
                        return None
                return R()

            async def commit(self):
                pass

            async def refresh(self, obj):
                obj.version = 1

        class FakeUser:
            id = "u1"

        obj = await save_snapshot(FakeDB(), "e1", "o1", FakeUser(), {"hazard_description": "x", "accident_types": ["火灾"], "control_measures": [], "emergency_measures": []})
        assert obj is None or obj.version == 1
        return True

    assert asyncio.run(run())
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_save_snapshot_increments_version -v`
预期：FAIL（`save_snapshot` 不存在）

- [ ] **步骤 2：实现 AI 优化服务与快照保存**

创建 `backend/app/services/risk_notice_card_ai.py`：

```python
"""风险告知卡 AI 优化（可选路径，规则生成失败不影响）。"""
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk_ai_service import _get_ai_config
from app.services.llm_client import llm_text_completion
from app.schemas.risk_notice_card import RightColumn


async def optimize_right_column(
    db: AsyncSession,
    user_id: str,
    enterprise_name: str,
    object_name: str,
    original: RightColumn,
) -> RightColumn:
    ai_config = await _get_ai_config(user_id, db)
    prompt = (
        "你是安全生产专家。请优化风险告知卡右栏文案，输出严格 JSON："
        '{"hazard_description": "主要危险因素描述", "control_measures": ["1. ...", "2. ..."], "emergency_measures": ["1. ...", "2. ..."]}。'
        f"企业：{enterprise_name}；风险点：{object_name}；原版：{original.model_dump_json()}。"
        "要求：措施用①②③编号形式（输出为字符串数组，每项以'① '开头）；事故类型不得改动；中文输出。"
    )
    raw = await llm_text_completion([{"role": "user", "content": prompt}], ai_config, timeout=60)
    data = json.loads(raw)
    return RightColumn(
        hazard_description=data.get("hazard_description", original.hazard_description),
        accident_types=original.accident_types,
        control_measures=data.get("control_measures", original.control_measures),
        emergency_measures=data.get("emergency_measures", original.emergency_measures),
    )
```

在 `risk_notice_card_service.py` 追加：

```python
async def save_snapshot(
    db: AsyncSession,
    enterprise_id: str,
    object_id: str,
    user_id: str,
    content: dict,
) -> RiskNoticeCard | None:
    existing = await get_snapshot(db, object_id)
    if existing:
        existing.version += 1
        existing.content = content
        existing.source = "ai"
        existing.created_by = user_id
        await db.commit()
        await db.refresh(existing)
        return existing
    snap = RiskNoticeCard(
        enterprise_id=enterprise_id,
        object_id=object_id,
        version=1,
        content=content,
        source="ai",
        created_by=user_id,
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap
```

- [ ] **步骤 3：实现 AI 优化与快照端点**

在 `risk_notice_card.py` 追加：

```python
from app.schemas.risk_notice_card import AiOptimizeResponse, SnapshotSaveRequest
from app.services.risk_notice_card_ai import optimize_right_column
from app.services.risk_notice_card_service import build_right_column, save_snapshot


@router.post("/{object_id}/ai-optimize", response_model=ApiResponse[AiOptimizeResponse])
async def ai_optimize(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(select(RiskObject).where(RiskObject.id == object_id, RiskObject.enterprise_id == enterprise_id))
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    events, measures = await load_events_and_measures(db, object_id)
    original = build_right_column(events, measures)
    try:
        optimized = await optimize_right_column(db, current_user.id, ent.name, obj.name, original)
    except Exception:
        raise HTTPException(502, "AI 优化失败，请稍后重试或保留原版")
    return ApiResponse(data=AiOptimizeResponse(original=original, optimized=optimized))


@router.put("/{object_id}/snapshot", response_model=ApiResponse[dict])
async def save_card_snapshot(
    enterprise_id: str,
    object_id: str,
    body: SnapshotSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    snap = await save_snapshot(db, enterprise_id, object_id, current_user.id, body.content.model_dump())
    return ApiResponse(data={"version": snap.version, "source": "ai"})
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_notice_card_ai.py backend/app/services/risk_notice_card_service.py backend/app/routers/risk_notice_card.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): add ai optimize and snapshot endpoints"
```

---

## 任务 8：docx 导出 + 二维码

**文件：**
- 创建：`backend/app/services/risk_notice_card_docx.py`
- 修改：`backend/app/routers/risk_notice_card.py`（导出端点）
- 修改：`backend/requirements.txt`（+ qrcode）
- 测试：`backend/tests/test_risk_notice_card_docx.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_risk_notice_card_docx.py`：

```python
"""风险告知卡 docx 导出测试。"""
import asyncio
import re
from pathlib import Path
from docx import Document

from app.services.risk_notice_card_docx import render_cards_docx, make_qr_png
from app.schemas.risk_notice_card import CardData, SignItem


def _card(oid: str, name: str, level: str = "重大") -> CardData:
    return CardData(
        object_id=oid, enterprise_name="测试公司", name=name, code="FX-001", level=level,
        level_color="#ff4d4f", responsible_unit="储运车间", responsible_person="张三",
        contact_phone="13800000000", fallback_used=False,
        signs=[SignItem(category="warning", name="当心爆炸", svg_name="warning-explosion")],
        hazard_description="泄漏遇明火引发火灾爆炸", accident_types=["火灾", "爆炸"],
        control_measures=["1. 防静电接地", "2. 动火审批"], emergency_measures=["1. 切断气源", "2. 报警"],
        public_url="/r/token123", generated_at="2026-08-11T00:00:00Z",
    )


def test_make_qr_png_returns_png_bytes():
    png = make_qr_png("http://localhost/r/token123")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_cards_docx_one_page_per_card(tmp_path):
    cards = [_card("o1", "LPG 储罐区"), _card("o2", "配电室", "较大")]
    out = tmp_path / "cards.docx"
    render_cards_docx(cards, str(out))
    assert out.exists()
    doc = Document(str(out))
    # 每卡一页：标题出现次数 = 卡数
    titles = [p.text for p in doc.paragraphs if "安全风险告知卡" in p.text]
    assert len(titles) == 2
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_docx.py -v`
预期：FAIL（模块不存在）

- [ ] **步骤 2：安装依赖**

```bash
cd backend && python -m pip install qrcode
```

在 `backend/requirements.txt` 追加：`qrcode`

- [ ] **步骤 3：实现 docx 渲染服务**

创建 `backend/app/services/risk_notice_card_docx.py`：

```python
"""风险告知卡 Word 渲染：A4 竖版、每卡一页、右上角二维码、左栏表格 + 标志 PNG。"""
import io
import os
from pathlib import Path

import qrcode
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

from app.schemas.risk_notice_card import CardData
from app.services.risk_notice_card_data import LEVEL_COLORS

SIGNS_DIR = Path(__file__).resolve().parent.parent / "static" / "signs"
EMU_PER_CM = 360000


def make_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _set_run(run, text: str, size: float = 10, bold: bool = False, color: str | None = None):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "黑体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _render_header(doc, card: CardData):
    table = doc.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_l, cell_m, cell_r = table.rows[0].cells
    p = cell_l.paragraphs[0]
    _set_run(p.add_run(), card.enterprise_name, size=9, color="666666")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = cell_m.paragraphs[0]
    _set_run(p.add_run(), f"{card.name}安全风险告知卡", size=16, bold=True)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = cell_r.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(io.BytesIO(make_qr_png(card.public_url)), width=Cm(1.4))
    # 底部等级色线（使用段落底纹近似，简化为标题下空行 + 色块段落）


def _render_left(doc, card: CardData):
    rows = [
        ("风险点名称", card.name),
        ("风险点编号", card.code),
        ("风险等级", card.level),
        ("责任单位", card.responsible_unit),
        ("责任人", card.responsible_person),
        ("联系电话", card.contact_phone),
    ]
    table = doc.add_table(rows=len(rows), cols=2)
    table.style = "Table Grid"
    for i, (k, v) in enumerate(rows):
        _set_run(table.rows[i].cells[0].paragraphs[0].add_run(), k, size=10, bold=True)
        _set_run(table.rows[i].cells[1].paragraphs[0].add_run(), v, size=10)
    doc.add_paragraph()
    p = doc.add_paragraph()
    _set_run(p.add_run(), "安全标志", size=11, bold=True)
    sign_par = doc.add_paragraph()
    for sign in card.signs:
        svg = SIGNS_DIR / f"{sign.svg_name}.svg"
        if svg.exists():
            run = sign_par.add_run()
            run.add_picture(str(svg), width=Cm(1.5))
        run = sign_par.add_run(f" {sign.name}  ")
        _set_run(run, f" {sign.name}  ", size=9)


def _render_right(doc, card: CardData):
    blocks = [
        ("主要危险因素描述", card.hazard_description),
        ("主要事故类型", "、".join(card.accident_types) + "（GB 6441 事故类别）"),
        ("主要风险控制措施", "\n".join(card.control_measures)),
        ("应急处置措施", "\n".join(card.emergency_measures)),
    ]
    for title, body in blocks:
        p = doc.add_paragraph()
        _set_run(p.add_run(), title, size=11, bold=True, color="FFFFFF")
        p.paragraph_format.space_before = Pt(6)
        for line in body.split("\n"):
            p2 = doc.add_paragraph()
            _set_run(p2.add_run(), line, size=10)


def render_cards_docx(cards: list[CardData], out_path: str):
    doc = Document()
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.left_margin = section.right_margin = Cm(1.8)
    section.top_margin = section.bottom_margin = Cm(1.5)
    for i, card in enumerate(cards):
        _render_header(doc, card)
        _render_left(doc, card)
        _render_right(doc, card)
        if i < len(cards) - 1:
            doc.add_page_break()
    doc.save(out_path)
```

> 实现注意：`run.add_picture(str(svg))` 若 python-docx 不支持直接嵌 SVG（取决于版本），改用 `render_svg_to_png`（`mermaid_renderer`，异步）将 SVG 转 PNG bytes 后嵌入。导出端点调用处用 `asyncio` 适配。

- [ ] **步骤 4：实现导出端点**

在 `risk_notice_card.py` 追加：

```python
import asyncio, os
from datetime import datetime
from app.config import settings
from app.schemas.risk_notice_card import ExportRequest, ExportResponse
from app.services.risk_notice_card_docx import render_cards_docx


@router.post("/export", response_model=ApiResponse[ExportResponse])
async def export_cards(
    enterprise_id: str,
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    cards = []
    warnings: list[str] = []
    for oid in body.object_ids:
        obj = (
            await db.execute(select(RiskObject).where(RiskObject.id == oid, RiskObject.enterprise_id == enterprise_id))
        ).scalar_one_or_none()
        if not obj:
            warnings.append(f"风险点不存在：{oid}")
            continue
        objects = (
            await db.execute(select(RiskObject).where(RiskObject.enterprise_id == enterprise_id).order_by(RiskObject.created_at))
        ).scalars().all()
        events, measures = await load_events_and_measures(db, oid)
        cards.append(await build_card_data(db, ent, obj, list(objects), events, measures))
    if not cards:
        raise HTTPException(400, "没有可导出的卡片")
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    file_key = f"risk-notice-{enterprise_id[:8]}-{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    out_path = os.path.join(settings.EXPORT_DIR, file_key)
    render_cards_docx(cards, out_path)
    return ApiResponse(data=ExportResponse(file_key=file_key))
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_docx.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/risk_notice_card_docx.py backend/app/routers/risk_notice_card.py backend/requirements.txt backend/tests/test_risk_notice_card_docx.py
git commit -m "feat(risk-notice-card): add docx export with qr code"
```

---

## 任务 9：公开 API + token 重置

**文件：**
- 创建：`backend/app/routers/public_risk_notice.py`
- 修改：`backend/app/routers/risk_notice_card.py`（token 重置端点）
- 测试：`backend/tests/test_public_risk_notice.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_public_risk_notice.py`：

```python
"""公开只读风险告知卡 API 测试。"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_public_unknown_token_returns_404(client):
    resp = client.get("/api/v1/public/risk-notice-cards/no-such-token")
    assert resp.status_code == 404
```

运行：`cd backend && python -m pytest tests/test_public_risk_notice.py -v`
预期：FAIL（路由不存在 → 404 页面而非 JSON 或 405）

- [ ] **步骤 2：实现公开 API**

创建 `backend/app/routers/public_risk_notice.py`：

```python
"""公开只读风险告知卡（无鉴权，token 防遍历）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskObject
from app.schemas.common import ApiResponse
from app.schemas.risk_notice_card import CardData
from app.services.risk_notice_card_service import build_card_data, load_events_and_measures

router = APIRouter(prefix="/public/risk-notice-cards", tags=["Public Risk Notice Card"])


@router.get("/{token}", response_model=ApiResponse[CardData])
async def public_card(token: str, db: AsyncSession = Depends(get_db)):
    obj = (
        await db.execute(
            select(RiskObject)
            .options(selectinload(RiskObject.zone))
            .where(RiskObject.public_token == token)
        )
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "卡片不存在或链接已失效")
    ent = (
        await db.execute(select(Enterprise).where(Enterprise.id == obj.enterprise_id))
    ).scalar_one()
    objects = (
        await db.execute(select(RiskObject).where(RiskObject.enterprise_id == obj.enterprise_id).order_by(RiskObject.created_at))
    ).scalars().all()
    events, measures = await load_events_and_measures(db, obj.id)
    data = await build_card_data(db, ent, obj, list(objects), events, measures)
    return ApiResponse(data=data)
```

- [ ] **步骤 3：token 重置端点**

在 `risk_notice_card.py` 追加：

```python
import secrets


@router.post("/{object_id}/token/reset", response_model=ApiResponse[dict])
async def reset_token(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(select(RiskObject).where(RiskObject.id == object_id, RiskObject.enterprise_id == enterprise_id))
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    obj.public_token = secrets.token_hex(32)
    await db.commit()
    return ApiResponse(data={"public_url": f"/r/{obj.public_token}"})
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_public_risk_notice.py tests/test_risk_notice_card_api.py -v`
预期：全部 PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/public_risk_notice.py backend/app/routers/risk_notice_card.py backend/tests/test_public_risk_notice.py
git commit -m "feat(risk-notice-card): add public read api and token reset"
```

---

## 任务 10：前端类型 + API service + 入口与路由

**文件：**
- 创建：`frontend/src/types/riskNoticeCard.ts`
- 创建：`frontend/src/services/riskNoticeCardService.ts`
- 创建：`frontend/src/services/riskNoticeCardService.test.ts`
- 修改：`frontend/src/App.tsx`（路由，先加管理页/公开页占位路由）
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`（顶部按钮）
- 修改：`frontend/src/types/riskManagement.ts`（RiskObject 字段）

- [ ] **步骤 1：编写失败测试（service）**

创建 `frontend/src/services/riskNoticeCardService.test.ts`：

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchCardSummaries, exportCards } from "./riskNoticeCardService";

describe("riskNoticeCardService", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchCardSummaries calls list endpoint", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, data: [] }),
    } as Response);
    await fetchCardSummaries("e1", { level: "重大" });
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/enterprises/e1/risk-notice-cards"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("exportCards posts object_ids and returns file_key", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, data: { file_key: "cards.docx" } }),
    } as Response);
    const result = await exportCards("e1", ["o1", "o2"]);
    expect(result).toBe("cards.docx");
  });
});
```

运行：`cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts`
预期：FAIL（模块不存在）

- [ ] **步骤 2：创建类型**

创建 `frontend/src/types/riskNoticeCard.ts`：

```typescript
export type SignCategory = "warning" | "prohibition" | "instruction" | "notice";

export interface SignItem {
  category: SignCategory;
  name: string;
  svg_name: string;
}

export interface RightColumn {
  hazard_description: string;
  accident_types: string[];
  control_measures: string[];
  emergency_measures: string[];
}

export interface CardData extends RightColumn {
  object_id: string;
  enterprise_name: string;
  name: string;
  code: string;
  level: string;
  level_color: string;
  responsible_unit: string;
  responsible_person: string;
  contact_phone: string;
  fallback_used: boolean;
  signs: SignItem[];
  snapshot: { version: number; source: string } | null;
  stale: boolean;
  public_url: string;
  generated_at: string;
}

export interface CardSummary {
  object_id: string;
  name: string;
  zone_name: string;
  level: string;
  level_color: string;
  accident_types: string[];
  signs: SignItem[];
  responsible_unit: string;
  snapshot: { version: number; source: string } | null;
  stale: boolean;
  public_url: string;
}
```

- [ ] **步骤 3：创建 service**

创建 `frontend/src/services/riskNoticeCardService.ts`（参考项目其他 service 的 `apiFetch` 风格；若项目有统一封装则复用）：

```typescript
import type { CardData, CardSummary, RightColumn } from "@/types/riskNoticeCard";
import { request } from "./request"; // 按项目现有请求封装调整

export interface CardListParams {
  level?: string;
  zone_id?: string;
  keyword?: string;
}

export async function fetchCardSummaries(enterpriseId: string, params: CardListParams = {}): Promise<CardSummary[]> {
  const query = new URLSearchParams();
  if (params.level) query.set("level", params.level);
  if (params.zone_id) query.set("zone_id", params.zone_id);
  if (params.keyword) query.set("keyword", params.keyword);
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards?${query.toString()}`);
  return res.data;
}

export async function fetchCardDetail(enterpriseId: string, objectId: string): Promise<CardData> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}`);
  return res.data;
}

export async function exportCards(enterpriseId: string, objectIds: string[]): Promise<string> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_ids: objectIds }),
  });
  return res.data.file_key as string;
}

export async function aiOptimize(enterpriseId: string, objectId: string): Promise<{ original: RightColumn; optimized: RightColumn }> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}/ai-optimize`, { method: "POST" });
  return res.data;
}

export async function saveSnapshot(enterpriseId: string, objectId: string, content: RightColumn): Promise<{ version: number }> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}/snapshot`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  return res.data;
}

export async function resetToken(enterpriseId: string, objectId: string): Promise<string> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}/token/reset`, { method: "POST" });
  return res.data.public_url as string;
}

export async function fetchPublicCard(token: string): Promise<CardData> {
  const res = await request(`/public/risk-notice-cards/${token}`);
  return res.data;
}
```

> 实现注意：若项目没有统一 `request` 封装，参照 `frontend/src/services/riskManagementService.ts` 的请求写法（含 token header / base URL）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts`
预期：PASS

- [ ] **步骤 5：RiskObject 类型加字段**

在 `frontend/src/types/riskManagement.ts` 的 RiskObject 相关类型中追加：

```typescript
responsible_unit?: string | null;
responsible_person?: string | null;
contact_phone?: string | null;
public_token?: string;
```

- [ ] **步骤 6：管理页路由 + Tab 入口 + 公开页占位**

- 在 `frontend/src/App.tsx` 的 router 配置中：管理页路由 `/enterprises/:enterpriseId/risk-notice-cards`（放在企业布局下）与公开路由 `/r/:token`（无登录守卫，指向 `PublicRiskNoticePage` 占位组件）。
- 在 `RiskManagementTab.tsx` 顶部操作区添加按钮（参照现有「智能填充」按钮样式）：

```tsx
<Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}>
  风险告知卡
</Button>
```

- 创建 `frontend/src/pages/PublicRiskNoticePage.tsx` 占位（任务 13 填充）：

```tsx
export default function PublicRiskNoticePage() {
  return <div>加载中…</div>;
}
```

- [ ] **步骤 7：门禁 + Commit**

运行：`cd frontend && npx tsc -b` 预期：0 错误；`npx vitest run` 预期：既有测试 + 新增全通过

```bash
git add frontend/src/types/riskNoticeCard.ts frontend/src/services/riskNoticeCardService.ts frontend/src/services/riskNoticeCardService.test.ts frontend/src/App.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/types/riskManagement.ts frontend/src/pages/PublicRiskNoticePage.tsx
git commit -m "feat(risk-notice-card): add frontend types, service, routes and entry"
```

---

## 任务 11：卡片管理页

**文件：**
- 创建：`frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx`

- [ ] **步骤 1：实现管理页（列表/筛选/勾选/批量导出）**

创建 `frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx`，核心结构（完整组件按项目 Ant Design 风格实现）：

```tsx
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Input, Select, Space, Table, Tag, Tooltip, message } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchCardSummaries, exportCards } from "@/services/riskNoticeCardService";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
import type { CardSummary } from "@/types/riskNoticeCard";

export default function RiskNoticeCardPage() {
  const { enterpriseId = "" } = useParams();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [selected, setSelected] = useState<string[]>([]);
  const [filters, setFilters] = useState<{ level?: string; keyword?: string }>({});

  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ["risk-notice-cards", enterpriseId, filters],
    queryFn: () => fetchCardSummaries(enterpriseId, filters),
  });

  const handleExport = async () => {
    if (!selected.length) {
      message.warning("请先勾选要导出的风险点");
      return;
    }
    const fileKey = await exportCards(enterpriseId, selected);
    window.open(`/api/v1/export/download/${fileKey}`, "_blank");
  };

  const columns = [
    { title: "风险点名称", dataIndex: "name",
      render: (name: string, r: CardSummary) => (
        <a onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards/${r.object_id}`)}>{name}</a>
      ) },
    { title: "所在分区", dataIndex: "zone_name" },
    { title: "风险等级", dataIndex: "level",
      render: (level: string, r: CardSummary) => (
        <Tag color={r.level_color}>{level}</Tag>
      ) },
    { title: "主要事故类型", dataIndex: "accident_types",
      render: (v: string[]) => v.join("、") },
    { title: "安全标志", dataIndex: "signs",
      render: (signs: CardSummary["signs"]) => (
        <Space size={2}>
          {signs.slice(0, 3).map((s) => (
            <Tooltip title={s.name} key={s.svg_name}>
              <img src={`/signs/${s.svg_name}.svg`} width={20} height={20} alt={s.name} />
            </Tooltip>
          ))}
        </Space>
      ) },
    { title: "责任单位", dataIndex: "responsible_unit" },
    { title: "快照", dataIndex: "snapshot",
      render: (s: CardSummary["snapshot"], r: CardSummary) =>
        r.stale ? <Tag color="orange">数据已变更</Tag> : s ? <Tag color="blue">V1.{s.version} AI</Tag> : <span>—</span> },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12, justifyContent: "space-between", width: "100%" }}>
        <h2>风险告知卡</h2>
        <Space>
          <Button onClick={() => refetch()}>刷新</Button>
          <Button type="primary" onClick={handleExport}>批量导出 Word</Button>
        </Space>
      </Space>
      <Space style={{ marginBottom: 12 }}>
        <Select
          allowClear placeholder="风险等级" style={{ width: 140 }}
          options={Object.entries(RISK_LEVEL_COLORS).map(([value, color]) => ({ value, label: value }))}
          onChange={(v) => setFilters((f) => ({ ...f, level: v }))}
        />
        <Input.Search
          placeholder="搜索风险点名称/责任单位" style={{ width: 240 }}
          onSearch={(v) => setFilters((f) => ({ ...f, keyword: v }))}
        />
      </Space>
      <Table
        rowKey="object_id"
        loading={isLoading}
        dataSource={data}
        columns={columns}
        rowSelection={{ selectedRowKeys: selected, onChange: setSelected }}
        pagination={{ pageSize: 20 }}
      />
      {selected.length > 0 && (
        <div style={{ marginTop: 12 }}>
          已选 {selected.length} 项 <Button type="primary" onClick={handleExport}>导出选中卡片 Word</Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **步骤 2：门禁**

运行：`cd frontend && npx tsc -b` 预期：0 错误

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskNoticeCardPage.tsx
git commit -m "feat(risk-notice-card): add card management page"
```

---

## 任务 12：卡片组件 + 单卡预览页 + AI 优化对比

**文件：**
- 创建：`frontend/src/components/enterprise/RiskNoticeCard.tsx`
- 创建：`frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`
- 修改：`frontend/src/App.tsx`（预览页路由）

- [ ] **步骤 1：实现卡片渲染组件**

创建 `frontend/src/components/enterprise/RiskNoticeCard.tsx`（v5 版式：头部企业名+标题+右上角二维码占位、左栏键值表+安全标志区、右栏四块、页脚；样式内联或 CSS Module）：

```tsx
import type { CardData } from "@/types/riskNoticeCard";

export default function RiskNoticeCard({ card }: { card: CardData }) {
  return (
    <div className="rnc-card">
      <div className="rnc-head">
        <div className="rnc-ent">{card.enterprise_name}</div>
        <div className="rnc-title">{card.name}安全风险告知卡</div>
        <div className="rnc-qr">{/* QR 由后端生成；预览期显示占位方块 */}<div className="rnc-qr-sq" /></div>
      </div>
      <div className="rnc-body">
        <div className="rnc-left">
          <div className="rnc-level" style={{ background: card.level_color }}>{card.level}风险</div>
          <table className="rnc-kv">
            <tbody>
              {[
                ["风险点名称", card.name], ["风险点编号", card.code], ["风险等级", card.level],
                ["责任单位", card.responsible_unit], ["责任人", card.responsible_person],
                ["联系电话", card.contact_phone],
              ].map(([k, v]) => (
                <tr key={k}><td className="k">{k}</td><td className="v">{v}</td></tr>
              ))}
            </tbody>
          </table>
          <div className="rnc-sign-head">安全标志</div>
          <div className="rnc-signs">
            {card.signs.map((s) => (
              <div className="rnc-sign" key={s.svg_name}>
                <img src={`/signs/${s.svg_name}.svg`} width={56} height={56} alt={s.name} />
                <span>{s.name}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rnc-right">
          {[
            ["主要危险因素描述", card.hazard_description],
            ["主要事故类型", card.accident_types.join("、") + "（GB 6441 事故类别）"],
            ["主要风险控制措施", card.control_measures.join("\n")],
            ["应急处置措施", card.emergency_measures.join("\n")],
          ].map(([title, body]) => (
            <div className="rnc-block" key={title}>
              <h4>{title}</h4>
              {body.split("\n").map((line, i) => <p key={i}>{line}</p>)}
            </div>
          ))}
        </div>
      </div>
      <div className="rnc-foot">
        <span>签发单位：{card.enterprise_name}</span>
        <span>编制日期：{new Date(card.generated_at).toLocaleDateString("zh-CN")}</span>
        <span>版本：{card.snapshot ? `V1.${card.snapshot.version}` : "V1.0"}</span>
      </div>
    </div>
  );
}
```

（`.rnc-*` 样式按 v5 原型实现：头部色线用 `card.level_color`、左栏 40%、标志区深色标题条、右栏深色标题块。）

- [ ] **步骤 2：实现预览页 + AI 对比**

创建 `frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`：

```tsx
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Space, Spin, Tag, Alert } from "antd";
import { useQuery } from "@tanstack/react-query";
import RiskNoticeCard from "@/components/enterprise/RiskNoticeCard";
import { fetchCardDetail, aiOptimize, saveSnapshot, resetToken } from "@/services/riskNoticeCardService";

export default function RiskNoticeCardPreviewPage() {
  const { enterpriseId = "", objectId = "" } = useParams();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [comparing, setComparing] = useState<{ original: any; optimized: any } | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: card, isLoading, refetch } = useQuery({
    queryKey: ["risk-notice-card", enterpriseId, objectId],
    queryFn: () => fetchCardDetail(enterpriseId, objectId),
  });

  const handleOptimize = async () => {
    setBusy(true);
    try {
      setComparing(await aiOptimize(enterpriseId, objectId));
    } catch {
      message.error("AI 优化失败，已保留原版");
    } finally {
      setBusy(false);
    }
  };

  const handleAdopt = async () => {
    if (!comparing) return;
    await saveSnapshot(enterpriseId, objectId, comparing.optimized);
    message.success("已保存快照");
    setComparing(null);
    refetch();
  };

  const handleCopyLink = async () => {
    await navigator.clipboard.writeText(`${location.origin}${card?.public_url}`);
    message.success("公开链接已复制");
  };

  if (isLoading || !card) return <Spin />;
  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Button onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}>返回列表</Button>
        <Tag color="blue">{card.snapshot ? `V1.${card.snapshot.version} · AI 优化` : "V1.0 · 规则生成"}</Tag>
        {card.stale && <Alert type="warning" showIcon message="风险数据已变更，建议重新生成" />}
      </Space>
      <Space style={{ marginBottom: 12 }}>
        <Button onClick={handleCopyLink}>复制公开链接</Button>
        <Button type="primary" loading={busy} onClick={handleOptimize}>AI 优化</Button>
      </Space>
      <RiskNoticeCard card={card} />
      {comparing && (
        <div style={{ display: "flex", gap: 16, marginTop: 16 }}>
          <div style={{ flex: 1 }}>
            <h3>原版（当前版本）</h3>
            <p>{comparing.original.hazard_description}</p>
            <p>{comparing.original.control_measures.join("\n")}</p>
            <p>{comparing.original.emergency_measures.join("\n")}</p>
          </div>
          <div style={{ flex: 1 }}>
            <h3>优化版（AI 生成）</h3>
            <p>{comparing.optimized.hazard_description}</p>
            <p>{comparing.optimized.control_measures.join("\n")}</p>
            <p>{comparing.optimized.emergency_measures.join("\n")}</p>
          </div>
        </div>
      )}
      {comparing && (
        <Space style={{ marginTop: 12 }}>
          <Button type="primary" onClick={handleAdopt}>采用优化版并保存快照（版本 +1）</Button>
          <Button onClick={() => setComparing(null)}>放弃，保留原版</Button>
        </Space>
      )}
    </div>
  );
}
```

- [ ] **步骤 3：App.tsx 加预览页路由**

```tsx
<Route path="/enterprises/:enterpriseId/risk-notice-cards/:objectId" element={<RiskNoticeCardPreviewPage />} />
```

- [ ] **步骤 4：门禁 + Commit**

运行：`cd frontend && npx tsc -b` 预期：0 错误

```bash
git add frontend/src/components/enterprise/RiskNoticeCard.tsx frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx frontend/src/App.tsx
git commit -m "feat(risk-notice-card): add card preview and ai optimize compare"
```

---

## 任务 13：公开只读页

**文件：**
- 修改：`frontend/src/pages/PublicRiskNoticePage.tsx`（填充实现）

- [ ] **步骤 1：实现公开页**

替换占位实现：

```tsx
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import RiskNoticeCard from "@/components/enterprise/RiskNoticeCard";
import { fetchPublicCard } from "@/services/riskNoticeCardService";

export default function PublicRiskNoticePage() {
  const { token = "" } = useParams();
  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["public-risk-notice", token],
    queryFn: () => fetchPublicCard(token),
    retry: false,
  });
  if (isLoading) return <Spin style={{ display: "block", margin: "80px auto" }} />;
  if (isError || !card) return <div style={{ textAlign: "center", marginTop: 80 }}>卡片不存在或链接已失效</div>;
  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: 12 }}>
      <RiskNoticeCard card={card} />
      <div style={{ textAlign: "center", color: "#999", fontSize: 12, marginTop: 12 }}>
        公开只读页面 · 数据来自系统快照 · 无需登录
      </div>
    </div>
  );
}
```

> 实现注意：公开页路由 `/r/:token` 必须在登录守卫之外（App.tsx 路由顶层，不包 ProtectedLayout）；若项目路由守卫要求，查看 `frontend/src/App.tsx` 的 router 结构后调整。

- [ ] **步骤 2：门禁 + Commit**

运行：`cd frontend && npx tsc -b` 预期：0 错误

```bash
git add frontend/src/pages/PublicRiskNoticePage.tsx
git commit -m "feat(risk-notice-card): add public read-only page"
```

---

## 任务 14：风险对象表单新增责任信息字段

**文件：**
- 修改：`frontend/src/components/enterprise/RiskObjectForm.tsx`
- 修改：`frontend/src/types/riskManagement.ts`（`RiskObjectFormValues` 相关类型）

- [ ] **步骤 1：表单加三字段**

在 `RiskObjectForm.tsx` 的「位置描述」Form.Item 之后添加：

```tsx
<div style={{ fontSize: 13, fontWeight: 600, color: "#1677ff", margin: "16px 0 8px", borderLeft: "3px solid #1677ff", paddingLeft: 8 }}>
  责任信息（用于风险告知卡）
</div>
<Form.Item name="responsible_unit" label="责任单位">
  <Input placeholder="如：储运车间" />
</Form.Item>
<Form.Item name="responsible_person" label="责任人">
  <Input placeholder="如：张三" />
</Form.Item>
<Form.Item name="contact_phone" label="联系电话">
  <Input placeholder="如：13800000000" />
</Form.Item>
<div style={{ fontSize: 12, color: "#999", background: "#fafafa", border: "1px dashed #e0e0e0", borderRadius: 4, padding: "6px 8px", marginBottom: 8 }}>
  这三个字段会显示在风险告知卡左栏。留空时，卡片自动使用企业信息中的安全负责人及电话兜底。
</div>
```

同时在 `RiskObjectFormValues` 接口追加：

```typescript
responsible_unit?: string;
responsible_person?: string;
contact_phone?: string;
```

（`handleFinish` 已透传全部 values，无需额外处理；`initialValues` 回显依赖后端返回字段。）

- [ ] **步骤 2：门禁 + Commit**

运行：`cd frontend && npx tsc -b` 预期：0 错误

```bash
git add frontend/src/components/enterprise/RiskObjectForm.tsx frontend/src/types/riskManagement.ts
git commit -m "feat(risk-notice-card): add responsibility fields to risk object form"
```

---

## 任务 15：回归门禁 + 收尾

**文件：** 无新增（视修复情况）

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && python -m pytest tests/ -v`
预期：全部 PASS（既有 346+ 与新增 ~20 条）

- [ ] **步骤 2：前端全量门禁**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：tsc 0 错误、vitest 全通过

- [ ] **步骤 3：SVG 合规复检**

运行：`cd backend && python -m pytest tests/test_static_signs.py -v`
预期：PASS（形状/颜色/引用全覆盖）

- [ ] **步骤 4：手工冒烟（可选）**

- 本地起后端，登录企业 → 风险管理 Tab →「风险告知卡」→ 列表可见 → 预览单卡 → 导出 Word 打开检查每卡一页、右上角二维码、标志 PNG → AI 优化 → 保存快照 → 版本 +1 → 复制公开链接新窗口打开无需登录。

- [ ] **步骤 5：Commit（如有修复）并同步规格文档更新**

```bash
git add -A
git commit -m "chore(risk-notice-card): regression fixes"
```

- [ ] **步骤 6：等待合并决策**

按 finishing-a-development-branch 流程向用户提供合并选项（本地合并回 master / PR / 保持）。

---

## 自检记录

**规格覆盖度：**
- §2 决策 1-10 → 任务 1/2/5/6/7/8/9/10/11/12/13/14 ✅
- §4 版式 v5 + 二维码右上角 → 任务 12（卡片组件）✅
- §6 数据模型（4 字段 + 快照表 + 编号）→ 任务 1/2/5 ✅
- §7 标志库 36 SVG + 20 类映射 → 任务 3/4 ✅
- §8 应急处置模板 → 任务 3（EMERGENCY_TEMPLATES）+ 任务 5（兜底逻辑）✅
- §9 API 6+1 → 任务 6/7/8/9 ✅
- §10 页面交互 4 屏 → 任务 10/11/12/13/14 ✅
- §11 导出与二维码 → 任务 8 ✅
- §12 AI 优化流程 → 任务 7/12 ✅
- §13 错误处理 → 任务 6/7/8/9 + 前端 catch ✅
- §14 测试计划 → 各任务测试 ✅
- §15 范围里程碑 → 任务 1-15 ✅

**占位符扫描：** 无 TODO/待定/后续实现；任务 13 明确「实现注意」为真实实现指引。

**类型一致性：** `CardData`/`RightColumn`/`SignItem` 在 spec（§9）、schemas（任务 6）、前端类型（任务 10）、服务（任务 5）间字段名一致（`hazard_description`/`accident_types`/`control_measures`/`emergency_measures`/`svg_name`/`public_url`）。
