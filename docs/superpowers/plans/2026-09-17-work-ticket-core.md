# 作业票核心（标准清洗 + 模板层 + 轻量审批引擎 + 动火/受限空间）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 建起特殊作业（作业票）模块的骨架并跑通两类票：动火、受限空间。骨架 = 模板驱动的票面 + 轻量审批引擎 + 气体检测 + 法定票面打印归档。

**架构：**

```
GB 30871-2022 标准文本
   ├─ 附录A 表A.1~A.8  →  票面字段定义（work_ticket_template_fields）
   ├─ 第5~12章条款      →  必备安全措施库（work_ticket_template_measures，逐条挂条文锚点）
   └─ 附录B 表B.1       →  默认审批流程（flow_templates + flow_nodes）
              ↓
       作业票实例（work_ticket_instances）
              ↓ 审批引擎（状态机 + 会签 + 受限条件分支）
       逐节点办理记录（work_ticket_node_records）→ 打印快照
```

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / PostgreSQL / python-docx / APScheduler / React 18 + antd 5。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §7、§13.1

**依赖：** 计划 2（AI 网关，提交前合规校验与 JSA 生成需要）、计划 3（前端模块入口与页面范式）。

**视觉走查确认的两条约束（必须遵守）：**

1. 作业票导航 = **单入口「特殊作业」+ 页面内按类型筛选**，不做 8 个独立菜单
2. 流程模板 = **法定环节锁定，可加不可删**——节点顺序与法定审批环节由标准锁定，企业只能改每个节点绑定的角色/人，可额外插入自有节点，**不能删除法定环节**

**范围：** 本计划只做**动火 + 受限空间**两类。其余 6 类在计划 9，靠模板驱动横向复制——**骨架没验证前铺 6 类等于 6 次返工**。

---

## 文件结构

**后端**

| 文件 | 职责 |
|---|---|
| `scripts/clean_gb30871_text.py`（新建） | 标准文本 OCR 讹字清洗（可复现） |
| `backend/app/models/work_ticket.py`（新建） | 模板层 + 实例层 + 留痕层 ORM |
| `backend/db_migration_20260917_work_ticket.sql`（新建） | DDL |
| `backend/seed_work_ticket_templates.py`（新建） | 由标准文本生成票面字段/措施库/审批流程种子 |
| `backend/app/services/work_ticket_flow.py`（新建） | 轻量审批引擎（纯函数状态机 + 会签 + 条件分支） |
| `backend/app/services/work_ticket_service.py`（新建） | 开票、提交、审批、延期、作废、归档编排 |
| `backend/app/services/work_ticket_docx.py`（新建） | 法定票面 DOCX 渲染 + 打印快照 |
| `backend/app/schemas/work_ticket.py`（新建） | 出入参 |
| `backend/app/routers/work_ticket.py`（新建） | REST API |
| `backend/app/main.py`（修改） | 注册路由 |
| `backend/tests/test_gb30871_clean.py`（新建） | 清洗脚本与判据 |
| `backend/tests/test_work_ticket_flow.py`（新建） | 状态机/会签/条件分支 |
| `backend/tests/test_work_ticket_service.py`（新建） | 开票到归档全链路 |
| `backend/tests/test_work_ticket_api.py`（新建） | 端点测试 |

**前端**

| 文件 | 职责 |
|---|---|
| `frontend/src/types/workTicket.ts`（新建） | 类型 |
| `frontend/src/services/workTicketService.ts`（新建） | API 封装 |
| `frontend/src/pages/Enterprise/WorkTicketListPage.tsx`（新建） | 票列表（单入口 + 类型筛选） |
| `frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`（新建） | 开票向导（6 步） |
| `frontend/src/pages/Enterprise/WorkTicketDetailPage.tsx`（新建） | 详情/审批/打印 |
| `frontend/src/pages/Enterprise/WorkTicketApprovalPage.tsx`（新建） | 审批工作台（我的待办） |
| `frontend/src/components/enterprise/workTicket/GasTestTable.tsx`（新建） | 气体检测录入 |
| `frontend/src/pages/Enterprise/enterpriseNavConfig.ts`（修改） | 加 `workTicketNavGroups` |
| `frontend/src/components/enterprise/cockpit/ModuleNav.tsx`（修改） | 12 → 13 模块 |
| `frontend/src/routes/index.tsx`（修改） | 4 条路由 |

---

## 标准资产（已核实，直接用）

| 资产 | 位置 | 内容 |
|---|---|---|
| GB 30871-2022 真原文 | `backend/app/regulations/data/texts/reg_gb_30871_2022.md` | 63KB / 1136 行 |
| **附录A** | 同上 | 表 A.1~A.8 = 8 类作业票**法定票面样式**，含逐条安全措施清单（带"是否涉及 / 确认人"列） |
| **附录B 表B.1** | 同上 | 法定"办理部门 / 审核会签 / 审批部门"矩阵 |
| **附录B 表B.2** | 同上 | 三联持有与保存；B.3 规定作业票至少保存一年、影像至少留存一个月 |

条款数：第4章通用要求 18 条、第5章动火 32 条、第6章受限空间 10 条、第7章盲板抽堵 12 条、第8章高处 16 条、第9章吊装 16 条、第10章临时用电 8 条、第11章动土 11 条、第12章断路 5 条。

**法定审批矩阵（表B.1，本计划要用的两类）**

| 作业票 | 办理部门 | 审核或会签 | 审批 |
|---|---|---|---|
| 动火·特级 | 危险化学品企业 | — | 主管领导 |
| 动火·一级 | 危险化学品企业 | — | 安全管理部门 |
| 动火·二级 | 危险化学品企业 | — | 所在基层单位 |
| 受限空间 | 所在单位 | — | 所在基层单位 |

---

## 任务 1（前置，不可跳过）：GB 30871 文本清洗

**文件：**

- 创建：`scripts/clean_gb30871_text.py`
- 测试：`backend/tests/test_gb30871_clean.py`

**为什么必须前置：** 库内标准文本有**系统性 OCR 讹字**，实测量化——**"式"出现 0 次、"怯"出现 30 次**（样式→样怯、方式→方怯、便携式/移动式/隔绝式同理）；**"Ⅱ"出现 0 次、"聂"出现 4 次**（Ⅱ级→聂级）。不修就 seed 措施库，用户会在动火票上看到"动火方怯"——合规产品里这是不能接受的。

**判据：** 修复后 `"式"` 计数 > 0 且 `"怯"` = 0、`"聂"` = 0。

- [ ] **步骤 1：编写失败的测试**

```python
"""GB 30871 文本清洗：讹字修复与判据。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb30871_2022.md"


def _load():
    """按路径加载脚本，避免把 scripts/ 变成包引入导入副作用。"""
    spec = importlib.util.spec_from_file_location(
        "clean_gb30871_text", ROOT / "scripts" / "clean_gb30871_text.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_source_has_known_ocr_corruption():
    """先确认问题真实存在，避免清洗变成"无的放矢"。"""
    t = SRC.read_text(encoding="utf-8")
    assert t.count("怯") > 0, "源文件应存在 式→怯 讹字"
    assert t.count("聂") > 0, "源文件应存在 Ⅱ→聂 讹字"


def test_clean_replaces_e_and_roman_numeral():
    mod = _load()
    out = mod.clean_text("动火方怯；聂级高处作业；便携怯检测仪")
    assert "方式" in out
    assert "Ⅱ级" in out
    assert "便携式" in out
    assert "怯" not in out
    assert "聂" not in out


def test_clean_is_idempotent():
    mod = _load()
    once = mod.clean_text("样怯与方怯")
    assert mod.clean_text(once) == once


def test_clean_writes_backup_and_verifies_criteria(tmp_path):
    mod = _load()
    target = tmp_path / "std.md"
    target.write_text("动火方怯与聂级", encoding="utf-8")
    report = mod.clean_file(target, backup_dir=tmp_path / "bak")

    assert (tmp_path / "bak" / "std.md").exists(), "必须先备份原文件"
    fixed = target.read_text(encoding="utf-8")
    assert "怯" not in fixed and "聂" not in fixed
    assert report["replacements"]["怯->式"] == 1
    assert report["replacements"]["聂->Ⅱ"] == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_gb30871_clean.py -q
```

预期：FAIL（`clean_gb30871_text.py` 不存在）

- [ ] **步骤 3：编写实现**

```python
"""GB 30871-2022 标准文本 OCR 讹字清洗。

背景：该 PDF 的文本层有系统性讹字——"式"全部被识成"怯"（30 处）、
罗马数字"Ⅱ"被识成"聂"（4 处）。不修就 seed 作业票措施库，
用户会在票面上看到"动火方怯"这类错字。

用法：
    python scripts/clean_gb30871_text.py            # 就地清洗（自动备份）
    python scripts/clean_gb30871_text.py --check    # 只检查不改
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb30871_2022.md"
BACKUP_DIR = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "_backup"

# 讹字映射。只登记已确认的映射；新增必须附证据，不做猜测式替换。
REPLACEMENTS: dict[str, str] = {"怯": "式", "聂": "Ⅱ"}


def clean_text(text: str) -> str:
    out = text
    for bad, good in REPLACEMENTS.items():
        out = out.replace(bad, good)
    return out


def count_replacements(before: str) -> dict:
    return {f"{b}->{g}": before.count(b) for b, g in REPLACEMENTS.items() if before.count(b)}


def verify(text: str) -> dict:
    """判据。三项全 True 才算清洗干净。"""
    return {
        "has_zheng_shi": text.count("式") > 0,
        "no_qie": text.count("怯") == 0,
        "no_nie": text.count("聂") == 0,
    }


def clean_file(target: Path, *, backup_dir: Path | None = None, check_only: bool = False) -> dict:
    before = target.read_text(encoding="utf-8")
    after = clean_text(before)
    report = {
        "file": str(target),
        "replacements": count_replacements(before),
        "before_criteria": verify(before),
        "after_criteria": verify(after),
    }
    if check_only or before == after:
        return report
    backup_dir = backup_dir or BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_dir / target.name)
    target.write_text(after, encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查不改")
    parser.add_argument("--target", default=str(TARGET))
    args = parser.parse_args()

    report = clean_file(Path(args.target), check_only=args.check)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not all(report["after_criteria"].values()):
        print("判据未全部通过，请人工复核", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_gb30871_clean.py -v
```

预期：`4 passed`

- [ ] **步骤 5：对真实标准文件执行清洗**

运行：

```bash
python scripts/clean_gb30871_text.py
python scripts/clean_gb30871_text.py --check
```

预期：第二次 `--check` 输出里 `after_criteria` 三项全为 `true`、退出码 0；备份在 `backend/app/regulations/data/texts/_backup/reg_gb30871_2022.md`

- [ ] **步骤 6：人工抽检（不能省）**

打开 `reg_gb30871_2022.md` 抽查：

1. 附录A 表A.1 动火票的「**动火方式**」（原为"动火方怯"）
2. 附录B 表B.1 的「**Ⅱ级、Ⅲ级高处作业**」（原为"聂级"）
3. 任取 3 处含"式"的句子，确认语义通顺

> 批量替换的风险是"把对的也换错了"。`式` 与 `怯` 字形相近但语义完全不同，
> 必须人眼确认替换后的句子读得通。

- [ ] **步骤 7：Commit**

```bash
git add scripts/clean_gb30871_text.py backend/tests/test_gb30871_clean.py backend/app/regulations/data/texts/reg_gb30871_2022.md
git commit -m "fix(work-ticket): GB30871 标准文本 OCR 讹字清洗（式/Ⅱ），含备份与判据（任务 1/8）"
```

---

## 任务 2：模板层 ORM 与迁移

**文件：**

- 创建：`backend/app/models/work_ticket.py`
- 创建：`backend/db_migration_20260917_work_ticket.sql`
- 测试：`backend/tests/test_work_ticket_models.py`

**设计要点：**

- **模板驱动**：8 类票的差异落在数据里（字段定义、措施库、流程节点），不落在代码里。这是"骨架没跑通不透支 6 类"能成立的前提。
- **`is_statutory` 标记法定环节**：这是视觉走查第 2 条约束（法定环节锁定，可加不可删）的代码落点。有这个标记，服务层才能拒绝对法定节点的删除。

- [ ] **步骤 1：编写失败的测试**

```python
"""作业票模板层表结构断言。"""

import re
from pathlib import Path

from app.models.work_ticket import (
    WorkTicketFlowNode,
    WorkTicketFlowTemplate,
    WorkTicketTemplate,
    WorkTicketTemplateField,
    WorkTicketTemplateMeasure,
)

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_work_ticket.sql").read_text(encoding="utf-8")


def test_tablenames():
    assert WorkTicketTemplate.__tablename__ == "work_ticket_templates"
    assert WorkTicketTemplateField.__tablename__ == "work_ticket_template_fields"
    assert WorkTicketTemplateMeasure.__tablename__ == "work_ticket_template_measures"
    assert WorkTicketFlowTemplate.__tablename__ == "work_ticket_flow_templates"
    assert WorkTicketFlowNode.__tablename__ == "work_ticket_flow_nodes"


def test_flow_node_has_statutory_flag():
    """法定环节标记是"可加不可删"约束的落点，不能省。"""
    cols = WorkTicketFlowNode.__table__.columns
    assert "is_statutory" in cols
    assert cols["is_statutory"].nullable is False
    assert cols["sign_policy"].nullable is False


def test_measure_has_article_anchor():
    """每条安全措施必须能追溯到标准条款——这是本平台的差异化能力。"""
    cols = WorkTicketTemplateMeasure.__table__.columns
    assert "article_anchor" in cols
    assert cols["article_anchor"].nullable is False
    assert cols["measure_text"].nullable is False


def test_migration_creates_five_tables():
    for t in (
        "work_ticket_templates",
        "work_ticket_template_fields",
        "work_ticket_template_measures",
        "work_ticket_flow_templates",
        "work_ticket_flow_nodes",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{t}\b", SQL), t


def test_migration_has_node_order_unique():
    """同一流程内节点顺序必须唯一，否则审批链会出现并列。"""
    assert re.search(r"UNIQUE\s*\(flow_template_id,\s*sort_order\s*\)", SQL, re.I)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_models.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.models.work_ticket'`

- [ ] **步骤 3：编写 ORM**

```python
"""作业票模板层 ORM：票面字段、措施库、审批流程。

设计要点：
- **模板驱动**——8 类票的差异落在数据里，不落在代码里；
- `is_statutory` 标记法定审批环节，服务层据此拒绝删除（视觉走查确认的"可加不可删"）；
- 每条安全措施带 `article_anchor`，可点开看 GB 30871 原文条款。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkTicketTemplate(Base):
    """作业票模板。一个作业类型可有多条（如动火票按特级/一级/二级分）。"""

    __tablename__ = "work_ticket_templates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # DHZY/YXKJ/MBCD/GCZY/QZDZ/LSYD/PTZY/DLZY
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20))  # 特级/一级/二级 或 Ⅰ级/Ⅱ级…；不分级票为空
    is_graded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    standard_ref: Mapped[str] = mapped_column(String(80), nullable=False, default="GB 30871-2022")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fields = relationship(
        "WorkTicketTemplateField", back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )
    measures = relationship(
        "WorkTicketTemplateMeasure", back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkTicketTemplateField(Base):
    """票面字段定义。"""

    __tablename__ = "work_ticket_template_fields"
    __table_args__ = (
        UniqueConstraint("template_id", "field_key", name="uq_wttf_template_key"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    group_name: Mapped[str] = mapped_column(String(40), nullable=False, default="基本信息")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    validation: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    allow_ai_prefill: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template = relationship("WorkTicketTemplate", back_populates="fields", lazy="selectin")


class WorkTicketTemplateMeasure(Base):
    """该模板的必备安全措施，逐条来自 GB 30871 第 5~12 章。"""

    __tablename__ = "work_ticket_template_measures"
    __table_args__ = (Index("idx_wttm_template_order", "template_id", "sort_order"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="CASCADE"), nullable=False
    )
    measure_text: Mapped[str] = mapped_column(Text, nullable=False)
    article_anchor: Mapped[str] = mapped_column(String(120), nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template = relationship("WorkTicketTemplate", back_populates="measures", lazy="selectin")


class WorkTicketFlowTemplate(Base):
    """审批流程模板。企业可对同一作业票类型配多条流程。"""

    __tablename__ = "work_ticket_flow_templates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    nodes = relationship(
        "WorkTicketFlowNode",
        back_populates="flow_template",
        cascade="all, delete-orphan",
        order_by="WorkTicketFlowNode.sort_order",
        lazy="selectin",
    )


class WorkTicketFlowNode(Base):
    """审批节点。

    `is_statutory=True` 表示该节点由 GB 30871 附录B 表B.1 法定要求，
    企业可以改绑定的角色、可以在其前后插入自有节点，**但不能删除**。
    """

    __tablename__ = "work_ticket_flow_nodes"
    __table_args__ = (
        UniqueConstraint("flow_template_id", "sort_order", name="uq_wtfn_flow_order"),
        UniqueConstraint("flow_template_id", "node_key", name="uq_wtfn_flow_key"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    flow_template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_flow_templates.id", ondelete="CASCADE"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    role_code: Mapped[Optional[str]] = mapped_column(String(30))  # 绑定既有 Role.code
    sign_policy: Mapped[str] = mapped_column(String(10), nullable=False, default="any")  # any|all
    condition_expr: Mapped[Optional[str]] = mapped_column(String(200))  # 受限表达式
    reject_to: Mapped[str] = mapped_column(String(20), nullable=False, default="previous")  # previous|submitter
    is_statutory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_hours: Mapped[Optional[int]] = mapped_column(Integer)

    flow_template = relationship("WorkTicketFlowTemplate", back_populates="nodes", lazy="selectin")
```

- [ ] **步骤 4：编写迁移 DDL**

```sql
-- 20260917 作业票模板层（票面字段 / 措施库 / 审批流程 / 流程节点）
-- 要点：is_statutory 标记法定审批环节，服务层据此拒绝删除（"可加不可删"）。

CREATE TABLE IF NOT EXISTS work_ticket_templates (
    id UUID PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    level VARCHAR(20),
    is_graded BOOLEAN NOT NULL DEFAULT FALSE,
    standard_ref VARCHAR(80) NOT NULL DEFAULT 'GB 30871-2022',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_wtt_code_level
    ON work_ticket_templates (code, COALESCE(level, ''));

CREATE TABLE IF NOT EXISTS work_ticket_template_fields (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE CASCADE,
    field_key VARCHAR(60) NOT NULL,
    label VARCHAR(200) NOT NULL,
    field_type VARCHAR(20) NOT NULL DEFAULT 'text',
    group_name VARCHAR(40) NOT NULL DEFAULT '基本信息',
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    options JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    allow_ai_prefill BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_wttf_template_key UNIQUE (template_id, field_key)
);

CREATE TABLE IF NOT EXISTS work_ticket_template_measures (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE CASCADE,
    measure_text TEXT NOT NULL,
    article_anchor VARCHAR(120) NOT NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_wttm_template_order
    ON work_ticket_template_measures (template_id, sort_order);

CREATE TABLE IF NOT EXISTS work_ticket_flow_templates (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS work_ticket_flow_nodes (
    id UUID PRIMARY KEY,
    flow_template_id UUID NOT NULL REFERENCES work_ticket_flow_templates(id) ON DELETE CASCADE,
    node_key VARCHAR(60) NOT NULL,
    name VARCHAR(200) NOT NULL,
    sort_order INTEGER NOT NULL,
    role_code VARCHAR(30),
    sign_policy VARCHAR(10) NOT NULL DEFAULT 'any',
    condition_expr VARCHAR(200),
    reject_to VARCHAR(20) NOT NULL DEFAULT 'previous',
    is_statutory BOOLEAN NOT NULL DEFAULT FALSE,
    timeout_hours INTEGER,
    CONSTRAINT uq_wtfn_flow_order UNIQUE (flow_template_id, sort_order),
    CONSTRAINT uq_wtfn_flow_key UNIQUE (flow_template_id, node_key)
);
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_models.py -v
```

预期：`5 passed`

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/work_ticket.py backend/db_migration_20260917_work_ticket.sql backend/tests/test_work_ticket_models.py
git commit -m "feat(work-ticket): 模板层 ORM 与迁移（字段/措施/流程/节点，含法定环节标记）（任务 2/8）"
```

---

## 任务 3：GB 30871 附录A/B 数据化（种子生成器）

**文件：**

- 创建：`backend/app/services/work_ticket_seed_data.py`（人工整理的常量，附条款出处）
- 创建：`backend/seed_work_ticket_templates.py`（生成确定性 UUID5 的种子 SQL）
- 创建：`backend/db_migration_20260917_work_ticket_seed.sql`（由脚本生成）
- 测试：`backend/tests/test_work_ticket_seed.py`

**为什么是"半自动"而不是纯解析：**

附录A 的表格是从 PDF 转出来的 markdown，结构不完全规整（合并单元格、跨行说明、图片公式）。纯自动解析**票面字段**与**审批矩阵**容易错，而这两块体量很小（每类票约 15 个字段、审批矩阵 4 行）——**人工抄录并标注出处，比写解析器更快也更可靠**。

而**措施清单**数量大（动火票 20+ 条），且格式规整（表格每行一条），适合解析。

结论：字段与审批矩阵用常量表；措施清单自动解析。

- [ ] **步骤 1：编写失败的测试**

```python
"""作业票种子：常量表结构与措施解析。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_data_covers_two_types_with_levels():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    codes = {t["code"] for t in mod.TEMPLATES}
    assert codes == {"DHZY", "YXKJ"}, "计划 8 只做动火与受限空间"
    dhzy_levels = {t["level"] for t in mod.TEMPLATES if t["code"] == "DHZY"}
    assert dhzy_levels == {"特级", "一级", "二级"}, "动火票按等级分三种模板"


def test_every_field_has_group_and_key():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    for tpl in mod.TEMPLATES:
        assert tpl["fields"], f"{tpl['name']} 没有票面字段"
        for f in tpl["fields"]:
            assert f["field_key"] and f["label"] and f["group_name"]


def test_approval_matrix_matches_standard_table_b1():
    """审批矩阵必须与 GB 30871 附录B 表B.1 一致。"""
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    m = {(r["code"], r["level"]): r["approver"] for r in mod.APPROVAL_MATRIX}
    assert m[("DHZY", "特级")] == "主管领导"
    assert m[("DHZY", "一级")] == "安全管理部门"
    assert m[("DHZY", "二级")] == "所在基层单位"
    assert m[("YXKJ", None)] == "所在基层单位"


def test_parse_measures_from_appendix_a():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    text = (ROOT / "backend/app/regulations/data/texts/reg_gb_30871_2022.md").read_text(
        encoding="utf-8"
    )
    measures = mod.parse_measures(text, chapter=5)
    assert len(measures) >= 10, f"动火作业措施应不少于 10 条，实际 {len(measures)}"
    for m in measures:
        assert m["measure_text"] and m["article_anchor"].startswith("GB 30871-2022")


def test_parse_measures_rejects_empty_text():
    mod = _load("wt_seed", "backend/app/services/work_ticket_seed_data.py")
    assert mod.parse_measures("", chapter=5) == []


def test_build_sql_is_deterministic():
    mod = _load("wt_seed_gen", "backend/seed_work_ticket_templates.py")
    a = mod.build_sql()
    b = mod.build_sql()
    assert a == b, "两次生成必须逐字节一致"
    assert "ON CONFLICT (id) DO NOTHING" in a
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_seed.py -q
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：编写常量与解析**

```python
"""GB 30871-2022 附录A/B 的种子数据与措施解析。

为什么字段与审批矩阵用常量表而不是解析：
附录A 的表格由 PDF 转换而来，存在合并单元格与跨行说明，纯解析易错，
而这两块体量很小（每类票约 15 字段、审批矩阵 4 行）。
人工抄录并标注出处更可靠；数量大的措施清单才值得写解析器。
"""

from __future__ import annotations

import re

STANDARD_REF = "GB 30871-2022"

# 依据：GB 30871-2022 附录B 表B.1「安全作业票的办理、审批内容」
# 说明：办理部门一列对动火票统一为"危险化学品企业"，此处不重复存储。
APPROVAL_MATRIX: list[dict] = [
    {"code": "DHZY", "level": "特级", "approver": "主管领导"},
    {"code": "DHZY", "level": "一级", "approver": "安全管理部门"},
    {"code": "DHZY", "level": "二级", "approver": "所在基层单位"},
    {"code": "YXKJ", "level": None, "approver": "所在基层单位"},
]

# 依据：GB 30871-2022 附录A 表A.1（动火安全作业票）、表A.2（受限空间安全作业票）
# 字段清单为人工抄录，group_name 用于开票向导的分步。
_COMMON_TAIL_FIELDS = [
    {"field_key": "risk_identification", "label": "风险辨识结果", "field_type": "textarea",
     "group_name": "危害因素", "is_required": True, "allow_ai_prefill": True},
    {"field_key": "related_tickets", "label": "关联的其他特殊作业及安全作业票编号",
     "field_type": "text", "group_name": "基本信息", "is_required": False},
]

TEMPLATES: list[dict] = [
    {
        "code": "DHZY",
        "name": "动火安全作业票",
        "level": "特级",
        "is_graded": True,
        "chapter": 5,
        "fields": [
            {"field_key": "applicant_unit", "label": "作业申请单位", "field_type": "text",
             "group_name": "基本信息", "is_required": True},
            {"field_key": "apply_time", "label": "作业申请时间", "field_type": "datetime",
             "group_name": "基本信息", "is_required": True},
            {"field_key": "work_content", "label": "作业内容", "field_type": "textarea",
             "group_name": "作业内容", "is_required": True, "allow_ai_prefill": True},
            {"field_key": "fire_location", "label": "动火地点及动火部位", "field_type": "text",
             "group_name": "作业内容", "is_required": True},
            {"field_key": "fire_level", "label": "动火作业级别", "field_type": "select",
             "group_name": "作业内容", "is_required": True,
             "options": {"choices": ["特级", "一级", "二级"]}},
            {"field_key": "fire_method", "label": "动火方式", "field_type": "text",
             "group_name": "作业内容", "is_required": True},
            {"field_key": "fire_person", "label": "动火人及证书编号", "field_type": "text",
             "group_name": "人员", "is_required": True},
            {"field_key": "work_unit", "label": "作业单位", "field_type": "text",
             "group_name": "基本信息", "is_required": True},
            {"field_key": "work_leader", "label": "作业负责人", "field_type": "text",
             "group_name": "人员", "is_required": True},
            {"field_key": "work_period", "label": "动火作业实施时间", "field_type": "datetimerange",
             "group_name": "基本信息", "is_required": True},
            *_COMMON_TAIL_FIELDS,
        ],
    },
    {
        "code": "YXKJ",
        "name": "受限空间安全作业票",
        "level": None,
        "is_graded": False,
        "chapter": 6,
        "fields": [
            {"field_key": "applicant_unit", "label": "作业申请单位", "field_type": "text",
             "group_name": "基本信息", "is_required": True},
            {"field_key": "apply_time", "label": "作业申请时间", "field_type": "datetime",
             "group_name": "基本信息", "is_required": True},
            {"field_key": "space_location", "label": "受限空间名称及位置", "field_type": "text",
             "group_name": "作业内容", "is_required": True},
            {"field_key": "work_content", "label": "作业内容", "field_type": "textarea",
             "group_name": "作业内容", "is_required": True, "allow_ai_prefill": True},
            {"field_key": "work_unit", "label": "作业单位", "field_type": "text",
             "group_name": "基本信息", "is_required": True},
            {"field_key": "work_leader", "label": "作业负责人", "field_type": "text",
             "group_name": "人员", "is_required": True},
            {"field_key": "guardian", "label": "监护人", "field_type": "text",
             "group_name": "人员", "is_required": True},
            {"field_key": "work_period", "label": "作业实施时间", "field_type": "datetimerange",
             "group_name": "基本信息", "is_required": True},
            *_COMMON_TAIL_FIELDS,
        ],
    },
]

_MEASURE_ROW = re.compile(r"^\|\s*\d+\s*\|\s*(?P<text>[^|]{4,})\|")


def parse_measures(text: str, *, chapter: int) -> list[dict]:
    """从附录A 的措施表格里抽出措施条目。

    只认「序号 | 措施正文 | 是否涉及 | 确认人」这种四列行；
    条款锚点按章节号生成（如第 5 章 → GB 30871-2022 5）。
    """
    if not text:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        m = _MEASURE_ROW.match(line.strip())
        if not m:
            continue
        measure = m.group("text").strip()
        if len(measure) < 6:
            continue
        out.append(
            {
                "measure_text": measure,
                "article_anchor": f"{STANDARD_REF} {chapter}",
                "is_mandatory": True,
                "sort_order": len(out) + 1,
            }
        )
    return out
```

- [ ] **步骤 4：编写种子 SQL 生成器**

```python
"""生成作业票模板种子 SQL（确定性 UUID5，可重复执行）。

用法：python backend/seed_work_ticket_templates.py
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "db_migration_20260917_work_ticket_seed.sql"
STANDARD_TEXT = (
    ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
)
NS = uuid.NAMESPACE_URL
NS_PREFIX = "work-ticket/GB30871-2022/"


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "wt_seed", ROOT / "backend" / "app" / "services" / "work_ticket_seed_data.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{NS_PREFIX}{kind}/{key}"))


def _q(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _bool(v: bool) -> str:
    return "TRUE" if v else "FALSE"


def build_sql() -> str:
    seed = _load_seed()
    text = STANDARD_TEXT.read_text(encoding="utf-8")

    lines = [
        "-- 20260917 作业票模板种子（由 backend/seed_work_ticket_templates.py 生成，勿手改）",
        "-- 依据：GB 30871-2022 附录A（票面样式与措施）、附录B 表B.1（审批矩阵）。",
        "-- id 使用 uuid5(NAMESPACE_URL, 'work-ticket/GB30871-2022/<表>/<自然键>')，配 ON CONFLICT (id) DO NOTHING。",
        "",
    ]

    for tpl in seed.TEMPLATES:
        tpl_key = f"{tpl['code']}/{tpl['level'] or 'NA'}"
        tpl_id = _uid("template", tpl_key)
        lines.append(
            "INSERT INTO work_ticket_templates "
            "(id, code, name, level, is_graded, standard_ref, is_enabled, sort_order) "
            f"VALUES ({_q(tpl_id)}, {_q(tpl['code'])}, {_q(tpl['name'])}, "
            f"{_q(tpl['level']) if tpl['level'] else 'NULL'}, {_bool(tpl['is_graded'])}, "
            f"{_q(seed.STANDARD_REF)}, TRUE, {seed.TEMPLATES.index(tpl)}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

        for idx, f in enumerate(tpl["fields"], start=1):
            fid = _uid("field", f"{tpl_key}/{f['field_key']}")
            options = f.get("options") or {}
            lines.append(
                "INSERT INTO work_ticket_template_fields "
                "(id, template_id, field_key, label, field_type, group_name, "
                "is_required, options, allow_ai_prefill, sort_order) VALUES "
                f"({_q(fid)}, {_q(tpl_id)}, {_q(f['field_key'])}, {_q(f['label'])}, "
                f"{_q(f['field_type'])}, {_q(f['group_name'])}, {_bool(f.get('is_required', False))}, "
                f"{_q(__import__('json').dumps(options, ensure_ascii=False))}::jsonb, "
                f"{_bool(f.get('allow_ai_prefill', False))}, {idx}) "
                "ON CONFLICT (id) DO NOTHING;"
            )

        for m in seed.parse_measures(text, chapter=tpl["chapter"]):
            mid = _uid("measure", f"{tpl_key}/{m['sort_order']}")
            lines.append(
                "INSERT INTO work_ticket_template_measures "
                "(id, template_id, measure_text, article_anchor, is_mandatory, sort_order) "
                f"VALUES ({_q(mid)}, {_q(tpl_id)}, {_q(m['measure_text'])}, "
                f"{_q(m['article_anchor'])}, TRUE, {m['sort_order']}) "
                "ON CONFLICT (id) DO NOTHING;"
            )

        flow_id = _uid("flow", tpl_key)
        approver = next(
            (
                r["approver"]
                for r in seed.APPROVAL_MATRIX
                if r["code"] == tpl["code"] and r["level"] == tpl["level"]
            ),
            None,
        )
        lines.append(
            "INSERT INTO work_ticket_flow_templates (id, template_id, name, is_active) "
            f"VALUES ({_q(flow_id)}, {_q(tpl_id)}, {_q(tpl['name'] + ' 审批流程')}, TRUE) "
            "ON CONFLICT (id) DO NOTHING;"
        )
        if approver:
            node_id = _uid("node", f"{tpl_key}/approve")
            lines.append(
                "INSERT INTO work_ticket_flow_nodes "
                "(id, flow_template_id, node_key, name, sort_order, role_code, "
                "sign_policy, reject_to, is_statutory) VALUES "
                f"({_q(node_id)}, {_q(flow_id)}, 'approve', {_q(approver + '审批')}, 1, "
                f"{_q(approver)}, 'any', 'submitter', TRUE) "
                "ON CONFLICT (id) DO NOTHING;"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    sql = build_sql()
    OUT.write_text(sql, encoding="utf-8", newline="\n")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(sql.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 5：生成并校验**

运行：

```bash
python backend/seed_work_ticket_templates.py
python backend/seed_work_ticket_templates.py && sha256sum backend/db_migration_20260917_work_ticket_seed.sql
```

预期：两次 sha256 一致（幂等）；文件含 2 个模板、约 22 个字段、若干措施、2 条流程与 2 个法定节点

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_seed.py -v
```

预期：`6 passed`

- [ ] **步骤 7：人工核对种子内容**

打开生成的 SQL，确认：

1. 动火三个等级的 `work_ticket_templates` 各一行
2. `work_ticket_flow_nodes` 里 **`is_statutory` 全为 TRUE**（法定环节）
3. 审批人与表B.1 一致（特级→主管领导、一级→安全管理部门、二级→所在基层单位、受限空间→所在基层单位）
4. 措施文本里**没有"怯"字**（任务 1 的清洗生效了）

- [ ] **步骤 8：Commit**

```bash
git add backend/app/services/work_ticket_seed_data.py backend/seed_work_ticket_templates.py backend/db_migration_20260917_work_ticket_seed.sql backend/tests/test_work_ticket_seed.py
git commit -m "feat(work-ticket): 附录A/B 数据化种子（票面字段+措施库+法定审批矩阵）（任务 3/8）"
```

---

## 任务 4：轻量审批引擎

**文件：**

- 创建：`backend/app/services/work_ticket_flow.py`
- 测试：`backend/tests/test_work_ticket_flow.py`

**沿用 `hazard_state_machine.py` 的范式**（`TRANSITIONS` + `ROLE_GATE`），保持两个模块的一致性——同一个项目里两套状态机写法会让人困惑。

**三件事是本引擎特有的：**

1. **会签 vs 或签**（`sign_policy`：`all` 需全部通过，`any` 一人通过即可）
2. **受限条件分支**（只支持字段比较，不引入通用表达式引擎）
3. **法定环节不可删**（`is_statutory=True` 的节点拒绝删除）

- [ ] **步骤 1：编写失败的测试**

```python
"""作业票审批引擎：状态机、会签、条件分支、法定环节保护。"""

from unittest.mock import MagicMock

import pytest

from app.services.work_ticket_flow import (
    FlowError,
    TRANSITIONS,
    can_transition,
    evaluate_condition,
    is_node_active,
    next_node,
    sign_requirement_met,
    validate_node_deletion,
)


def _node(key, order, policy="any", cond=None, statutory=False, role="mgr"):
    n = MagicMock()
    n.node_key = key
    n.sort_order = order
    n.sign_policy = policy
    n.condition_expr = cond
    n.is_statutory = statutory
    n.role_code = role
    n.name = key
    return n


def test_transitions_table_shape():
    assert set(TRANSITIONS) >= {
        "draft", "submitted", "approving", "approved",
        "rejected", "cancelled", "working", "finished", "closed", "expired",
    }
    assert "approve" in TRANSITIONS["approving"]
    assert "reject" in TRANSITIONS["approving"]


def test_can_transition_allows_legal_action():
    assert can_transition("approving", "approve") is True


def test_can_transition_rejects_illegal_action():
    """已归档的票不能再审批。"""
    assert can_transition("closed", "approve") is False


def test_can_transition_rejects_expired_resume():
    """已过期的票不能直接进入作业中，必须重新开票。"""
    assert can_transition("expired", "start") is False


def test_evaluate_condition_simple_equality():
    assert evaluate_condition("level == 特级", {"level": "特级"}) is True
    assert evaluate_condition("level == 特级", {"level": "一级"}) is False


def test_evaluate_condition_in_operator():
    assert evaluate_condition("level in [特级, 一级]", {"level": "一级"}) is True
    assert evaluate_condition("level in [特级, 一级]", {"level": "二级"}) is False


def test_evaluate_condition_boolean_field():
    assert evaluate_condition("is_cross_dept == true", {"is_cross_dept": True}) is True
    assert evaluate_condition("is_cross_dept == true", {"is_cross_dept": False}) is False


def test_evaluate_condition_empty_means_always_active():
    assert evaluate_condition(None, {}) is True
    assert evaluate_condition("", {}) is True


def test_evaluate_condition_unknown_field_is_false_not_crash():
    """字段不存在时返回 False，不抛异常——流程不能因为少一个字段就崩。"""
    assert evaluate_condition("level == 特级", {}) is False


def test_evaluate_condition_rejects_unsupported_syntax():
    """不支持的语法必须报错，不能静默放行——静默放行等于绕过审批。"""
    with pytest.raises(FlowError):
        evaluate_condition("__import__('os').system('ls')", {"level": "一级"})


def test_is_node_active_uses_condition():
    assert is_node_active(_node("a", 1, cond="level == 一级"), {"level": "一级"}) is True
    assert is_node_active(_node("a", 1, cond="level == 一级"), {"level": "二级"}) is False


def test_sign_requirement_met_any():
    node = _node("a", 1, policy="any")
    assert sign_requirement_met(node, signed_users=["u1"], eligible_users=[]) is True


def test_sign_requirement_met_all_needs_everyone():
    node = _node("a", 1, policy="all")
    assert sign_requirement_met(node, signed_users=["u1"], eligible_users=["u1", "u2"]) is False
    assert sign_requirement_met(node, signed_users=["u1", "u2"], eligible_users=["u1", "u2"]) is True


def test_sign_requirement_met_all_with_no_eligible_users():
    """节点没配人时不能判定为已签，否则审批会被空跳过。"""
    node = _node("a", 1, policy="all")
    assert sign_requirement_met(node, signed_users=[], eligible_users=[]) is False


def test_next_node_skips_inactive_branches():
    nodes = [
        _node("approve_special", 1, cond="level == 特级"),
        _node("approve_first", 2, cond="level == 一级"),
        _node("approve_second", 3, cond="level == 二级"),
    ]
    nxt = next_node(nodes, current_order=0, ctx={"level": "一级"})
    assert nxt.node_key == "approve_first"


def test_next_node_returns_none_when_finished():
    nodes = [_node("approve", 1)]
    assert next_node(nodes, current_order=1, ctx={}) is None


def test_validate_node_deletion_blocks_statutory():
    """法定环节不可删——这是"平台不提供绕过合规的开关"的代码落点。"""
    with pytest.raises(FlowError) as ei:
        validate_node_deletion(_node("approve", 1, statutory=True))
    assert "法定" in str(ei.value)


def test_validate_node_deletion_allows_custom():
    validate_node_deletion(_node("custom", 2, statutory=False))
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_flow.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""作业票轻量审批引擎。

三次设计决策（见 spec §7.4）：
1. **不引入 BPMN 引擎**——8 类票的流程本质是固定骨架 + 少量条件分支，
   且标准附录B 表B.1 已给定审批人；Flowable/Camunda 是 Java 服务，
   与 Python 栈不匹配且 AI 难介入解释；
2. **条件表达式受限**——只支持字段比较，不引入通用表达式引擎。
   安全是次要的，主要理由是"人一眼能看懂这条分支为什么这么走"；
3. **法定环节不可删**——`is_statutory=True` 的节点拒绝删除，
   与"法定必填项一律阻断"同属一条原则：平台不提供绕过合规的开关。
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence


class FlowError(ValueError):
    """流程配置或流转非法。"""


# 状态机。与 app/services/hazard_state_machine.py 同构，保持项目内一致性。
TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submit", "cancel"},
    "submitted": {"start_review", "cancel"},
    "approving": {"approve", "reject", "cancel"},
    "rejected": {"submit", "cancel"},
    "approved": {"start", "cancel", "expire"},
    "working": {"finish"},
    "finished": {"close"},
    "closed": set(),
    "cancelled": set(),
    "expired": set(),  # 已过期只能重新开票，不能恢复
}


def can_transition(status: str, action: str) -> bool:
    return action in TRANSITIONS.get(status, set())


# --- 条件表达式（受限） ---------------------------------------------------

_EQ = re.compile(r"^(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*(?P<value>.+)$")
_IN = re.compile(r"^(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+\[(?P<items>[^\]]*)\]$")


def _norm(value: Any) -> str:
    """统一比较口径：布尔转小写字符串，其余去空白转字符串。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def evaluate_condition(expr: Optional[str], ctx: dict) -> bool:
    """求值受限条件表达式。空表达式恒为真；字段缺失返回 False。"""
    if not expr or not expr.strip():
        return True
    text = expr.strip()

    m = _EQ.match(text)
    if m:
        field, expected = m.group("field"), m.group("value").strip()
        if field not in ctx:
            return False
        return _norm(ctx[field]) == _norm(expected)

    m = _IN.match(text)
    if m:
        field = m.group("field")
        if field not in ctx:
            return False
        items = [i.strip() for i in m.group("items").split(",") if i.strip()]
        return _norm(ctx[field]) in {_norm(i) for i in items}

    raise FlowError(
        f"不支持的条件表达式：{expr!r}。只允许 `字段 == 值` 或 `字段 in [值1, 值2]` 两种形式"
    )


def is_node_active(node, ctx: dict) -> bool:
    """该节点在当前作业票数据下是否需要走（条件分支命中与否）。"""
    return evaluate_condition(getattr(node, "condition_expr", None), ctx)


# --- 会签 -----------------------------------------------------------------


def sign_requirement_met(node, *, signed_users: Sequence[str], eligible_users: Sequence[str]) -> bool:
    """判断节点签署是否已完成。

    - `any`：有一人签即可；
    - `all`：所有有资格的人都要签。**没配有资格的人时判定为未完成**——
      否则一个空节点会被当成"已通过"，审批被静默跳过。
    """
    policy = getattr(node, "sign_policy", "any")
    signed = {u for u in signed_users if u}
    if policy == "any":
        return bool(signed)
    if policy == "all":
        eligible = {u for u in eligible_users if u}
        if not eligible:
            return False
        return eligible <= signed
    raise FlowError(f"未知会签策略：{policy!r}，只允许 any / all")


# --- 节点推进 -------------------------------------------------------------


def next_node(nodes: Sequence, *, current_order: int, ctx: dict):
    """返回 current_order 之后第一个「条件命中」的节点；没有则返回 None（流程结束）。"""
    ordered = sorted(nodes, key=lambda n: n.sort_order)
    for node in ordered:
        if node.sort_order <= current_order:
            continue
        if is_node_active(node, ctx):
            return node
    return None


def validate_node_deletion(node) -> None:
    """删除节点前的校验。法定环节一律拒绝。"""
    if getattr(node, "is_statutory", False):
        raise FlowError(
            f"节点「{getattr(node, 'name', '')}」是 GB 30871 附录B 规定的法定审批环节，"
            "不允许删除；如需调整可改绑定的角色或在其前后插入自有节点"
        )
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_flow.py -v
```

预期：`18 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/work_ticket_flow.py backend/tests/test_work_ticket_flow.py
git commit -m "feat(work-ticket): 轻量审批引擎（状态机+受限条件分支+会签+法定环节保护）（任务 4/8）"
```

---

## 任务 5：实例层 ORM 与迁移

**文件：**

- 修改：`backend/app/models/work_ticket.py`（追加实例层与留痕层）
- 修改：`backend/db_migration_20260917_work_ticket.sql`（追加 DDL）
- 测试：`backend/tests/test_work_ticket_models.py`（追加）

**设计要点：**

- `level` 存在实例上——它是**审批条件分支的依据字段**（`level == 特级` 决定走哪个节点），不能只留在 `values` JSONB 里靠字符串搜。
- `code` 的唯一约束是 `(enterprise_id, code)`——**编号并发防重靠数据库，不靠应用层查重**。
- `valid_from` / `valid_to` + `ix_wti_valid_to` 索引：有效期到期扫描要能走索引，否则票据一多调度器会慢。

- [ ] **步骤 1：编写失败的测试（追加）**

```python
from app.models.work_ticket import (
    WorkTicketAuditLog,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketNodeRecord,
    WorkTicketPrintSnapshot,
)


def test_instance_tablenames():
    assert WorkTicketInstance.__tablename__ == "work_ticket_instances"
    assert WorkTicketNodeRecord.__tablename__ == "work_ticket_node_records"
    assert WorkTicketGasTest.__tablename__ == "work_ticket_gas_tests"
    assert WorkTicketAuditLog.__tablename__ == "work_ticket_audit_logs"
    assert WorkTicketPrintSnapshot.__tablename__ == "work_ticket_print_snapshots"


def test_instance_has_level_for_condition_branching():
    """level 必须是独立列——审批条件分支依赖它，藏在 JSONB 里搜不动。"""
    cols = WorkTicketInstance.__table__.columns
    assert "level" in cols
    assert "current_order" in cols
    assert "valid_to" in cols
    assert cols["status"].nullable is False


def test_instance_enterprise_code_unique():
    names = {c.name for c in WorkTicketInstance.__table__.constraints if hasattr(c, "name")}
    assert "uq_wti_ent_code" in names


def test_gas_test_requires_sampled_at():
    cols = WorkTicketGasTest.__table__.columns
    assert cols["sampled_at"].nullable is False


def test_print_snapshot_has_hash_and_version():
    cols = WorkTicketPrintSnapshot.__table__.columns
    assert cols["content_hash"].nullable is False
    assert cols["snapshot"].nullable is False


def test_migration_creates_instance_tables():
    for t in (
        "work_ticket_instances",
        "work_ticket_node_records",
        "work_ticket_gas_tests",
        "work_ticket_audit_logs",
        "work_ticket_print_snapshots",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{t}\b", SQL), t


def test_migration_indexes_valid_to():
    """有效期到期扫描要走索引，否则票据一多调度器就慢。"""
    assert re.search(r"INDEX[^\n]*work_ticket_instances\s*\(valid_to\)", SQL, re.I)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_models.py -q
```

预期：`ImportError: cannot import name 'WorkTicketInstance'`

- [ ] **步骤 3：追加 ORM（到 `backend/app/models/work_ticket.py` 末尾）**

```python
class WorkTicketInstance(Base):
    """作业票实例。编号规则 {类型}-{企业码}-{YYYYMMDD}-{4位序号}。"""

    __tablename__ = "work_ticket_instances"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "code", name="uq_wti_ent_code"),
        Index("idx_wti_enterprise_status", "enterprise_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_templates.id", ondelete="RESTRICT"), nullable=False
    )
    flow_template_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_flow_templates.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_type: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    current_node_key: Mapped[Optional[str]] = mapped_column(String(60))
    current_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    values: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    extend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text)
    submitted_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkTicketNodeRecord(Base):
    """节点办理记录。"""

    __tablename__ = "work_ticket_node_records"
    __table_args__ = (Index("idx_wtnr_instance", "instance_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    opinion: Mapped[Optional[str]] = mapped_column(Text)
    acted_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkTicketGasTest(Base):
    """气体检测记录。动火/受限空间类为提交前必填，一次作业可多次取样。"""

    __tablename__ = "work_ticket_gas_tests"
    __table_args__ = (Index("idx_wtgt_instance", "instance_id", "sampled_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    gas_type: Mapped[Optional[str]] = mapped_column(String(100))
    result: Mapped[Optional[str]] = mapped_column(String(100))
    tester: Mapped[Optional[str]] = mapped_column(String(100))
    conclusion: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkTicketAuditLog(Base):
    """全状态变更留痕（对齐 HazardAuditLog）。"""

    __tablename__ = "work_ticket_audit_logs"
    __table_args__ = (Index("idx_wtal_instance", "instance_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20))
    to_status: Mapped[Optional[str]] = mapped_column(String(20))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    acted_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkTicketPrintSnapshot(Base):
    """打印快照。打印即固化，之后只能新建版本。"""

    __tablename__ = "work_ticket_print_snapshots"
    __table_args__ = (UniqueConstraint("instance_id", "version", name="uq_wtps_instance_version"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("work_ticket_instances.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    printed_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **步骤 4：追加迁移 DDL（到 `backend/db_migration_20260917_work_ticket.sql` 末尾）**

```sql
CREATE TABLE IF NOT EXISTS work_ticket_instances (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES work_ticket_templates(id) ON DELETE RESTRICT,
    flow_template_id UUID REFERENCES work_ticket_flow_templates(id) ON DELETE SET NULL,
    code VARCHAR(64) NOT NULL,
    ticket_type VARCHAR(20) NOT NULL,
    level VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    current_node_key VARCHAR(60),
    current_order INTEGER NOT NULL DEFAULT 0,
    values JSONB NOT NULL DEFAULT '{}'::jsonb,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    extend_count INTEGER NOT NULL DEFAULT 0,
    cancel_reason TEXT,
    submitted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_wti_ent_code UNIQUE (enterprise_id, code)
);
CREATE INDEX IF NOT EXISTS idx_wti_enterprise_status ON work_ticket_instances (enterprise_id, status);
CREATE INDEX IF NOT EXISTS ix_wti_valid_to ON work_ticket_instances (valid_to);

CREATE TABLE IF NOT EXISTS work_ticket_node_records (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    node_key VARCHAR(60) NOT NULL,
    action VARCHAR(20) NOT NULL,
    opinion TEXT,
    acted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtnr_instance ON work_ticket_node_records (instance_id, created_at);

CREATE TABLE IF NOT EXISTS work_ticket_gas_tests (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    sampled_at TIMESTAMPTZ NOT NULL,
    location VARCHAR(200),
    gas_type VARCHAR(100),
    result VARCHAR(100),
    tester VARCHAR(100),
    conclusion VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtgt_instance ON work_ticket_gas_tests (instance_id, sampled_at);

CREATE TABLE IF NOT EXISTS work_ticket_audit_logs (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    action VARCHAR(30) NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    acted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtal_instance ON work_ticket_audit_logs (instance_id, created_at);

CREATE TABLE IF NOT EXISTS work_ticket_print_snapshots (
    id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES work_ticket_instances(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    content_hash VARCHAR(64) NOT NULL,
    snapshot JSONB NOT NULL,
    printed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_wtps_instance_version UNIQUE (instance_id, version)
);
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_models.py -v
```

预期：`12 passed`（模板层 5 + 实例层 7）

- [ ] **步骤 6：验证迁移幂等**

```bash
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_work_ticket.sql
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_work_ticket.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "\dt work_ticket*"
```

预期：两次执行均无报错；列出 10 张 `work_ticket_*` 表

- [ ] **步骤 7：Commit**

```bash
git add backend/app/models/work_ticket.py backend/db_migration_20260917_work_ticket.sql backend/tests/test_work_ticket_models.py
git commit -m "feat(work-ticket): 实例层 ORM 与迁移（实例/节点记录/气体检测/留痕/打印快照）（任务 5/8）"
```

---

## 任务 6：开票到归档的服务编排 + 提交前合规校验

**文件：**

- 创建：`backend/app/services/work_ticket_service.py`
- 测试：`backend/tests/test_work_ticket_service.py`

**提交前合规校验是本任务的重点。** spec §7.8 定的规则：**涉及法定必填项与证件有效期时，无论 AI 开关取值一律阻断**——这条在代码里的落点就是 `validate_before_submit()`，它**不接受任何"跳过校验"的参数**。

- [ ] **步骤 1：编写失败的测试**

```python
"""作业票服务：编号生成、提交校验、审批推进、有效期。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.work_ticket_service import (
    SubmitValidationError,
    build_ticket_code,
    next_code_seq,
    validate_before_submit,
)


def test_build_ticket_code_format():
    code = build_ticket_code("DHZY", "TYKJ", datetime(2026, 9, 17), 1)
    assert code == "DHZY-TYKJ-20260917-0001"


def test_build_ticket_code_pads_to_four_digits():
    assert build_ticket_code("YXKJ", "A", datetime(2026, 1, 2), 42).endswith("-0042")


def test_next_code_seq_starts_at_one():
    assert next_code_seq([]) == 1


def test_next_code_seq_increments_from_max():
    """取当天已有序号的最大值 +1，避免删除中间记录后重号。"""
    existing = ["DHZY-A-20260917-0001", "DHZY-A-20260917-0003"]
    assert next_code_seq(existing) == 4


def test_next_code_seq_ignores_malformed_codes():
    assert next_code_seq(["DHZY-A-20260917-0002", "垃圾数据"]) == 3


def _tpl(required=("work_content",), allow_ai=True):
    fields = []
    for key in required:
        f = MagicMock()
        f.field_key = key
        f.label = key
        f.is_required = True
        fields.append(f)
    tpl = MagicMock()
    tpl.fields = fields
    tpl.code = "DHZY"
    return tpl


def _measures(count=2):
    out = []
    for i in range(count):
        m = MagicMock()
        m.is_mandatory = True
        m.measure_text = f"措施{i}"
        m.sort_order = i + 1
        out.append(m)
    return out


def _now():
    return datetime.now(timezone.utc)


def test_validate_flags_missing_required_field():
    errs = validate_before_submit(
        template=_tpl(required=("work_content",)),
        values={},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[{"sampled_at": _now()}],
        requires_gas_test=True,
    )
    assert any("work_content" in e for e in errs)


def test_validate_flags_unconfirmed_measure():
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(2),
        confirmed_measure_orders=[1],
        gas_tests=[{"sampled_at": _now()}],
        requires_gas_test=True,
    )
    assert any("措施" in e for e in errs)


def test_validate_requires_gas_test_for_hot_work():
    """动火/受限空间类没有气体检测记录一律不能提交。"""
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[],
        requires_gas_test=True,
    )
    assert any("气体检测" in e for e in errs)


def test_validate_rejects_stale_gas_test():
    """取样时间必须覆盖开工前 30 分钟内。"""
    old = _now() - timedelta(hours=3)
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[{"sampled_at": old}],
        requires_gas_test=True,
    )
    assert any("30 分钟" in e for e in errs)


def test_validate_passes_when_everything_ok():
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[{"sampled_at": _now()}],
        requires_gas_test=True,
    )
    assert errs == []


def test_validate_has_no_skip_switch():
    """校验函数不接受任何"跳过"参数——法定必填项不得被开关绕过。"""
    import inspect

    params = set(inspect.signature(validate_before_submit).parameters)
    for banned in ("skip", "force", "bypass", "ignore_required", "ai_check_mode"):
        assert banned not in params, f"校验函数不应接受 {banned} 参数"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_service.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现（校验与编号部分）**

```python
"""作业票服务：开票、提交、审批推进、延期、作废、归档。

一条不可协商的规则：**法定必填项与证件有效期的校验不受任何开关影响**。
`validate_before_submit()` 据此设计——它不接受 skip/force/bypass 之类的参数，
调用方没有"跳过校验"的可能。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_ticket import (
    WorkTicketAuditLog,
    WorkTicketGasTest,
    WorkTicketInstance,
    WorkTicketNodeRecord,
)
from app.services.work_ticket_flow import (
    FlowError,
    can_transition,
    next_node,
    sign_requirement_met,
)

logger = logging.getLogger("work_ticket_service")

GAS_TEST_MAX_AGE = timedelta(minutes=30)


class SubmitValidationError(ValueError):
    """提交前校验未通过。"""


class WorkTicketError(ValueError):
    """作业票状态或数据错误。"""


_CODE_SEQ = re.compile(r"-(\d{4})$")


def build_ticket_code(ticket_type: str, enterprise_code: str, day: datetime, seq: int) -> str:
    """编号规则：{类型}-{企业码}-{YYYYMMDD}-{4位序号}。"""
    return f"{ticket_type}-{enterprise_code}-{day.strftime('%Y%m%d')}-{seq:04d}"


def next_code_seq(existing_codes: Sequence[str]) -> int:
    """取当天已有序号的最大值 +1。

    用"最大值 +1"而不是"数量 +1"——删掉中间某张票后，用数量会撞上已存在的编号。
    """
    max_seq = 0
    for code in existing_codes:
        m = _CODE_SEQ.search(code or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def validate_before_submit(
    *,
    template,
    values: dict,
    measures: Sequence,
    confirmed_measure_orders: Sequence[int],
    gas_tests: Sequence[dict],
    requires_gas_test: bool,
    now: Optional[datetime] = None,
) -> list[str]:
    """提交前合规校验。返回问题清单；空列表表示可以提交。

    刻意不接受 skip/force/bypass 参数：法定必填项一律阻断，平台不提供绕过入口。
    """
    now = now or datetime.now(timezone.utc)
    errors: list[str] = []

    for field in getattr(template, "fields", []) or []:
        if not getattr(field, "is_required", False):
            continue
        key = field.field_key
        raw = values.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            errors.append(f"必填项「{getattr(field, 'label', key)}」尚未填写")

    mandatory = [m for m in measures if getattr(m, "is_mandatory", True)]
    confirmed = set(confirmed_measure_orders or [])
    missing = [m for m in mandatory if getattr(m, "sort_order", 0) not in confirmed]
    if missing:
        errors.append(
            f"还有 {len(missing)} 条安全措施未确认（如「{missing[0].measure_text[:20]}…」）"
        )

    if requires_gas_test:
        if not gas_tests:
            errors.append("动火/受限空间作业必须至少录入一次气体检测记录")
        else:
            latest = max(
                (g.get("sampled_at") for g in gas_tests if g.get("sampled_at")),
                default=None,
            )
            if latest is None:
                errors.append("气体检测记录缺少取样时间")
            else:
                if latest.tzinfo is None:
                    latest = latest.replace(tzinfo=timezone.utc)
                if now - latest > GAS_TEST_MAX_AGE:
                    errors.append(
                        "气体检测取样时间已超过 30 分钟，请重新检测后再提交"
                    )
    return errors
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_service.py -v
```

预期：`12 passed`

- [ ] **步骤 5：追加编排函数（同文件）**

```python
async def open_ticket(
    db: AsyncSession,
    *,
    enterprise_id: str,
    enterprise_code: str,
    ticket_type: str,
    template_id: str,
    level: Optional[str] = None,
    values: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> WorkTicketInstance:
    """开票（草稿态）。编号冲突时重试，最终由数据库唯一约束兜底。"""
    day = datetime.now(timezone.utc)
    prefix = f"{ticket_type}-{enterprise_code}-{day.strftime('%Y%m%d')}-"
    res = await db.execute(
        select(WorkTicketInstance.code).where(
            WorkTicketInstance.enterprise_id == enterprise_id,
            WorkTicketInstance.code.like(f"{prefix}%"),
        )
    )
    seq = next_code_seq([row[0] for row in res.all()])

    instance = WorkTicketInstance(
        enterprise_id=enterprise_id,
        template_id=template_id,
        code=build_ticket_code(ticket_type, enterprise_code, day, seq),
        ticket_type=ticket_type,
        level=level,
        status="draft",
        values=values or {},
        submitted_by=user_id,
    )
    db.add(instance)
    await db.flush()
    db.add(
        WorkTicketAuditLog(
            instance_id=instance.id,
            action="open",
            to_status="draft",
            detail={"code": instance.code},
            acted_by=user_id,
        )
    )
    await db.commit()
    return instance


async def submit_ticket(
    db: AsyncSession,
    *,
    instance_id: str,
    user_id: Optional[str] = None,
) -> dict:
    """提交审批。先过合规校验，再过状态机；任一不过即拒绝。"""
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == instance_id))
    instance = res.scalar_one_or_none()
    if instance is None:
        raise WorkTicketError("作业票不存在")
    if not can_transition(instance.status, "submit"):
        raise WorkTicketError(f"当前状态（{instance.status}）不允许提交")

    tpl_res = await db.execute(
        select(WorkTicketTemplate).where(WorkTicketTemplate.id == instance.template_id)
    )
    template = tpl_res.scalar_one_or_none()
    values = instance.values or {}
    gas_res = await db.execute(
        select(WorkTicketGasTest).where(WorkTicketGasTest.instance_id == instance_id)
    )
    gas_tests = [
        {"sampled_at": g.sampled_at, "conclusion": g.conclusion}
        for g in gas_res.scalars().all()
    ]
    measures = list(getattr(template, "measures", []) or [])
    errors = validate_before_submit(
        template=template,
        values=values,
        measures=measures,
        confirmed_measure_orders=values.get("confirmed_measures", []),
        gas_tests=gas_tests,
        requires_gas_test=instance.ticket_type in ("DHZY", "YXKJ"),
    )
    if errors:
        raise SubmitValidationError("；".join(errors))

    from_status = instance.status
    instance.status = "approving"
    node = await _advance_to_first_active_node(db, instance)
    db.add(
        WorkTicketAuditLog(
            instance_id=instance.id,
            action="submit",
            from_status=from_status,
            to_status="approving",
            detail={"first_node": getattr(node, "node_key", None)},
            acted_by=user_id,
        )
    )
    await db.commit()
    return {"instance_id": instance.id, "status": instance.status, "node": getattr(node, "node_key", None)}


async def _advance_to_first_active_node(db: AsyncSession, instance: WorkTicketInstance):
    """从 current_order 之后找第一个条件命中的节点并写回实例。"""
    if not instance.flow_template_id:
        raise WorkTicketError("作业票未绑定审批流程")
    res = await db.execute(
        select(WorkTicketFlowNode).where(
            WorkTicketFlowNode.flow_template_id == instance.flow_template_id
        )
    )
    nodes = list(res.scalars().all())
    ctx = {"level": instance.level, **(instance.values or {})}
    node = next_node(nodes, current_order=instance.current_order, ctx=ctx)
    if node is None:
        instance.status = "approved"
        instance.current_node_key = None
    else:
        instance.current_node_key = node.node_key
        instance.current_order = node.sort_order
    return node


async def act_on_node(
    db: AsyncSession,
    *,
    instance_id: str,
    action: str,
    user_id: str,
    opinion: Optional[str] = None,
) -> dict:
    """在审批节点上动作：approve / reject。会签未满足时不允许流转。"""
    res = await db.execute(select(WorkTicketInstance).where(WorkTicketInstance.id == instance_id))
    instance = res.scalar_one_or_none()
    if instance is None:
        raise WorkTicketError("作业票不存在")
    if instance.status != "approving":
        raise WorkTicketError(f"当前状态（{instance.status}）不在审批中")
    if action not in ("approve", "reject"):
        raise WorkTicketError(f"未知动作：{action}")

    db.add(
        WorkTicketNodeRecord(
            instance_id=instance_id,
            node_key=instance.current_node_key or "",
            action=action,
            opinion=opinion,
            acted_by=user_id,
        )
    )

    if action == "reject":
        from_status = instance.status
        instance.status = "rejected"
        instance.current_node_key = None
        instance.current_order = 0
        db.add(
            WorkTicketAuditLog(
                instance_id=instance.id,
                action="reject",
                from_status=from_status,
                to_status="rejected",
                detail={"opinion": opinion},
                acted_by=user_id,
            )
        )
        await db.commit()
        return {"instance_id": instance.id, "status": instance.status}

    node_res = await db.execute(
        select(WorkTicketFlowNode).where(
            WorkTicketFlowNode.flow_template_id == instance.flow_template_id,
            WorkTicketFlowNode.node_key == instance.current_node_key,
        )
    )
    node = node_res.scalar_one_or_none()
    if node is None:
        raise WorkTicketError("当前节点配置缺失")

    rec_res = await db.execute(
        select(WorkTicketNodeRecord.acted_by).where(
            WorkTicketNodeRecord.instance_id == instance_id,
            WorkTicketNodeRecord.node_key == node.node_key,
            WorkTicketNodeRecord.action == "approve",
        )
    )
    signed = [row[0] for row in rec_res.all()]
    eligible = await _eligible_users(db, node)
    if not sign_requirement_met(node, signed_users=signed, eligible_users=eligible):
        await db.commit()
        return {
            "instance_id": instance.id,
            "status": instance.status,
            "pending_signs": len([u for u in eligible if u not in signed]),
        }

    from_status = instance.status
    nxt = await _advance_to_first_active_node(db, instance)
    db.add(
        WorkTicketAuditLog(
            instance_id=instance.id,
            action="approve",
            from_status=from_status,
            to_status=instance.status,
            detail={"node": node.node_key, "next": getattr(nxt, "node_key", None)},
            acted_by=user_id,
        )
    )
    await db.commit()
    return {
        "instance_id": instance.id,
        "status": instance.status,
        "node": getattr(nxt, "node_key", None),
    }


async def _eligible_users(db: AsyncSession, node) -> list[str]:
    """取该节点绑定的角色成员。没有 role_code 时返回空列表（会签将判为未完成）。"""
    role_code = getattr(node, "role_code", None)
    if not role_code:
        return []
    res = await db.execute(select(User.id).join(Role, User.role_id == Role.id).where(Role.code == role_code))
    return [row[0] for row in res.all()]


async def expire_overdue_tickets(db: AsyncSession, *, now: Optional[datetime] = None) -> int:
    """把批准后超过有效期仍未开工的票置为 expired。由调度器周期调用。"""
    now = now or datetime.now(timezone.utc)
    res = await db.execute(
        select(WorkTicketInstance).where(
            WorkTicketInstance.status == "approved",
            WorkTicketInstance.valid_to.is_not(None),
            WorkTicketInstance.valid_to < now,
        )
    )
    rows = list(res.scalars().all())
    for instance in rows:
        from_status = instance.status
        instance.status = "expired"
        db.add(
            WorkTicketAuditLog(
                instance_id=instance.id,
                action="expire",
                from_status=from_status,
                to_status="expired",
                detail={"valid_to": instance.valid_to.isoformat() if instance.valid_to else None},
            )
        )
    if rows:
        await db.commit()
    return len(rows)
```

> 顶部 import 需补：`from app.models.work_ticket import WorkTicketFlowNode, WorkTicketTemplate`、
> `from app.models.user import User`、`from app.models.role import Role`。

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_service.py -v
```

预期：`12 passed`

- [ ] **步骤 7：Commit**

```bash
git add backend/app/services/work_ticket_service.py backend/tests/test_work_ticket_service.py
git commit -m "feat(work-ticket): 服务编排（编号/提交校验/审批推进/会签/过期扫描）（任务 6/8）"
```

---

## 任务 7：法定票面打印与归档

**文件：**

- 创建：`backend/app/services/work_ticket_docx.py`
- 修改：`backend/app/routers/work_ticket.py`（导出端点，任务 8 里一起加）
- 测试：`backend/tests/test_work_ticket_docx.py`

**核心约束：打印即固化。** 每次打印生成一份不可变快照（含内容 hash），之后修改票据内容只能产生新的打印版本——**这是审计追溯的底线**。没有这条，"票面被事后改过"就无法证明。

**票面按 GB 30871 附录A 的样式渲染**：复用 `app/services/docx_template.py` 的公文能力（表格、签字页、页眉页脚），不重写版式。

- [ ] **步骤 1：编写失败的测试**

```python
"""法定票面渲染与打印快照。"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.work_ticket_docx import (
    build_snapshot,
    content_hash,
    render_ticket_docx,
)


def _instance():
    i = MagicMock()
    i.id = "wt1"
    i.code = "DHZY-TYKJ-20260917-0001"
    i.ticket_type = "DHZY"
    i.level = "一级"
    i.status = "approved"
    i.values = {"work_content": "焊接", "fire_location": "罐区A 北侧管廊"}
    i.valid_from = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
    i.valid_to = datetime(2026, 9, 17, 17, 0, tzinfo=timezone.utc)
    return i


def _template():
    t = MagicMock()
    t.name = "动火安全作业票"
    f1 = MagicMock()
    f1.field_key = "work_content"
    f1.label = "作业内容"
    f1.sort_order = 1
    f2 = MagicMock()
    f2.field_key = "fire_location"
    f2.label = "动火地点及动火部位"
    f2.sort_order = 2
    t.fields = [f1, f2]
    m1 = MagicMock()
    m1.measure_text = "动火设备内部构件清洗干净"
    m1.article_anchor = "GB 30871-2022 5"
    m1.sort_order = 1
    t.measures = [m1]
    return t


def test_build_snapshot_contains_faces_and_measures():
    snap = build_snapshot(
        instance=_instance(),
        template=_template(),
        node_records=[{"node_key": "approve", "action": "approve", "acted_by": "u1", "opinion": "同意"}],
        gas_tests=[{"sampled_at": "2026-09-17T08:40:00+00:00", "result": "合格"}],
    )
    assert snap["code"] == "DHZY-TYKJ-20260917-0001"
    assert snap["fields"][0]["label"] == "作业内容"
    assert snap["measures"][0]["article_anchor"] == "GB 30871-2022 5"
    assert snap["node_records"][0]["opinion"] == "同意"
    assert snap["copies"] == ["第一联 监护人/作业单位", "第二联 所在基层单位", "第三联 存档"]


def test_content_hash_is_stable_and_changes_on_content():
    snap1 = {"a": 1, "b": [1, 2]}
    snap2 = {"b": [1, 2], "a": 1}  # 键序不同
    assert content_hash(snap1) == content_hash(snap2), "键序变化不应改变 hash"
    assert content_hash(snap1) != content_hash({"a": 1, "b": [1, 3]})


def test_snapshot_excludes_nothing_sensitive_field_keys():
    """票面可能含人名电话，快照要留痕但不额外存无关字段。"""
    snap = build_snapshot(
        instance=_instance(), template=_template(), node_records=[], gas_tests=[]
    )
    assert set(snap) == {
        "code", "ticket_type", "level", "status", "valid_from", "valid_to",
        "fields", "measures", "node_records", "gas_tests", "copies",
    }


def test_render_ticket_docx_calls_docx_template():
    with patch("app.services.work_ticket_docx.build_table") as bt, patch(
        "app.services.work_ticket_docx.Document"
    ) as doc:
        doc.return_value = MagicMock()
        render_ticket_docx(snapshot=build_snapshot(
            instance=_instance(), template=_template(), node_records=[], gas_tests=[]
        ))
        assert bt.call_count >= 2, "票面字段表与措施表都要渲染成表格"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_docx.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
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
```

> `render_ticket_docx` 的 import 以 `docx_template.py` 实际导出名为准。
> 若 `set_page_margins` 签名是位置参数而非关键字，按其实际签名调整。

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_docx.py -v
```

预期：`4 passed`

- [ ] **步骤 5：真实文档目视验收**

造一张已批准的动火票（含 2 条措施、2 条气体检测、1 条审批记录），渲染 DOCX 后用 Word 打开检查：

1. 标题、编号、级别正确
2. 票面字段表两列对齐、无错位
3. 措施表四列（序号/措施/依据条款/是否确认）完整
4. 气体检测表与审批记录表都在
5. 末尾三联标注与"至少保存一年"提示可见

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/work_ticket_docx.py backend/tests/test_work_ticket_docx.py
git commit -m "feat(work-ticket): 法定票面 DOCX 渲染与打印快照（含内容 hash 与三联标注）（任务 7/8）"
```
