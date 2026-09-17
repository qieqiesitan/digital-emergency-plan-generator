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
