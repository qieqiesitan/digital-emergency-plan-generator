# 事故类型全链路对齐 GB 6441-2025 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将系统中所有「事故类型/风险类别」使用点统一到 GB 6441-2025 的 27 类，完成 4 张表存量数据迁移，并修复风险源模板/AI 生成端点的 NameError。

**架构：** 前后端各收敛一个共享常量模块（`accident_types.py` / `accidentTypes.ts`）；告知卡标志组与处置模板按 27 类重建；AI 提示词、Excel 模板、法规库同步更新；存量数据按新旧映射表幂等迁移，自由值保留。

**技术栈：** Python 3.11 / FastAPI / SQLAlchemy async / PostgreSQL 16 / openpyxl；TypeScript / React 18 / antd / Vitest

---

## 文件结构

**新增：**
- `backend/app/services/accident_types.py` — 27 类清单 + 新旧映射 + normalize/split
- `backend/tests/test_accident_types.py` — 共享模块单测
- `backend/db_migration_accident_types_2025.sql` — 4 张表幂等迁移
- `backend/app/regulations/data/texts/gb6441_2025.md` — 新国标全文
- `frontend/src/utils/accidentTypes.ts` — 前端共享模块
- `frontend/src/utils/accidentTypes.test.ts` — 前端单测

**修改：**
- `backend/app/services/risk_notice_card_data.py` — 27 类标志组/处置模板
- `backend/app/services/risk_assessment_service.py:22/:60/:61/:77` — 标准引用 + 27 类 + 修错字
- `backend/app/services/risk_ai_service.py:166/:202/:221` — 27 类约束
- `backend/seed_prompts_full.py:367/:432/:440` — 提示词 + 重新 seed
- `backend/app/routers/risk_sources_ext.py:183/:309/:521/:683` — 修 NameError + 27 类
- `backend/app/services/risk_source_migration_service.py:82/:198` — normalize 兜底
- `backend/app/routers/chat.py:38` — 工具参数描述（可选）
- `backend/app/regulations/data/index.yaml` — 新法规入索引
- `backend/app/regulations/data/texts/gb6441_1986.md` — 标注废止
- `backend/tests/test_risk_notice_card_data.py` / `test_risk_notice_card_service.py` — 27 类断言
- `frontend/src/utils/riskMethodEngine.ts:32` — 删除本地清单
- `frontend/src/utils/constants.ts:1` — 删除 PRESET_RISK_CATEGORIES
- `frontend/src/pages/Plan/PlanCreatePage.tsx:116-125` — 共享 27 类
- `frontend/src/mobile/screens/PlanCreateScreen.tsx:60-67/:205-235` — chips 选择
- `frontend/src/components/enterprise/RiskEventForm.tsx:414` — 占位文案
- `frontend/src/components/enterprise/RiskSourceForm.tsx:8/:143` — 导入共享清单

---

## 共享常量（任务 1/2 的最终内容）

**27 类清单（按国标表 1 顺序，全项目唯一事实源）：**

```
物体打击、厂（场）内车辆致害、道路（轨道）车辆致害、机械致害、起重致害、触电、
淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、
可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、
高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他
```

**新旧映射（22 项 = 20 旧标 + 2 旧预设）：**

```
物体打击→物体打击        车辆伤害→厂（场）内车辆致害    机械伤害→机械致害
起重伤害→起重致害        触电→触电                    淹溺→淹溺
灼烫→灼烫                火灾→火灾                    高处坠落→高处坠落
坍塌→坍塌                冒顶片帮→坍塌                透水→水害
放炮→民用爆炸物品爆炸    火药爆炸→民用爆炸物品爆炸    瓦斯爆炸→可燃气体爆炸
锅炉爆炸→容器爆炸        容器爆炸→容器爆炸            其他爆炸→其他
中毒和窒息→中毒          其他伤害→其他                爆炸→其他
中毒窒息→中毒
```

---

### 任务 1：后端共享模块（TDD）

**文件：**
- 创建：`backend/app/services/accident_types.py`
- 测试：`backend/tests/test_accident_types.py`

- [ ] **步骤 1：编写失败的测试** `backend/tests/test_accident_types.py`

```python
"""事故类型共享模块测试：GB 6441-2025 27 类清单、新旧映射、normalize/split。"""
from app.services.accident_types import (
    ACCIDENT_TYPES_2025,
    LEGACY_TO_NEW_MAP,
    normalize_accident_type,
    split_accident_values,
)


def test_accident_types_2025_complete_and_ordered():
    expected = [
        "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
        "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
        "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
        "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
        "泄漏", "其他",
    ]
    assert ACCIDENT_TYPES_2025 == expected
    assert len(ACCIDENT_TYPES_2025) == 27
    assert len(set(ACCIDENT_TYPES_2025)) == 27


def test_legacy_map_covers_all_old_standard_and_presets():
    old_standard = [
        "物体打击", "车辆伤害", "机械伤害", "起重伤害", "触电", "淹溺", "灼烫", "火灾",
        "高处坠落", "坍塌", "冒顶片帮", "透水", "放炮", "火药爆炸", "瓦斯爆炸", "锅炉爆炸",
        "容器爆炸", "其他爆炸", "中毒和窒息", "其他伤害",
    ]
    for old in old_standard:
        assert old in LEGACY_TO_NEW_MAP, old
        assert LEGACY_TO_NEW_MAP[old] in ACCIDENT_TYPES_2025
    assert LEGACY_TO_NEW_MAP["爆炸"] == "其他"
    assert LEGACY_TO_NEW_MAP["中毒窒息"] == "中毒"
    assert LEGACY_TO_NEW_MAP["瓦斯爆炸"] == "可燃气体爆炸"
    assert LEGACY_TO_NEW_MAP["锅炉爆炸"] == "容器爆炸"


def test_normalize_three_states():
    assert normalize_accident_type("火灾") == "火灾"
    assert normalize_accident_type("中毒和窒息") == "中毒"
    assert normalize_accident_type("设备损坏/数据丢失") == "设备损坏/数据丢失"
    assert normalize_accident_type("") == ""
    assert normalize_accident_type(None) == ""


def test_split_accident_values():
    assert split_accident_values("火灾、触电") == ["火灾", "触电"]
    assert split_accident_values("火灾,爆炸") == ["火灾", "爆炸"]
    assert split_accident_values("火灾") == ["火灾"]
    assert split_accident_values("") == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_accident_types.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.accident_types'`

- [ ] **步骤 3：实现共享模块** `backend/app/services/accident_types.py`

```python
"""事故类型共享常量：GB 6441-2025《生产安全事故分类与编码》27 类 + 新旧映射。

全项目事故类型/风险类别唯一事实源。所有下拉、提示词、告知卡映射、迁移逻辑
必须从此模块引用，禁止再散落硬编码清单。
"""

ACCIDENT_TYPES_2025: list[str] = [
    "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
    "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
    "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
    "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
    "泄漏", "其他",
]

# GB/T 6441-1986 20 类 + 旧系统预设类别 → GB 6441-2025
LEGACY_TO_NEW_MAP: dict[str, str] = {
    "物体打击": "物体打击",
    "车辆伤害": "厂（场）内车辆致害",   # 拆分默认：企业风控场景默认厂内
    "机械伤害": "机械致害",
    "起重伤害": "起重致害",
    "触电": "触电",
    "淹溺": "淹溺",
    "灼烫": "灼烫",
    "火灾": "火灾",
    "高处坠落": "高处坠落",
    "坍塌": "坍塌",
    "冒顶片帮": "坍塌",                 # 删除并入
    "透水": "水害",                     # 删除替代
    "放炮": "民用爆炸物品爆炸",         # 删除替代
    "火药爆炸": "民用爆炸物品爆炸",     # 删除替代
    "瓦斯爆炸": "可燃气体爆炸",         # 删除替代（瓦斯=甲烷）
    "锅炉爆炸": "容器爆炸",             # 删除替代（锅炉属承压容器）
    "容器爆炸": "容器爆炸",
    "其他爆炸": "其他",                 # 删除兜底
    "中毒和窒息": "中毒",               # 拆分默认：有限空间事故以中毒为主因
    "其他伤害": "其他",
    "爆炸": "其他",                     # 旧预设泛化值，无法细分
    "中毒窒息": "中毒",                 # 旧预设
}


def normalize_accident_type(value: str | None) -> str:
    """旧值→新值；27 类原样；未知值原样保留（自由事件名/复合表述）。"""
    if not value:
        return ""
    v = str(value).strip()
    return LEGACY_TO_NEW_MAP.get(v, v)


def split_accident_values(value: str | None) -> list[str]:
    """按顿号/逗号拆分多值（预案事故类型、风险源类别）。"""
    if not value:
        return []
    import re
    return [p.strip() for p in re.split(r"[、,]", str(value)) if p.strip()]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_accident_types.py -v`
预期：PASS（4 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/accident_types.py backend/tests/test_accident_types.py
git commit -m "feat(accident-types): add shared GB 6441-2025 module with legacy mapping"
```

---

### 任务 2：前端共享模块（TDD）

**文件：**
- 创建：`frontend/src/utils/accidentTypes.ts`
- 测试：`frontend/src/utils/accidentTypes.test.ts`

- [ ] **步骤 1：编写失败的测试** `frontend/src/utils/accidentTypes.test.ts`

```ts
import {
  ACCIDENT_TYPES_2025,
  LEGACY_TO_NEW_ACCIDENT_TYPE_MAP,
  normalizeAccidentType,
} from "./accidentTypes";

describe("accidentTypes (GB 6441-2025)", () => {
  it("exposes exactly 27 ordered types", () => {
    expect(ACCIDENT_TYPES_2025).toEqual([
      "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
      "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
      "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
      "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
      "泄漏", "其他",
    ]);
    expect(new Set(ACCIDENT_TYPES_2025).size).toBe(27);
  });

  it("maps all 20 old standard types and 2 presets", () => {
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["瓦斯爆炸"]).toBe("可燃气体爆炸");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["锅炉爆炸"]).toBe("容器爆炸");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["爆炸"]).toBe("其他");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["中毒窒息"]).toBe("中毒");
    expect(Object.keys(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP)).toHaveLength(22);
  });

  it("normalizes new/legacy/unknown values", () => {
    expect(normalizeAccidentType("火灾")).toBe("火灾");
    expect(normalizeAccidentType("中毒和窒息")).toBe("中毒");
    expect(normalizeAccidentType("设备损坏/数据丢失")).toBe("设备损坏/数据丢失");
    expect(normalizeAccidentType("")).toBe("");
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd frontend && npx vitest run src/utils/accidentTypes.test.ts`
预期：FAIL，`Cannot find module './accidentTypes'`

- [ ] **步骤 3：实现共享模块** `frontend/src/utils/accidentTypes.ts`

```ts
/** 事故类型共享常量：GB 6441-2025《生产安全事故分类与编码》27 类 + 新旧映射。
 *  全前端事故类型/风险类别唯一事实源。 */

export const ACCIDENT_TYPES_2025 = [
  "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
  "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
  "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
  "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
  "泄漏", "其他",
] as const;

/** GB/T 6441-1986 20 类 + 旧系统预设类别 → GB 6441-2025。 */
export const LEGACY_TO_NEW_ACCIDENT_TYPE_MAP: Record<string, string> = {
  "物体打击": "物体打击",
  "车辆伤害": "厂（场）内车辆致害",
  "机械伤害": "机械致害",
  "起重伤害": "起重致害",
  "触电": "触电",
  "淹溺": "淹溺",
  "灼烫": "灼烫",
  "火灾": "火灾",
  "高处坠落": "高处坠落",
  "坍塌": "坍塌",
  "冒顶片帮": "坍塌",
  "透水": "水害",
  "放炮": "民用爆炸物品爆炸",
  "火药爆炸": "民用爆炸物品爆炸",
  "瓦斯爆炸": "可燃气体爆炸",
  "锅炉爆炸": "容器爆炸",
  "容器爆炸": "容器爆炸",
  "其他爆炸": "其他",
  "中毒和窒息": "中毒",
  "其他伤害": "其他",
  "爆炸": "其他",
  "中毒窒息": "中毒",
};

export function normalizeAccidentType(value: string): string {
  if (!value) return "";
  const v = value.trim();
  return LEGACY_TO_NEW_ACCIDENT_TYPE_MAP[v] ?? v;
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd frontend && npx vitest run src/utils/accidentTypes.test.ts`
预期：PASS（3 passed）

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/utils/accidentTypes.ts frontend/src/utils/accidentTypes.test.ts
git commit -m "feat(accident-types): add shared frontend GB 6441-2025 module"
```

---

### 任务 3：告知卡常量升级为 27 类（TDD）

**文件：**
- 修改：`backend/app/services/risk_notice_card_data.py`（整文件重写，99→约 180 行）
- 修改：`backend/app/services/risk_notice_card_service.py:123-130`（match_signs 加 normalize）
- 修改：`backend/tests/test_risk_notice_card_data.py`（27 类断言）
- 修改：`backend/tests/test_risk_notice_card_service.py`（旧类型→新类型）

- [ ] **步骤 1：更新测试（先失败）** `backend/tests/test_risk_notice_card_data.py`

将全部 `GB6441_ACCIDENT_TYPES` 引用替换为 `ACCIDENT_TYPES_2025`（import 同步改），并将以下断言更新：

```python
def test_eyewash_not_mapped_to_thermal_burn_or_inhalation():
    for accident_type in ("灼烫", "中毒"):
        names = [s["name"] for s in SIGN_GROUPS[accident_type]]
        assert "洗眼台" not in names, f"{accident_type} 不应包含洗眼台"


def test_vehicle_group_has_no_emergency_exit():
    names = [s["name"] for s in SIGN_GROUPS["厂（场）内车辆致害"]]
    assert "当心车辆" in names
    assert "紧急出口" not in names


def test_container_explosion_group_has_exit_not_static():
    names = [s["name"] for s in SIGN_GROUPS["容器爆炸"]]
    assert "当心爆炸" in names
    assert "必须消除静电" in names  # 容器爆炸保留静电提示
    assert "紧急出口" in names


def test_other_group_has_no_production_ppe():
    names = [s["name"] for s in SIGN_GROUPS["其他"]]
    assert "紧急出口" in names
    for bad in ("必须戴安全帽", "当心机械伤人", "禁止烟火"):
        assert bad not in names, f"其他组不应包含 {bad}"


def test_new_2025_types_have_sign_groups():
    for t in ("道路（轨道）车辆致害", "跌落", "管道爆炸", "可燃液体蒸气爆炸", "粉尘爆炸",
              "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "窒息", "滑坡", "泄漏"):
        assert SIGN_GROUPS[t], t
        assert EMERGENCY_TEMPLATES[t], t
```

`test_risk_notice_card_service.py` 同步替换：
- `["其他伤害", "灼烫"]` → `["其他", "灼烫"]`
- `["中毒和窒息"]` → `["中毒"]`
- `match_signs(["车辆伤害"])` → `match_signs(["厂（场）内车辆致害"])`
- `match_signs(["锅炉爆炸"])` → `match_signs(["容器爆炸"])`（断言改为「有紧急出口」）
- 新增：`match_signs(["瓦斯爆炸"])` 必须命中「必须消除静电」（兼容旧值 normalize）

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_data.py tests/test_risk_notice_card_service.py -v`
预期：FAIL（SIGN_GROUPS 缺新键、旧键失效）

- [ ] **步骤 3：重写 `backend/app/services/risk_notice_card_data.py`**

要点：`from app.services.accident_types import ACCIDENT_TYPES_2025`；删除本地 `GB6441_ACCIDENT_TYPES`；`SIGN_GROUPS` 保留/更名/承接 16 组 + 新增 11 组（见下方清单），键全集恰为 27 类；`DEFAULT_SIGN_GROUP` 取 `SIGN_GROUPS["其他"]`；`EXTRA_SIGN_GROUPS` 保留 `{"火灾爆炸": list(SIGN_GROUPS["火灾"])}`；`EMERGENCY_TEMPLATES` 同键 27 项。

新增 11 组标志（复用现有 36 个 SVG，测试会校验 svg 存在）：

```python
"道路（轨道）车辆致害": [W("当心车辆", "warning-vehicle"), P("禁止通行", "prohibition-pass")],
"跌落": [W("当心坠落", "warning-fall"), P("禁止抛物", "prohibition-throwing")],
"管道爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须消除静电", "instruction-eliminate-static")],
"可燃液体蒸气爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须消除静电", "instruction-eliminate-static")],
"粉尘爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须消除静电", "instruction-eliminate-static")],
"烟花爆竹爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), P("禁止动火作业", "prohibition-hot-work")],
"其他可燃固体爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须消除静电", "instruction-eliminate-static")],
"高温熔融物爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须穿防护服", "instruction-protective-suit")],
"窒息": [W("当心窒息", "warning-suffocation"), W("当心有限空间", "warning-confined-space"), I("必须通风", "instruction-ventilate")],
"滑坡": [W("当心坍塌", "warning-collapse"), P("禁止通行", "prohibition-pass")],
"泄漏": [W("当心中毒", "warning-poison"), I("必须戴防毒面具", "instruction-gas-mask"), I("必须通风", "instruction-ventilate")],
```

更名/承接组（内容沿用旧组）：

```python
"厂（场）内车辆致害": 旧"车辆伤害"组
"机械致害": 旧"机械伤害"组
"起重致害": 旧"起重伤害"组
"水害": 旧"透水"组
"民用爆炸物品爆炸": 旧"火药爆炸"组
"可燃气体爆炸": 旧"瓦斯爆炸"组
"中毒": [W("当心中毒", "warning-poison"), I("必须戴防毒面具", "instruction-gas-mask"), I("必须通风", "instruction-ventilate")]
"其他": 旧"其他伤害"组
```

新增 11 组应急处置模板：

```python
"道路（轨道）车辆致害": ["立即制动停车，设置警戒", "现场急救伤员，拨打 120", "保护现场，配合事故调查"],
"跌落": ["立即停止作业，保护现场", "检查伤员意识与伤情，勿随意搬动", "拨打 120 送医"],
"管道爆炸": ["立即切断气源电源，撤离现场", "拨打 119/120 报警", "警戒隔离，防止二次爆炸"],
"可燃液体蒸气爆炸": ["立即切断火源电源，撤离现场", "拨打 119/120 报警", "严禁烟火，通风稀释，配合救援"],
"粉尘爆炸": ["立即断电停机，撤离现场", "拨打 119/120 报警", "禁止扬尘扰动，防止二次爆炸"],
"烟花爆竹爆炸": ["立即撤离现场，警戒隔离", "拨打 119/120 报警", "清点人数，配合专业救援"],
"其他可燃固体爆炸": ["立即切断电源火源，撤离现场", "拨打 119/120 报警", "警戒隔离，防止复燃爆炸"],
"高温熔融物爆炸": ["立即撤离危险区域，警戒隔离", "对灼烫伤员用清水冲洗创面", "拨打 119/120 报警"],
"窒息": ["佩戴防护用品后进入，禁止盲目施救", "立即通风，将伤员移至新鲜空气处", "拨打 120，必要时心肺复苏"],
"滑坡": ["立即撤出危险区域，设置警戒", "在确保安全前提下搜救", "拨打 119/120 请求专业救援"],
"泄漏": ["立即切断泄漏源，警戒隔离", "佩戴防护用品，通风稀释", "拨打 119/120 报警，报告企业应急指挥部"],
```

`match_signs`（`risk_notice_card_service.py:123`）在查表前加兼容：

```python
def match_signs(accident_types: list[str]) -> list[dict]:
    """按 SIGN_GROUPS 合并去重，旧值经 normalize 映射；按 警告→禁止→指令→提示 排序。"""
    from app.services.accident_types import normalize_accident_type
    groups = []
    for at in accident_types:
        key = normalize_accident_type(at)
        group = EXTRA_SIGN_GROUPS.get(key) or SIGN_GROUPS.get(key, DEFAULT_SIGN_GROUP)
        groups.extend(group)
    ...
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_data.py tests/test_risk_notice_card_service.py -v`
预期：PASS；再跑 `python -m pytest tests/test_risk_notice_card_api.py -v` 确认 API 测试（用旧值 火灾 的仍通过）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_notice_card_data.py backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_data.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(accident-types): rebuild risk notice card groups for GB 6441-2025"
```

---

### 任务 4：后端 AI 提示词与种子模板更新

**文件：**
- 修改：`backend/app/services/risk_assessment_service.py`
- 修改：`backend/app/services/risk_ai_service.py`
- 修改：`backend/seed_prompts_full.py`

- [ ] **步骤 1：更新 `risk_assessment_service.py` 提示词**

精确替换（注意 `\u00d7` 等转义保持原样）：

```text
替换 1（:22）：
- 《企业职工伤亡事故分类》（GB 6441-1986）
→ - 《生产安全事故分类与编码》（GB 6441-2025）

替换 2（:60）：
2. 事故类型统一按 GB 6441-1986 分类：物体打击、车辆伤害、机械伤害、起重伤害、触电、淹溾、灼烫、火灾、高处坠落、坍塌、锅炉爆炸、容器爆炸、其他爆炸、中毒和窒息、其他伤害。
→ 2. 事故类型统一按 GB 6441-2025 分类：物体打击、厂（场）内车辆致害、道路（轨道）车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他。

替换 3（:61 行末重复清单）：同上 27 类（去掉重复句亦可，保留同 27 类）

替换 4（:77 结论示例）：
《企业职工伤亡事故分类》（GB 6441-1986）→《生产安全事故分类与编码》（GB 6441-2025）
（示例正文里的 火灾、爆炸；中毒和窒息、车辆伤害 等旧词可保留为示例语义，但改为：较大风险事故类型为：火灾、可燃气体爆炸；一般风险事故类型为：触电、中毒、车辆致害；低风险事故类型为：物体打击、高处坠落、灼烫、淹溺、起重致害、机械致害）
```

- [ ] **步骤 2：更新 `risk_ai_service.py`**

```text
替换 1（:166/:221 system）：
精通 GB/T 13861 和 GB 6441 → 精通 GB/T 13861 和 GB 6441-2025

替换 2（:202）：
- accident_type: 事故类型（按 GB 6441-1986）
→ - accident_type: 事故类型（按 GB 6441-2025 的 27 类：物体打击、厂（场）内车辆致害、道路（轨道）车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他）
```

- [ ] **步骤 3：更新 `seed_prompts_full.py`**

```text
替换（:367 system_prompt 内）：
【技术标准】- 《企业职工伤亡事故分类》（GB 6441-1986）→ 《生产安全事故分类与编码》（GB 6441-2025）
术语标准第 2 条 15 类 → 27 类全文（同 risk_assessment_service 替换 2）
淹溾 → 淹溺
结论示例引文 GB 6441-1986 → GB 6441-2025

替换（:432/:440 辨识维度）：
按火灾/爆炸、中毒和窒息、灼烧、触电、机械伤害、高处坠落、物体打击、车辆伤害、淹溺、其他伤害等事故类型
→ 按 GB 6441-2025 事故类型（物体打击、厂（场）内车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他等）
```

- [ ] **步骤 4：重新 seed 同步数据库**

运行：`cd backend && python seed_prompts_full.py`
预期：`Seed complete: 0 new, N updated`（提示词模板按 template_code 幂等更新）

- [ ] **步骤 5：跑相关测试 + Commit**

运行：`cd backend && python -m pytest tests/test_prompt_templates_onsite_cards.py tests/test_generation_batch_refactor.py -q`
预期：PASS

```bash
git add backend/app/services/risk_assessment_service.py backend/app/services/risk_ai_service.py backend/seed_prompts_full.py
git commit -m "feat(accident-types): update AI prompts and seeds to GB 6441-2025"
```

---

### 任务 5：前端消费点改造

**文件：**
- 修改：`frontend/src/utils/riskMethodEngine.ts:32`
- 修改：`frontend/src/utils/constants.ts:1-4`
- 修改：`frontend/src/components/enterprise/RiskEventForm.tsx:9/:414`
- 修改：`frontend/src/components/enterprise/RiskSourceForm.tsx:8/:143`
- 修改：`frontend/src/pages/Plan/PlanCreatePage.tsx:116-125`
- 修改：`frontend/src/mobile/screens/PlanCreateScreen.tsx`

- [ ] **步骤 1：删除旧清单、接入共享模块**

```text
riskMethodEngine.ts:32 删除 `export const ACCIDENT_TYPES = [...15 类];`
constants.ts:1-4 删除 `PRESET_RISK_CATEGORIES`
RiskEventForm.tsx:9 改 import：`import { ACCIDENT_TYPES_2025 } from "@/utils/accidentTypes";`（:415 options 用 ACCIDENT_TYPES_2025，:414 占位文案改「选择 GB 6441-2025 事故类型」）
RiskSourceForm.tsx:8 改 import：`import { ACCIDENT_TYPES_2025 } from "@/utils/accidentTypes";`（:143 options 用 ACCIDENT_TYPES_2025）
PlanCreatePage.tsx:116-125 options 改为 `ACCIDENT_TYPES_2025.map((t) => ({ value: t, label: t }))`，顶部加 import
```

- [ ] **步骤 2：移动端 PlanCreateScreen 改为 27 类 chips**

将 :60-67 `accidentOptions` 逻辑与 :205-235 渲染改为：始终展示 `ACCIDENT_TYPES_2025` 全集 chips；风险源推荐值（`rows.map(r => normalizeAccidentType(r.accident_type))`）置前并默认勾选；移除自由文本 `<Input>` 兜底。

```tsx
// 顶部 import
import { ACCIDENT_TYPES_2025, normalizeAccidentType } from "@/utils/accidentTypes";

// 推荐值（风险源事件类型，归一化后置前）
const recommended = useMemo(
  () => [...new Set(rows.map((r) => normalizeAccidentType(r.accident_type)))]
    .filter((t) => ACCIDENT_TYPES_2025.includes(t as (typeof ACCIDENT_TYPES_2025)[number])),
  [rows],
);
const accidentOptions = useMemo(
  () => [...recommended, ...ACCIDENT_TYPES_2025.filter((t) => !recommended.includes(t))],
  [recommended],
);
```

渲染区删除 `{accidentOptions.length > 0 ? (...) : (<Input .../>)}` 三元，直接渲染 `accidentOptions.map(...)` 的 chips（原 chip 交互保留）。

- [ ] **步骤 3：运行前端门禁**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：exit 0；若 `eventPayload.test.ts`/`riskHierarchyEvents.test.ts` 等引用旧值导致失败，将测试值替换为仍存在的值（如 火灾）或新值。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/utils/riskMethodEngine.ts frontend/src/utils/constants.ts frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/components/enterprise/RiskSourceForm.tsx frontend/src/pages/Plan/PlanCreatePage.tsx frontend/src/mobile/screens/PlanCreateScreen.tsx
git commit -m "feat(accident-types): switch frontend dropdowns and mobile chips to GB 6441-2025"
```

---

### 任务 6：风险源模板 NameError 修复 + AI 建议链路约束

**文件：**
- 修改：`backend/app/routers/risk_sources_ext.py`
- 修改：`backend/app/services/risk_source_migration_service.py`

- [ ] **步骤 1：`risk_sources_ext.py` 接入共享清单**

```text
顶部 import：`from app.services.accident_types import ACCIDENT_TYPES_2025`
4 处 `PRESET_RISK_CATEGORIES` → `ACCIDENT_TYPES_2025`（:183 模板下拉、:309 导入校验、:521 AI 提问、:683 AI 生成）
```

- [ ] **步骤 2：编写回归测试（NameError）** `backend/tests/test_risk_sources_ext.py`

```python
"""风险源扩展端点回归：模板下载不再 NameError，类别下拉含 27 类。

按 test_risk_notice_card_api.py 惯例：独立 FastAPI 挂载 router，
dependency_overrides 替换鉴权与 DB 依赖。
"""
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import risk_sources_ext


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(risk_sources_ext.router, prefix="/api/v1")

    async def _get_enterprise_data(enterprise_id, user_id, db):
        return {"name": "甲公司", "industry": "工贸", "business_scope": "", "building_overview": "", "employee_count": 10, "address": ""}

    monkeypatch.setattr(risk_sources_ext, "_get_enterprise_data", _get_enterprise_data)

    async def _current_user():
        return type("U", (), {"id": "u1", "email": "admin@test.com"})()

    async def _db():
        yield None

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_risk_source_template_uses_2025_categories(client):
    resp = client.get("/api/v1/enterprises/e1/risk-sources/template")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws["A2"].value == "火灾"
    dv = ws.data_validations.dataValidation[0]
    assert "机械致害" in dv.formula1
    assert "锅炉爆炸" not in dv.formula1
```

- [ ] **步骤 3：`risk_source_migration_service.py` normalize 兜底**

```text
:82 区域：`item["suggested_event"] = ai.get("suggested_accident_type") or ...`
→ 对该值先 `normalize_accident_type(...)` 再赋值；
:198 创建 RiskEvent 时：`accident_type=normalize_accident_type(mapping.accident_type)`
顶部 import：`from app.services.accident_types import normalize_accident_type`
```

- [ ] **步骤 4：测试 + Commit**

运行：`cd backend && python -m pytest tests/test_risk_sources_ext.py tests/test_risk_source_migration*.py -q`
预期：PASS

```bash
git add backend/app/routers/risk_sources_ext.py backend/app/services/risk_source_migration_service.py backend/tests/test_risk_sources_ext.py
git commit -m "fix(accident-types): repair risk source template NameError, normalize AI suggestions"
```

---

### 任务 7：存量数据迁移 SQL

**文件：**
- 创建：`backend/db_migration_accident_types_2025.sql`

- [ ] **步骤 1：编写迁移 SQL**

```sql
-- 事故类型存量迁移：GB/T 6441-1986 + 旧预设 → GB 6441-2025（幂等）
-- 自由事件名/复合表述（不在映射表内）保持原样。
-- 映射函数（单值）
CREATE OR REPLACE FUNCTION _migrate_accident_type(v text) RETURNS text AS $$
  SELECT CASE v
    WHEN '物体打击' THEN '物体打击'
    WHEN '车辆伤害' THEN '厂（场）内车辆致害'
    WHEN '机械伤害' THEN '机械致害'
    WHEN '起重伤害' THEN '起重致害'
    WHEN '冒顶片帮' THEN '坍塌'
    WHEN '透水' THEN '水害'
    WHEN '放炮' THEN '民用爆炸物品爆炸'
    WHEN '火药爆炸' THEN '民用爆炸物品爆炸'
    WHEN '瓦斯爆炸' THEN '可燃气体爆炸'
    WHEN '锅炉爆炸' THEN '容器爆炸'
    WHEN '其他爆炸' THEN '其他'
    WHEN '中毒和窒息' THEN '中毒'
    WHEN '其他伤害' THEN '其他'
    WHEN '爆炸' THEN '其他'
    WHEN '中毒窒息' THEN '中毒'
    ELSE v END;
$$ LANGUAGE sql IMMUTABLE;

-- 1) 风险事件（单值）
UPDATE risk_events SET accident_type = _migrate_accident_type(accident_type);

-- 2) 预案（顿号/逗号分隔多值，回拼保留顿号）
UPDATE plan_projects p SET accident_type = sub.new_val
FROM (
  SELECT id, string_agg(_migrate_accident_type(t), '、' ORDER BY ord) AS new_val
  FROM plan_projects, unnest(string_to_array(accident_type, '、')) WITH ORDINALITY AS x(t, ord)
  WHERE accident_type IS NOT NULL AND accident_type <> ''
  GROUP BY id
) sub WHERE p.id = sub.id;

-- 3) 风险源类别（逗号分隔）
UPDATE risk_sources s SET categories = sub.new_val
FROM (
  SELECT id, string_agg(_migrate_accident_type(t), ',' ORDER BY ord) AS new_val
  FROM risk_sources, unnest(string_to_array(categories, ',')) WITH ORDINALITY AS x(t, ord)
  WHERE categories <> ''
  GROUP BY id
) sub WHERE s.id = sub.id;

-- 4) 告知卡快照（JSONB 数组逐元素；不动 signs）
UPDATE risk_notice_cards
SET content = jsonb_set(
  content,
  '{accident_types}',
  (SELECT jsonb_agg(_migrate_accident_type(elem::text)::jsonb #>> '{}')
   FROM jsonb_array_elements_text(content->'accident_types') AS elem)
)
WHERE content ? 'accident_types';

-- 清理
DROP FUNCTION IF EXISTS _migrate_accident_type(text);
```

注意：迁移前先对 `plan_projects` 中同时含顿号与逗号的异常值人工核对（当前库均为单值或顿号）；若存在逗号混用，先执行一次 `UPDATE plan_projects SET accident_type = replace(accident_type, ',', '、') WHERE accident_type LIKE '%,%';`

- [ ] **步骤 2：先在本地库验证（幂等 + 校验）**

运行：
```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "BEGIN; \i /dev/stdin" < backend/db_migration_accident_types_2025.sql
```
（或 `docker exec -i emergency-plan-db psql -U postgres -d emergency_plan < backend/db_migration_accident_types_2025.sql`）

校验查询（旧值零残留）：
```sql
SELECT accident_type, count(*) FROM risk_events
WHERE accident_type IN ('车辆伤害','机械伤害','起重伤害','冒顶片帮','透水','放炮','火药爆炸','瓦斯爆炸','锅炉爆炸','其他爆炸','中毒和窒息','其他伤害','爆炸','中毒窒息')
GROUP BY 1;
```
预期：0 行。再原样重跑一次迁移脚本，确认幂等（结果不变）。

- [ ] **步骤 3：自由值核对**

```sql
SELECT accident_type, count(*) FROM risk_events GROUP BY 1 ORDER BY 2 DESC;
```
预期：27 类 + 保留的自由值（火灾爆炸、设备损坏/数据丢失 等），自由值数量与迁移前一致。

- [ ] **步骤 4：Commit**

```bash
git add backend/db_migration_accident_types_2025.sql
git commit -m "feat(accident-types): add idempotent legacy-to-2025 data migration SQL"
```

---

### 任务 8：法规库补充 GB 6441-2025

**文件：**
- 创建：`backend/app/regulations/data/texts/gb6441_2025.md`
- 修改：`backend/app/regulations/data/texts/gb6441_1986.md`
- 修改：`backend/app/regulations/data/index.yaml`

- [ ] **步骤 1：编写 `gb6441_2025.md`**

内容为官方标准条文整理：前言变更说明（a-u 项）、第 4 章事故分类（4.1 基本事故类型表 1 全 27 行：序号/名称/说明）、4.2 人身伤害程度分类、4.3 行业分类、第 5 章事故类型编码（WSA + 9 位）。表 1 的 27 行说明取自官方文本（说明文字以「物体在受重力或其他外力的作用下产生运动，打击人体或设备设施造成的事故」风格撰写，与解读材料一致）。头部元数据格式与 `gb6441_1986.md` 一致：

```markdown
# GB 6441-2025 生产安全事故分类与编码

- 发布机关：国家市场监督管理总局（国家标准化管理委员会）
- 发布日期：2025-12-31
- 施行日期：2026-07-01
- 代替：GB/T 6441-1986《企业职工伤亡事故分类》
- 适用主题：事故分类、风险评估

---
```

- [ ] **步骤 2：`gb6441_1986.md` 标注废止**

头部追加：

```markdown
> ⚠ 本文件已被《生产安全事故分类与编码》（GB 6441-2025）全部代替，2026-07-01 起施行；仅作历史对照保留。
```

- [ ] **步骤 3：`index.yaml` 加入新法规**

`risk_assessment.optional` 列表追加 `gb6441_2025`（保留 `gb6441_1986` 供对照）。

- [ ] **步骤 4：重建检索索引**

运行：`cd backend && python -m scripts.build_regulation_index`（重建 BM25/向量索引；若脚本依赖 AI 则改走管理员 API `POST /api/v1/regulations/reindex`）
预期：日志显示新增 `gb6441_2025` 条文入库

- [ ] **步骤 5：Commit**

```bash
git add backend/app/regulations/data/texts/gb6441_2025.md backend/app/regulations/data/texts/gb6441_1986.md backend/app/regulations/data/index.yaml backend/app/regulations/data/bm25_index.json
git commit -m "feat(accident-types): add GB 6441-2025 to regulation library, mark 1986 superseded"
```

---

### 任务 9：全量门禁与收尾

**文件：** 无（验证）

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && python -m pytest -q`
预期：全部 PASS（约 1035+，含新增）

- [ ] **步骤 2：前端全量门禁**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：exit 0，全部测试通过

- [ ] **步骤 3：旧清单零残留扫描**

运行：
```bash
rg -n "冒顶片帮|透水|放炮|火药爆炸|瓦斯爆炸|锅炉爆炸|其他爆炸|中毒和窒息|其他伤害|GB 6441-1986|GB6441-1986" backend frontend/src --glob "*.py" --glob "*.ts" --glob "*.tsx" --glob "*.md"
```
预期：仅出现在 `accident_types.py`/`accidentTypes.ts`（映射表）、`gb6441_1986.md`（历史对照）、迁移 SQL 与设计/计划文档中。

- [ ] **步骤 4：Docker 冒烟**

```bash
docker restart emergency-plan-backend
curl -s http://localhost:8000/api/health
```
预期：200；前端 5173 页面预案创建下拉含 27 类。

- [ ] **步骤 5：图谱同步 + 收尾提交**

```bash
codegraph sync .
graphify update .
```
如有遗留 lint 债（既有项）不处理，仅确认零新增。

---

## 自检记录

- **规格覆盖度**：规格 §4（27 类清单）→ 任务 1/2；§5（映射表）→ 任务 1/2/7；§6（共享模块）→ 任务 1/2；§7（消费点）→ 任务 3/4/5/6/8；§8（迁移）→ 任务 7；§9（测试）→ 各任务内建；§10/11（风险与验证）→ 任务 9
- **占位符**：无 TODO/待定；每个代码步骤含实际代码或精确替换文本
- **类型一致性**：`ACCIDENT_TYPES_2025` / `LEGACY_TO_NEW_MAP` / `normalize_accident_type` / `normalizeAccidentType` 前后端命名一致；`SIGN_GROUPS` 键集 = `EMERGENCY_TEMPLATES` 键集 = 27 类，测试强制断言
