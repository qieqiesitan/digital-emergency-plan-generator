# Codex Custom Subagents task handoff v1

Task: notice_cards_2025

## 任务：风险告知卡常量升级为 GB 6441-2025 27 类（TDD）

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；测试在 `backend` 子目录执行（先 `cd backend`）。前置依赖已提交：`backend/app/services/accident_types.py`（ACCIDENT_TYPES_2025 / LEGACY_TO_NEW_MAP / normalize_accident_type）。

### 背景

风险告知卡按事故类型匹配安全标志组（SIGN_GROUPS）与应急处置模板（EMERGENCY_TEMPLATES）。现需从旧 20 类升级为 GB 6441-2025 的 27 类：16 组沿用/更名/承接、11 组新增、7 组旧键删除；`match_signs` 兼容旧值（normalize 后查表）。

### 第 1 步：更新测试（先失败，红灯）

**文件 1：`backend\tests\test_risk_notice_card_data.py`**

做以下修改（保留其余测试）：

1. import 区：`GB6441_ACCIDENT_TYPES` 改为从 `app.services.accident_types` 导入 `ACCIDENT_TYPES_2025`
2. 全部 `GB6441_ACCIDENT_TYPES` 引用替换为 `ACCIDENT_TYPES_2025`
3. 替换以下测试函数：

```python
def test_eyewash_not_mapped_to_thermal_burn_or_inhalation():
    for accident_type in ("灼烫", "中毒"):
        names = [s["name"] for s in SIGN_GROUPS[accident_type]]
        assert "洗眼台" not in names, f"{accident_type} 不应包含洗眼台"


def test_vehicle_group_has_no_emergency_exit():
    names = [s["name"] for s in SIGN_GROUPS["厂（场）内车辆致害"]]
    assert "当心车辆" in names
    assert "紧急出口" not in names


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

4. 删除引用旧键的测试：`test_vehicle_injury_group_has_no_emergency_exit`（旧键车辆伤害）、`test_boiler_explosion_group_has_no_static_instruction`（旧键锅炉爆炸）

**文件 2：`backend\tests\test_risk_notice_card_service.py`**

替换：

```python
def test_match_signs_excludes_eyewash_for_burn_and_poisoning():
    for accident_types in (["灼烫"], ["其他", "灼烫"], ["中毒"]):
        signs = match_signs(accident_types)
        assert all(s["name"] != "洗眼台" for s in signs), accident_types


def test_match_signs_vehicle_and_explosion():
    vehicle = match_signs(["厂（场）内车辆致害"])
    assert all(s["name"] != "紧急出口" for s in vehicle)
    explosion = match_signs(["容器爆炸"])
    assert any(s["name"] == "紧急出口" for s in explosion)


def test_match_signs_normalizes_legacy_values():
    """旧值经 normalize 映射到新组：瓦斯爆炸→可燃气体爆炸（含防静电）。"""
    signs = match_signs(["瓦斯爆炸"])
    assert any(s["name"] == "必须消除静电" for s in signs)
```

并删除/替换其他引用旧键（车辆伤害/锅炉爆炸/其他伤害/中毒和窒息）的断言为新键（厂（场）内车辆致害/容器爆炸/其他/中毒）。

### 第 2 步：运行测试确认失败

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_risk_notice_card_data.py tests/test_risk_notice_card_service.py -q
```

预期：FAIL（SIGN_GROUPS 缺新键、旧键失效）。

### 第 3 步：重写 `backend\app\services\risk_notice_card_data.py`

顶部改为：

```python
"""风险告知卡常量：GB 6441-2025 二十七类事故 → 安全标志组、应急处置模板。

标志图形完全符合 GB 2894-2025《安全色和安全标志》：
警告=黄底黑边正三角 / 禁止=白底红圈红斜杠 / 指令=蓝底白圆 / 提示=绿底白方。
"""

from app.services.accident_types import ACCIDENT_TYPES_2025
from app.services.risk_mapping_service import LEVEL_COLORS
```

删除本地 `GB6441_ACCIDENT_TYPES` 列表（改用 `ACCIDENT_TYPES_2025`）。`SIGN_CATEGORY_ORDER`、`W/P/I/N` 辅助函数保留。

`SIGN_GROUPS` 整体替换为以下内容（键全集 = 27 类；每类标志顺序 警告→禁止→指令→提示）：

```python
SIGN_GROUPS: dict[str, list[dict]] = {
    "物体打击": [W("当心坠落物", "warning-falling-object"), I("必须戴安全帽", "instruction-helmet")],
    "厂（场）内车辆致害": [W("当心车辆", "warning-vehicle"), P("禁止通行", "prohibition-pass")],
    "道路（轨道）车辆致害": [W("当心车辆", "warning-vehicle"), P("禁止通行", "prohibition-pass")],
    "机械致害": [W("当心机械伤人", "warning-machinery"), I("必须戴防护手套", "instruction-gloves")],
    "起重致害": [W("当心起重伤害", "warning-crane"), P("禁止站人", "prohibition-standing"), I("必须戴安全帽", "instruction-helmet")],
    "触电": [W("当心触电", "warning-electric"), P("禁止触摸", "prohibition-touch"),
             I("必须穿绝缘鞋", "instruction-insulating-shoes"), I("必须戴防护手套", "instruction-gloves"), N("紧急出口", "notice-exit")],
    "淹溺": [W("当心落水", "warning-drowning"), I("必须穿救生衣", "instruction-lifejacket")],
    "灼烫": [W("当心烫伤", "warning-burn"), I("必须穿防护服", "instruction-protective-suit"),
             I("必须戴防护手套", "instruction-gloves")],
    "火灾": [W("当心火灾", "warning-fire"), P("禁止烟火", "prohibition-smoking"),
             P("禁止动火作业", "prohibition-hot-work"), N("紧急出口", "notice-exit")],
    "高处坠落": [W("当心坠落", "warning-fall"), P("禁止抛物", "prohibition-throwing"), I("必须系安全带", "instruction-seatbelt")],
    "跌落": [W("当心坠落", "warning-fall"), P("禁止抛物", "prohibition-throwing")],
    "坍塌": [W("当心坍塌", "warning-collapse"), P("禁止通行", "prohibition-pass")],
    "水害": [W("当心透水", "warning-water-inrush"), I("必须穿救生衣", "instruction-lifejacket")],
    "容器爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static"), N("紧急出口", "notice-exit")],
    "管道爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static")],
    "可燃气体爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                      I("必须消除静电", "instruction-eliminate-static"), I("必须穿防静电工作服", "instruction-anti-static-clothes")],
    "可燃液体蒸气爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                          I("必须消除静电", "instruction-eliminate-static")],
    "粉尘爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static")],
    "民用爆炸物品爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                           P("禁止动火作业", "prohibition-hot-work"), I("必须消除静电", "instruction-eliminate-static")],
    "烟花爆竹爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                      P("禁止动火作业", "prohibition-hot-work")],
    "其他可燃固体爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                          I("必须消除静电", "instruction-eliminate-static")],
    "高温熔融物爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                        I("必须穿防护服", "instruction-protective-suit")],
    "中毒": [W("当心中毒", "warning-poison"), I("必须戴防毒面具", "instruction-gas-mask"),
             I("必须通风", "instruction-ventilate")],
    "窒息": [W("当心窒息", "warning-suffocation"), W("当心有限空间", "warning-confined-space"),
             I("必须通风", "instruction-ventilate")],
    "滑坡": [W("当心坍塌", "warning-collapse"), P("禁止通行", "prohibition-pass")],
    "泄漏": [W("当心中毒", "warning-poison"), I("必须戴防毒面具", "instruction-gas-mask"),
             I("必须通风", "instruction-ventilate")],
    "其他": [N("紧急出口", "notice-exit")],
}

DEFAULT_SIGN_GROUP = list(SIGN_GROUPS["其他"])

# 自定义/非标准事故类型的合理映射（补充 GB 6441-2025 27 类之外的常见表述）
EXTRA_SIGN_GROUPS: dict[str, list[dict]] = {
    "火灾爆炸": list(SIGN_GROUPS["火灾"]),
}
```

`EMERGENCY_TEMPLATES` 整体替换为以下内容（键全集 = 27 类，每类 ≥2 步）：

```python
EMERGENCY_TEMPLATES: dict[str, list[str]] = {
    "物体打击": ["立即停止作业，保护现场", "对伤员止血包扎，尽快送医", "拨打 120 急救电话", "报告企业安全管理部门"],
    "厂（场）内车辆致害": ["立即制动熄火，设置警戒", "现场急救伤员，拨打 120", "保护现场，配合事故调查"],
    "道路（轨道）车辆致害": ["立即制动停车，设置警戒", "现场急救伤员，拨打 120", "保护现场，配合事故调查"],
    "机械致害": ["立即停机断电", "对伤员止血包扎固定，拨打 120", "保护现场，禁止移动伤者"],
    "起重致害": ["立即停止起吊作业", "抢救伤员并拨打 120", "设置警戒区，保护现场"],
    "触电": ["立即切断电源或用绝缘物使伤员脱离电源", "判断意识与呼吸，必要时心肺复苏", "拨打 120，持续施救至医务人员到达"],
    "淹溺": ["立即将溺水者救出水面", "清理口鼻异物，判断呼吸，必要时心肺复苏", "拨打 120，注意保暖"],
    "灼烫": ["立即用大量清水冲洗创面 15 分钟以上", "小心脱除衣物，避免撕扯", "覆盖创面送医，拨打 120"],
    "火灾": ["立即切断气源、电源，停止作业", "拨打 119 报警并报告企业应急指挥部", "组织人员从上风向撤离，清点人数", "使用灭火器材初期扑救，禁止盲目进入"],
    "高处坠落": ["保持伤员静止，勿随意搬动", "固定伤者后平稳搬运", "拨打 120，保护现场"],
    "跌落": ["立即停止作业，保护现场", "检查伤员意识与伤情，勿随意搬动", "拨打 120 送医"],
    "坍塌": ["立即设置警戒，禁止无关人员进入", "防止二次坍塌，谨慎搜救", "拨打 119/120 请求专业救援"],
    "水害": ["立即沿避灾路线撤离，发出警报", "报告调度，清点人数", "在安全地点等待救援"],
    "容器爆炸": ["立即切断气源电源，撤离", "拨打 119/120 报警", "警戒隔离，配合专业处置"],
    "管道爆炸": ["立即切断气源电源，撤离现场", "拨打 119/120 报警", "警戒隔离，防止二次爆炸"],
    "可燃气体爆炸": ["立即切断电源，组织撤离", "拨打 119/120 报警", "严禁火源，通风排放，配合救援"],
    "可燃液体蒸气爆炸": ["立即切断火源电源，撤离现场", "拨打 119/120 报警", "严禁烟火，通风稀释，配合救援"],
    "粉尘爆炸": ["立即断电停机，撤离现场", "拨打 119/120 报警", "禁止扬尘扰动，防止二次爆炸"],
    "民用爆炸物品爆炸": ["立即切断电源与火源，撤离现场", "拨打 119/120 报警", "清点人数，配合专业救援"],
    "烟花爆竹爆炸": ["立即撤离现场，警戒隔离", "拨打 119/120 报警", "清点人数，配合专业救援"],
    "其他可燃固体爆炸": ["立即切断电源火源，撤离现场", "拨打 119/120 报警", "警戒隔离，防止复燃爆炸"],
    "高温熔融物爆炸": ["立即撤离危险区域，警戒隔离", "对灼烫伤员用清水冲洗创面", "拨打 119/120 报警"],
    "中毒": ["佩戴防护用品后进入，禁止盲目施救", "立即通风，将伤员移至新鲜空气处", "拨打 120，必要时心肺复苏", "报警并报告企业应急指挥部"],
    "窒息": ["佩戴防护用品后进入，禁止盲目施救", "立即通风，将伤员移至新鲜空气处", "拨打 120，必要时心肺复苏"],
    "滑坡": ["立即撤出危险区域，设置警戒", "在确保安全前提下搜救", "拨打 119/120 请求专业救援"],
    "泄漏": ["立即切断泄漏源，警戒隔离", "佩戴防护用品，通风稀释", "拨打 119/120 报警，报告企业应急指挥部"],
    "其他": ["立即停止作业，现场急救", "拨打 120 送医", "报告企业安全管理部门"],
}
```

保留文件尾部的 `LEVEL_ORDER`。

### 第 4 步：更新 `backend\app\services\risk_notice_card_service.py` 的 `match_signs`

在 `match_signs` 函数（约 :123）开头加旧值兼容：

```python
def match_signs(accident_types: list[str]) -> list[dict]:
    """按 SIGN_GROUPS 合并去重；旧值经 normalize_accident_type 映射；按 警告→禁止→指令→提示 排序，每类最多 2 个。"""
    from app.services.accident_types import normalize_accident_type

    groups: list[dict] = []
    for at in accident_types:
        key = normalize_accident_type(at)
        group = EXTRA_SIGN_GROUPS.get(key) or SIGN_GROUPS.get(key, DEFAULT_SIGN_GROUP)
        groups.extend(group)
    # 以下去重/排序/限量逻辑保持原样（normalize_signs 等既有实现）
    ...
```

保留原函数后续的去重、排序、限量逻辑不动，只改查表入口。

### 第 5 步：运行测试确认通过（绿灯）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_risk_notice_card_data.py tests/test_risk_notice_card_service.py tests/test_risk_notice_card_api.py -q
```

预期：全部 PASS。

### 第 6 步：全量回归 + 提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest -q
```

若全量有失败，先修复（只允许修本任务相关文件）；全绿后提交：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/services/risk_notice_card_data.py backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_data.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(accident-types): rebuild risk notice card groups for GB 6441-2025"
```

### 红线

- 只改动上述 4 个文件（如需修其他测试文件以适配新键，允许且必须，但要说明）
- 不要做状态汇报或计划总结，直接执行
- 中文内容保持 UTF-8 编码，不得使用转义
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 红灯输出摘要（一行）+ 绿灯结果（目标测试 + 全量 pytest 数字）
- 修改了哪些文件（含额外适配的测试文件）
- commit SHA（git log -1 --format=%h）
