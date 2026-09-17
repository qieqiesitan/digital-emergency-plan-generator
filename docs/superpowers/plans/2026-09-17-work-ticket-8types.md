# 作业票其余 6 类（附录A/B 数据化扩展 + 会签场景）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把作业票从 2 类扩到 8 类——盲板抽堵、高处、吊装、临时用电、动土、断路。**靠模板驱动复制，不写 6 套代码。**

**架构：** 计划 8 已经把骨架建好（模板层 + 审批引擎 + 实例 + 打印）。本计划的活是**数据扩展 + 两处真正的新增能力**：

1. 附录A 表A.3~A.8 的票面字段与措施数据化（第 7~12 章）
2. 附录B 表B.1 的其余审批行（含**多单位会签**——临时用电的配送电单位、动土的七个涉及单位）

**技术栈：** 全部复用计划 8 的栈，不引入新依赖。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §7.1、§13.1

**依赖：** **计划 8 必须已完成并验证**——骨架没跑通就铺 6 类，等于 6 次返工。这是规格里明确写死的前置。

---

## 文件结构

| 文件 | 改动 |
|---|---|
| `backend/app/services/work_ticket_seed_data.py`（修改） | 追加 6 类模板的字段定义与审批矩阵行 |
| `backend/seed_work_ticket_templates.py`（修改） | 支持多节点流程与会签策略 |
| `backend/db_migration_20260917_work_ticket_seed_v2.sql`（新建） | 增量种子（不覆盖 v1） |
| `backend/app/services/work_ticket_service.py`（修改） | `requires_gas_test` 的类型集合抽成常量；会签资格人支持"按单位" |
| `backend/tests/test_work_ticket_seed_v2.py`（新建） | 8 类完整性 |
| `backend/tests/test_work_ticket_countersign.py`（新建） | 多单位会签 |
| `frontend/src/pages/Enterprise/WorkTicketListPage.tsx`（修改） | 8 类筛选全部解禁 |
| `frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`（修改） | 分级票的级别选项按类型变化 |

**既有约定（来自计划 8，不重复说明）**

- 种子生成器：`_uid(kind, key)` = `uuid5(NAMESPACE_URL, "work-ticket/GB30871-2022/<kind>/<key>")`，配 `ON CONFLICT (id) DO NOTHING`
- 审批引擎：`TRANSITIONS` + `can_transition` + `sign_requirement_met` + `next_node`
- 法定环节：`is_statutory=True` 的节点不可删

**不要改已发布的 v1 种子文件。** 增量用 v2，理由是：已按 v1 部署过的环境再跑 v1 不会补数据（`ON CONFLICT DO NOTHING` 会跳过），必须用新文件触发增量执行。

---

## 8 类作业票与标准的对应（先对齐，再写代码）

| 类型码 | 名称 | 分级 | 标准章节 | 措施来源 | 气体检测 | 法定审批 |
|---|---|---|---|---|---|---|
| DHZY | 动火安全作业票 | 特级/一级/二级 | 第5章 | 附录A 表A.1 | ✅ 必填 | 按级别 |
| YXKJ | 受限空间安全作业票 | 不分级 | 第6章 | 表A.2 | ✅ 必填 | 所在基层单位 |
| MBCD | 盲板抽堵安全作业票 | 不分级 | 第7章 | 表A.3 | ❌ | 所在基层单位 |
| GCZY | 高处安全作业票 | Ⅰ/Ⅱ/Ⅲ/Ⅳ级 | 第8章 | 表A.4 | ❌ | 按级别（4 档） |
| QZDZ | 吊装安全作业票 | 一级/二级/三级 | 第9章 | 表A.5 | ❌ | 按级别（3 档） |
| LSYD | 临时用电安全作业票 | 不分级 | 第10章 | 表A.6 | ❌ | **配送电单位**（会签+审批） |
| PTZY | 动土安全作业票 | 不分级 | 第11章 | 表A.7 | ❌ | **多单位会签** + 所在单位专业部门 |
| DLZY | 断路安全作业票 | 不分级 | 第12章 | 表A.8 | ❌ | **涉及单位会签** + 所在单位专业部门 |

**法定审批矩阵（表B.1 其余行）**

| 类型 | 级别 | 审核或会签 | 审批部门（人） |
|---|---|---|---|
| 高处 | Ⅰ级 | — | 所在基层单位 |
| 高处 | Ⅱ级、Ⅲ级 | — | 所在单位专业部门 |
| 高处 | Ⅳ级 | — | 主管厂长或总工程师 |
| 吊装 | 一级 | — | 主管厂长或总工程师 |
| 吊装 | 二级、三级 | — | 所在单位专业部门 |
| 临时用电 | — | 配送电单位 | 配送电单位 |
| 动土 | — | 水、电、汽、工艺、设备、消防、安全管理等动土涉及单位 | 所在单位专业部门 |
| 断路 | — | 断路涉及单位消防、安全管理部门 | 所在单位专业部门 |

> 表B.1 附注有两条与本计划相关的说明：
> ①「安全作业票的审核或会签人员根据危险化学品企业具体管理机构设置情况参照执行」——
> 对应我们"节点可改角色绑定"的设计；
> ②「吊装质量小于 10t 的作业可不办理吊装票，但应进行风险分析」——
> 在吊装类型下加一个提示，不要硬性阻止。

---

## 任务 1：附录A 其余 6 类票面字段数据化

**文件：**

- 修改：`backend/app/services/work_ticket_seed_data.py`
- 测试：`backend/tests/test_work_ticket_seed_v2.py`

**字段来源：** GB 30871-2022 附录A 表A.3~A.8。沿用计划 8 的做法——**人工抄录 + 标注出处**，不写解析器（每类票约 10~15 个字段，抄比解析可靠）。

- [ ] **步骤 1：编写失败的测试**

```python
"""8 类作业票种子完整性。"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "wt_seed", ROOT / "backend" / "app" / "services" / "work_ticket_seed_data.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_all_eight_types_present():
    mod = _load()
    codes = {t["code"] for t in mod.TEMPLATES}
    assert codes == {"DHZY", "YXKJ", "MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY"}


def test_graded_types_have_expected_levels():
    mod = _load()
    by_code: dict[str, set] = {}
    for t in mod.TEMPLATES:
        by_code.setdefault(t["code"], set()).add(t["level"])
    assert by_code["DHZY"] == {"特级", "一级", "二级"}
    assert by_code["GCZY"] == {"Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"}
    assert by_code["QZDZ"] == {"一级", "二级", "三级"}
    for code in ("YXKJ", "MBCD", "LSYD", "PTZY", "DLZY"):
        assert by_code[code] == {None}, f"{code} 不应分级"


def test_every_template_has_fields_and_chapter():
    mod = _load()
    for t in mod.TEMPLATES:
        assert t["fields"], f"{t['name']} 缺票面字段"
        assert isinstance(t["chapter"], int) and 5 <= t["chapter"] <= 12, t["name"]
        keys = [f["field_key"] for f in t["fields"]]
        assert len(keys) == len(set(keys)), f"{t['name']} 字段 key 重复"


def test_approval_matrix_covers_all_standard_rows():
    """表B.1 的每一行都要有对应配置。"""
    mod = _load()
    m = {(r["code"], r["level"]) for r in mod.APPROVAL_MATRIX}
    expected = {
        ("DHZY", "特级"), ("DHZY", "一级"), ("DHZY", "二级"),
        ("YXKJ", None), ("MBCD", None),
        ("GCZY", "Ⅰ级"), ("GCZY", "Ⅱ级"), ("GCZY", "Ⅲ级"), ("GCZY", "Ⅳ级"),
        ("QZDZ", "一级"), ("QZDZ", "二级"), ("QZDZ", "三级"),
        ("LSYD", None), ("PTZY", None), ("DLZY", None),
    }
    assert expected <= m, f"缺少审批行：{expected - m}"


def test_countersign_rows_present():
    """临时用电与动土/断路的会签单位不能漏。"""
    mod = _load()
    countersign = {r["code"]: r for r in mod.APPROVAL_MATRIX if r.get("countersign")}
    assert "配送电单位" in countersign["LSYD"]["countersign"]
    assert len(countersign["PTZY"]["countersign"]) >= 5, "动土应涉及多单位会签"
    assert countersign["DLZY"]["countersign"], "断路应有涉及单位会签"


def test_gas_test_required_only_for_two_types():
    """只有动火与受限空间强制气体检测。"""
    mod = _load()
    required = {t["code"] for t in mod.TEMPLATES if t.get("requires_gas_test")}
    assert required == {"DHZY", "YXKJ"}
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_seed_v2.py -q
```

预期：FAIL（只有 2 类、审批矩阵不足）

- [ ] **步骤 3：扩展常量表**

在 `work_ticket_seed_data.py` 里：

1. 给**已有**的 DHZY 三条与 YXKJ 一条补 `"requires_gas_test": True`
2. 追加 6 类模板定义（每类的 `fields` 按附录A 表A.3~A.8 抄录；`group_name` 沿用"基本信息 / 作业内容 / 危害因素 / 气体检测 / 人员 / 签字"六组）
3. 把 `APPROVAL_MATRIX` 补全为 15 行，并给 LSYD / PTZY / DLZY 加 `countersign` 字段

```python
# 其余 6 类的字段定义（依据 GB 30871-2022 附录A 表A.3~A.8）
# 每类的通用首尾字段（申请单位/时间/作业内容/作业单位/负责人/实施时间/风险辨识/关联票）
# 与专用字段（如盲板抽堵的"盲板编号/规格"、高处的"作业高度/作业方式"）区分开
_COMMON_HEAD_FIELDS = [
    {"field_key": "applicant_unit", "label": "作业申请单位", "field_type": "text",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "apply_time", "label": "作业申请时间", "field_type": "datetime",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "work_content", "label": "作业内容", "field_type": "textarea",
     "group_name": "作业内容", "is_required": True, "allow_ai_prefill": True},
    {"field_key": "work_unit", "label": "作业单位", "field_type": "text",
     "group_name": "基本信息", "is_required": True},
    {"field_key": "work_leader", "label": "作业负责人", "field_type": "text",
     "group_name": "人员", "is_required": True},
    {"field_key": "work_period", "label": "作业实施时间", "field_type": "datetimerange",
     "group_name": "基本信息", "is_required": True},
]

# 各类型的专用字段（table_no 对应附录A 的表号，供人工核对出处）
_TYPE_SPECIFIC_FIELDS: dict[str, list[dict]] = {
    "MBCD": [
        {"field_key": "blind_plate_no", "label": "盲板编号", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "pipe_position", "label": "管线/设备位置", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "operate_type", "label": "作业类别", "field_type": "select",
         "group_name": "作业内容", "is_required": True,
         "options": {"choices": ["抽盲板", "堵盲板"]}},
    ],
    "GCZY": [
        {"field_key": "work_height", "label": "作业高度(m)", "field_type": "number",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "high_level", "label": "高处作业级别", "field_type": "select",
         "group_name": "作业内容", "is_required": True,
         "options": {"choices": ["Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"]}},
        {"field_key": "work_method", "label": "作业方式", "field_type": "text",
         "group_name": "作业内容", "is_required": False},
    ],
    "QZDZ": [
        {"field_key": "lift_weight", "label": "吊装质量(t)", "field_type": "number",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "lift_level", "label": "吊装作业级别", "field_type": "select",
         "group_name": "作业内容", "is_required": True,
         "options": {"choices": ["一级", "二级", "三级"]}},
        {"field_key": "lift_commander", "label": "吊装指挥", "field_type": "text",
         "group_name": "人员", "is_required": True},
        {"field_key": "lift_machine", "label": "起重机械及编号", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
    ],
    "LSYD": [
        {"field_key": "power_source", "label": "电源接入点", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "power_capacity", "label": "用电容量(kW)", "field_type": "number",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "electrician", "label": "电工及证书编号", "field_type": "text",
         "group_name": "人员", "is_required": True},
        {"field_key": "logout_person", "label": "作业结束后注销人", "field_type": "text",
         "group_name": "人员", "is_required": False},
    ],
    "PTZY": [
        {"field_key": "dig_location", "label": "动土地点及部位", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "dig_depth", "label": "动土深度(m)", "field_type": "number",
         "group_name": "作业内容", "is_required": False},
        {"field_key": "dig_method", "label": "动土方式", "field_type": "text",
         "group_name": "作业内容", "is_required": False},
    ],
    "DLZY": [
        {"field_key": "road_position", "label": "断路地点及部位", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "road_scope", "label": "断路范围及时间", "field_type": "text",
         "group_name": "作业内容", "is_required": True},
        {"field_key": "traffic_plan", "label": "交通组织方案", "field_type": "textarea",
         "group_name": "危害因素", "is_required": False, "allow_ai_prefill": True},
    ],
}

_SIMPLE_TYPES = [
    ("MBCD", "盲板抽堵安全作业票", 7),
    ("LSYD", "临时用电安全作业票", 10),
    ("PTZY", "动土安全作业票", 11),
    ("DLZY", "断路安全作业票", 12),
]
_GRADED_TYPES = [
    ("GCZY", "高处安全作业票", 8, ["Ⅰ级", "Ⅱ级", "Ⅲ级", "Ⅳ级"]),
    ("QZDZ", "吊装安全作业票", 9, ["一级", "二级", "三级"]),
]

for _code, _name, _chapter in _SIMPLE_TYPES:
    TEMPLATES.append({
        "code": _code, "name": _name, "level": None, "is_graded": False,
        "chapter": _chapter, "requires_gas_test": False,
        "fields": [*_COMMON_HEAD_FIELDS, *_TYPE_SPECIFIC_FIELDS[_code], *_COMMON_TAIL_FIELDS],
    })

for _code, _name, _chapter, _levels in _GRADED_TYPES:
    for _level in _levels:
        TEMPLATES.append({
            "code": _code, "name": f"{_name}（{_level}）", "level": _level, "is_graded": True,
            "chapter": _chapter, "requires_gas_test": False,
            "fields": [*_COMMON_HEAD_FIELDS, *_TYPE_SPECIFIC_FIELDS[_code], *_COMMON_TAIL_FIELDS],
        })

for _tpl in TEMPLATES:
    if _tpl["code"] in ("DHZY", "YXKJ"):
        _tpl.setdefault("requires_gas_test", True)

APPROVAL_MATRIX.extend([
    {"code": "MBCD", "level": None, "approver": "所在基层单位"},
    {"code": "GCZY", "level": "Ⅰ级", "approver": "所在基层单位"},
    {"code": "GCZY", "level": "Ⅱ级", "approver": "所在单位专业部门"},
    {"code": "GCZY", "level": "Ⅲ级", "approver": "所在单位专业部门"},
    {"code": "GCZY", "level": "Ⅳ级", "approver": "主管厂长或总工程师"},
    {"code": "QZDZ", "level": "一级", "approver": "主管厂长或总工程师"},
    {"code": "QZDZ", "level": "二级", "approver": "所在单位专业部门"},
    {"code": "QZDZ", "level": "三级", "approver": "所在单位专业部门"},
    {"code": "LSYD", "level": None, "approver": "配送电单位",
     "countersign": ["配送电单位"]},
    {"code": "PTZY", "level": None, "approver": "所在单位专业部门",
     "countersign": ["水", "电", "汽", "工艺", "设备", "消防", "安全管理"]},
    {"code": "DLZY", "level": None, "approver": "所在单位专业部门",
     "countersign": ["消防", "安全管理"]},
])
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_seed_v2.py -v
```

预期：`6 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/work_ticket_seed_data.py backend/tests/test_work_ticket_seed_v2.py
git commit -m "feat(work-ticket): 附录A/B 扩展至 8 类（票面字段+审批矩阵+会签单位）（任务 1/6）"
```

---

## 任务 2：措施库解析扩展与 v2 种子生成

**文件：**

- 修改：`backend/seed_work_ticket_templates.py`
- 创建：`backend/db_migration_20260917_work_ticket_seed_v2.sql`

- [ ] **步骤 1：扩展生成器的章节覆盖**

现有生成器按 `tpl["chapter"]` 调 `parse_measures`，扩展 6 类后会自动覆盖第 7~12 章。**但要加一道校验**：每类模板解析出的措施数不能为 0——为零说明标准文本里那段表格没被识别，需要人工介入而不是静默生成空措施库。

在 `build_sql()` 的措施循环处加：

```python
        parsed = seed.parse_measures(text, chapter=tpl["chapter"])
        if not parsed:
            raise RuntimeError(
                f"「{tpl['name']}」未能从第 {tpl['chapter']} 章解析出任何安全措施，"
                "请检查标准文本的表格结构是否被清洗脚本破坏"
            )
        for m in parsed:
            ...
```

- [ ] **步骤 2：把输出改到 v2 文件**

生成器顶部常量改指向增量文件：

```python
OUT = ROOT / "backend" / "db_migration_20260917_work_ticket_seed_v2.sql"
```

并把 SQL 头部注释改成说明这是**增量**：

```python
    lines = [
        "-- 20260917 作业票模板种子【增量 v2】：补齐至 8 类（GB 30871-2022 附录A/B）",
        "-- 增量说明：已按 v1 部署过的环境用本文件补齐；v2 内容包含 v1，",
        "-- 全部使用 ON CONFLICT (id) DO NOTHING，重复执行安全。",
        ...
    ]
```

- [ ] **步骤 3：生成并校验**

运行：

```bash
python backend/seed_work_ticket_templates.py
python backend/seed_work_ticket_templates.py && sha256sum backend/db_migration_20260917_work_ticket_seed_v2.sql
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_work_ticket_seed_v2.sql
docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_work_ticket_seed_v2.sql
```

预期：sha256 两次一致；SQL 连跑两次无报错

- [ ] **步骤 4：核对库里的最终状态**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT code, count(*) FROM work_ticket_templates GROUP BY code ORDER BY code;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) AS nodes, count(*) FILTER (WHERE is_statutory) AS statutory FROM work_ticket_flow_nodes;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) FROM work_ticket_template_measures;"
```

预期：8 个类型码齐全、模板总数 15（动火 3 + 高处 4 + 吊装 3 + 其余 5）；**法定节点数 = 审批矩阵行数（15）**；措施总数 > 100

- [ ] **步骤 5：Commit**

```bash
git add backend/seed_work_ticket_templates.py backend/db_migration_20260917_work_ticket_seed_v2.sql
git commit -m "feat(work-ticket): v2 增量种子（8 类措施库与审批流程，空措施即报错）（任务 2/6）"
```

---

## 任务 3：多单位会签落地

**文件：**

- 修改：`backend/app/services/work_ticket_service.py`
- 测试：`backend/tests/test_work_ticket_countersign.py`

**这是 6 类扩展里唯一真正的新增能力。** 计划 8 的会签按**角色**取资格人（`_eligible_users` 用 `Role.code`）。但动土票的会签单位是"水、电、汽、工艺、设备、消防、安全管理"——**这不是角色，是部门/单位**。

两种处理方式：

- **A. 把每个单位建成角色**：污染角色体系（角色是权限概念，不该拿来当部门用）
- **B. 节点绑定"会签单位清单"**：`role_code` 之外增加 `countersign_units` 概念，资格人 = 这些单位的成员

选 **B**。理由是角色决定"能做什么"，部门决定"属于谁"——把部门塞进角色会让权限模型变形。

- [ ] **步骤 1：编写失败的测试**

```python
"""多单位会签：按部门/单位取会签资格人。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.work_ticket_flow import FlowError, sign_requirement_met
from app.services.work_ticket_service import eligible_users_for_node


def _node(policy="all", role=None, units=None):
    n = MagicMock()
    n.sign_policy = policy
    n.role_code = role
    n.node_key = "countersign"
    n.name = "会签"
    n.countersign_units = units
    return n


def test_node_can_declare_units_instead_of_role():
    """单位会签节点不需要 role_code。"""
    n = _node(units=["水", "电", "汽"])
    assert n.role_code is None
    assert n.countersign_units == ["水", "电", "汽"]


def test_sign_requirement_all_with_units():
    """七个单位都要签，只签三个不能流转。"""
    n = _node(policy="all", units=["水", "电", "汽", "工艺", "设备", "消防", "安全管理"])
    assert sign_requirement_met(n, signed_users=["u1", "u2", "u3"], eligible_users=["u1","u2","u3","u4","u5","u6","u7"]) is False
    assert sign_requirement_met(
        n, signed_users=["u1","u2","u3","u4","u5","u6","u7"],
        eligible_users=["u1","u2","u3","u4","u5","u6","u7"],
    ) is True


@pytest.mark.asyncio
async def test_eligible_users_by_units_queries_departments():
    """按单位取人：走 sys_depart 名称匹配，不走 Role。"""
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.all.return_value = [("u1",), ("u2",)]
        return res

    db.execute = execute
    node = _node(units=["水", "电"])
    users = await eligible_users_for_node(db, node)
    assert set(users) == {"u1", "u2"}


@pytest.mark.asyncio
async def test_eligible_users_empty_when_node_has_neither_role_nor_units():
    db = MagicMock()
    db.execute = AsyncMock()
    node = _node(role=None, units=None)
    assert await eligible_users_for_node(db, node) == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_countersign.py -q
```

预期：`ImportError: cannot import name 'eligible_users_for_node'`

- [ ] **步骤 3：加字段与实现**

`work_ticket_flow_nodes` 增加一列（`work_ticket.py` 与迁移 SQL 同步加）：

```python
    # 会签单位清单（如动土的"水/电/汽/工艺/设备/消防/安全管理"）。
    # 用于"按部门会签"场景——部门是组织概念，不该塞进 Role（角色是权限概念）。
    countersign_units: Mapped[Optional[list]] = mapped_column(JSONB)
```

```sql
ALTER TABLE work_ticket_flow_nodes
    ADD COLUMN IF NOT EXISTS countersign_units JSONB;
```

在 `work_ticket_service.py` 里把 `_eligible_users` 替换为：

```python
async def eligible_users_for_node(db: AsyncSession, node) -> list[str]:
    """取节点的会签资格人。

    两种来源：
    - `role_code`：按角色取人（适用于"安全管理部门审批"这类）；
    - `countersign_units`：按部门取人（适用于动土这种多单位会签）。

    两者都为空时返回空列表——会签将判定为未完成，**不会被静默跳过**。
    """
    units = getattr(node, "countersign_units", None)
    if units:
        res = await db.execute(
            select(SysDepartUser.user_id)
            .join(SysDepart, SysDepartUser.depart_id == SysDepart.id)
            .where(SysDepart.depart_name.in_(units))
        )
        return [row[0] for row in res.all()]

    role_code = getattr(node, "role_code", None)
    if not role_code:
        return []
    res = await db.execute(
        select(User.id).join(Role, User.role_id == Role.id).where(Role.code == role_code)
    )
    return [row[0] for row in res.all()]
```

> `SysDepart` / `SysDepartUser` 的实际模型名以 `app/models/enterprise_org.py` 为准。
> 若现有组织模型不是这两个名字，按其实际表结构改查询——**关键是"按部门取人"这条路径存在**，
> 具体字段名不是重点。

- [ ] **步骤 4：生成器支持会签节点**

在 `seed_work_ticket_templates.py` 里，对 `APPROVAL_MATRIX` 中带 `countersign` 的行，先生成一个 `sign_policy='all'` 的会签节点（order 1），再生成审批节点（order 2）：

```python
        countersign = next(
            (
                r.get("countersign")
                for r in seed.APPROVAL_MATRIX
                if r["code"] == tpl["code"] and r["level"] == tpl["level"]
            ),
            None,
        )
        order = 1
        if countersign:
            node_id = _uid("node", f"{tpl_key}/countersign")
            units_json = json.dumps(countersign, ensure_ascii=False)
            lines.append(
                "INSERT INTO work_ticket_flow_nodes "
                "(id, flow_template_id, node_key, name, sort_order, sign_policy, "
                "reject_to, is_statutory, countersign_units) VALUES "
                f"({_q(node_id)}, {_q(flow_id)}, 'countersign', '涉及单位会签', {order}, "
                f"'all', 'submitter', TRUE, {_q(units_json)}::jsonb) "
                "ON CONFLICT (id) DO NOTHING;"
            )
            order += 1
        # 审批节点用 order 而不是固定 1
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_countersign.py tests/test_work_ticket_flow.py tests/test_work_ticket_service.py -q
```

预期：全绿

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/work_ticket.py backend/app/services/work_ticket_service.py backend/app/services/work_ticket_flow.py backend/seed_work_ticket_templates.py backend/db_migration_20260917_work_ticket.sql backend/db_migration_20260917_work_ticket_seed_v2.sql backend/tests/test_work_ticket_countersign.py
git commit -m "feat(work-ticket): 多单位会签（按部门取资格人，不污染角色体系）（任务 3/6）"
```

---

## 任务 4：气体检测必填范围抽成常量

**文件：**

- 修改：`backend/app/services/work_ticket_service.py`
- 测试：`backend/tests/test_work_ticket_service.py`（追加）

**为什么单独做这一小步：** 计划 8 把"需要气体检测的类型"硬编码成了 `("DHZY", "YXKJ")`。扩到 8 类时必须验证这个集合**没有被顺手放宽**——气体检测是动火与受限空间的法定硬要求，多一类少一类都是错的。

- [ ] **步骤 1：编写失败的测试（追加）**

```python
def test_gas_test_required_types_is_exactly_two():
    """只有动火与受限空间强制气体检测；扩到 8 类后这个集合不能变。"""
    from app.services.work_ticket_service import GAS_TEST_REQUIRED_TYPES

    assert set(GAS_TEST_REQUIRED_TYPES) == {"DHZY", "YXKJ"}


def test_other_six_types_do_not_require_gas_test():
    from app.services.work_ticket_service import requires_gas_test

    for code in ("MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY"):
        assert requires_gas_test(code) is False, code
    for code in ("DHZY", "YXKJ"):
        assert requires_gas_test(code) is True, code
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_service.py -q
```

预期：`ImportError: cannot import name 'GAS_TEST_REQUIRED_TYPES'`

- [ ] **步骤 3：抽出常量与函数**

在 `work_ticket_service.py` 顶部追加：

```python
# 强制气体检测的作业类型。依据 GB 30871-2022 第 5 章（动火）与第 6 章（受限空间）：
# 这两类作业在作业前及作业过程中必须进行气体分析。其余类型不作强制。
GAS_TEST_REQUIRED_TYPES = ("DHZY", "YXKJ")


def requires_gas_test(ticket_type: str) -> bool:
    """该类型是否强制气体检测。"""
    return ticket_type in GAS_TEST_REQUIRED_TYPES
```

并把 `submit_ticket` 里的硬编码改为调用：

```python
        requires_gas_test=requires_gas_test(instance.ticket_type),
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_service.py -v
```

预期：`14 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/work_ticket_service.py backend/tests/test_work_ticket_service.py
git commit -m "refactor(work-ticket): 气体检测必填类型抽为常量并加回归守护（任务 4/6）"
```

---

## 任务 5：前端解禁 8 类与分级联动

**文件：**

- 修改：`frontend/src/pages/Enterprise/WorkTicketListPage.tsx`
- 修改：`frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`
- 修改：`backend/app/schemas/work_ticket.py`（放开类型白名单）

- [ ] **步骤 1：放开后端类型白名单**

`OpenTicketIn.ticket_type` 的 `pattern="^(DHZY|YXKJ)$"` 改为覆盖 8 类：

```python
    ticket_type: str = Field(pattern="^(DHZY|YXKJ|MBCD|GCZY|QZDZ|LSYD|PTZY|DLZY)$")
```

并同步更新 `test_work_ticket_api.py` 里那条 `test_open_ticket_rejects_unimplemented_type`——它原来用 `GCZY` 断言 422，现在 `GCZY` 已实现，改用真正非法的值（如 `"XXXX"`）来守这条断言。**改断言时必须保留"非法类型被拒"这个语义，不能因为要过测试就把断言删掉。**

- [ ] **步骤 2：列表页解禁 8 类筛选**

`WorkTicketListPage` 的类型筛选从 2 个标签扩到 8 个，**并保留"未启用的类型灰显"能力**：标签的禁用状态由后端 `GET /templates` 返回的实际类型集合驱动，不在前端硬编码。这样将来某类票被企业停用时，界面自动灰显，不用改前端。

```tsx
// 类型标签由模板列表驱动，不硬编码
const { data: templates } = useQuery(["wt-templates"], listTemplates);
const enabledTypes = new Set((templates || []).map((t) => t.code));

{ALL_TICKET_TYPES.map((t) => (
  <Tag.CheckableTag
    key={t.code}
    checked={filter === t.code}
    onChange={() => setFilter(t.code)}
    style={enabledTypes.has(t.code) ? undefined : { opacity: 0.45, pointerEvents: "none" }}
  >
    {t.label}
    {!enabledTypes.has(t.code) && <span style={{ fontSize: 11 }}>（未启用）</span>}
  </Tag.CheckableTag>
))}
```

```ts
// 8 类的展示名（与后端 code 对应）
export const ALL_TICKET_TYPES = [
  { code: "DHZY", label: "动火作业" },
  { code: "YXKJ", label: "受限空间作业" },
  { code: "MBCD", label: "盲板抽堵作业" },
  { code: "GCZY", label: "高处作业" },
  { code: "QZDZ", label: "吊装作业" },
  { code: "LSYD", label: "临时用电作业" },
  { code: "PTZY", label: "动土作业" },
  { code: "DLZY", label: "断路作业" },
];
```

- [ ] **步骤 3：开票向导的级别选项按类型联动**

向导第 1 步的"级别"选项**不能写死**，要按所选类型的模板列表生成：

- 动火 → 特级 / 一级 / 二级
- 高处 → Ⅰ级 / Ⅱ级 / Ⅲ级 / Ⅳ级
- 吊装 → 一级 / 二级 / 三级
- 其余 5 类 → 不显示级别选择

```tsx
const levelsForType = (templates || [])
  .filter((t) => t.code === selectedType && t.level)
  .map((t) => t.level as string);
```

选完级别后，第 6 步预览"将按 XX 审批"——审批人由后端返回的流程节点决定，前端**不自己推断**（审批矩阵是法定数据，推断会失真）。

- [ ] **步骤 4：临时用电与动土的会签提示**

向导第 6 步对带会签的类型显示提示：

- 临时用电：「本票需**配送电单位**会签后审批」
- 动土：「本票需**水、电、汽、工艺、设备、消防、安全管理**等涉及单位会签后审批」
- 断路：「本票需**消防、安全管理部门**会签后审批」

提示文案从后端流程节点的 `countersign_units` 生成，不写死在前端。

- [ ] **步骤 5：验证**

运行：

```bash
cd backend && python -m pytest tests/test_work_ticket_api.py -q
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
```

预期：后端全绿；`tsc` exit 0；vitest 全绿

- [ ] **步骤 6：真实浏览器端到端（8 类各开一张）**

对 8 类各开一张票并提交，确认：

1. 分级票（动火/高处/吊装）的级别选项**只出现该类型的级别**，不串类
2. 提交后落到**正确的审批节点**（用三种动火级别 + 四种高处置级别验证分支）
3. **临时用电与动土出现会签节点**，且会签单位文案与标准一致
4. 动火/受限空间缺气体检测时**仍被阻断**（扩类后这条不能被破坏）
5. 其余 6 类**不强制**气体检测（不出现误拦）

- [ ] **步骤 7：Commit**

```bash
git add backend/app/schemas/work_ticket.py backend/tests/test_work_ticket_api.py frontend/src/pages/Enterprise/WorkTicketListPage.tsx frontend/src/pages/Enterprise/WorkTicketNewPage.tsx frontend/src/types/workTicket.ts
git commit -m "feat(work-ticket): 前端解禁 8 类（类型标签由后端驱动 + 级别联动 + 会签提示）（任务 5/6）"
```

---

## 任务 6：8 类回归与验收

**文件：** 无新增，纯验证。

- [ ] **步骤 1：跑全量后端回归**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：失败数不高于 4 个既有失败；通过数 = 基线 + 本计划新增用例数

- [ ] **步骤 2：核对种子数据与标准的一致性（人工）**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT code, level, count(*) FROM work_ticket_templates GROUP BY code, level ORDER BY code, level;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT n.node_key, n.name, n.sign_policy, n.is_statutory, n.countersign_units FROM work_ticket_flow_nodes n ORDER BY n.name;"
```

逐条对照 GB 30871 附录B 表B.1：

1. 15 条模板齐全（动火 3 + 高处 4 + 吊装 3 + 其余 5）
2. 每条的审批人名与表B.1 一致
3. **会签节点的 `sign_policy` 是 `all`**、`is_statutory` 为 TRUE
4. 临时用电/动土/断路的 `countersign_units` 与标准列举的单位一致

- [ ] **步骤 3：确认措施库覆盖到 8 类**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT t.code, count(m.id) AS measures FROM work_ticket_templates t LEFT JOIN work_ticket_template_measures m ON m.template_id = t.id GROUP BY t.code ORDER BY t.code;"
```

预期：8 个类型码的措施数**均大于 0**（动火/受限空间应明显多于其他，因为第 5、6 章条款更细）

- [ ] **步骤 4：Commit（如有遗留改动）**

```bash
git status --porcelain
# 如有未提交的验证期修补，按涉及文件逐个 add 后提交
```

---

## 验收清单

- [ ] 8 个类型码全部可开票；15 条模板与 GB 30871 附录B 表B.1 逐行对应
- [ ] **分级票的级别选项不串类**：动火只有特/一/二级，高处只有 Ⅰ~Ⅳ，吊装只有一/二/三级
- [ ] **审批分支正确**：动火三级 + 高处四级共 7 条路径各走一遍，落到正确节点
- [ ] **多单位会签生效**：动土票在七个单位未全部签署前不流转；临时用电需配送电单位会签
- [ ] **法定环节保护仍生效**：会签节点与审批节点都标 `is_statutory=TRUE`，删除被拒
- [ ] **气体检测规则未被放宽**：动火/受限空间缺检测仍被阻断；其余 6 类不误拦
- [ ] **措施库覆盖 8 类**：每类措施数 > 0，且每条带 `article_anchor`
- [ ] **类型标签由后端驱动**：停用某类模板后，界面自动灰显该标签（前端不硬编码）
- [ ] 种子 SQL 连跑两次无报错、sha256 一致
- [ ] 全量后端回归失败数不高于 4 个既有失败

## 未纳入本计划

- **JSA 与提交前 AI 合规校验接入 6 类新票**：属计划 2 的 AI 能力接线，机制对 8 类通用，接线时机由业务决定
- **吊装质量 < 10t 可免票的提示**：表B.1 附注提到，但在票面加提示需要先有企业实际使用反馈，先不做
- **作业过程影像留存**：需移动端配合，与计划 8 一致地后置
- **票面打印模板的逐类微调**：计划 8 的通用渲染已能出票；若某类票的法定版式差异大（如断路票的交通组织图），按实际验收反馈再调
