# Codex Custom Subagents task handoff v1

Task: accident_types_backend

## 任务：后端事故类型共享模块（GB 6441-2025，TDD）

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

这是隔离 git 分支 `codex/accident-types-2025` 的工作区。命令在 PowerShell 中执行；测试在 `backend` 子目录执行（先 `cd backend`）。

### 背景

数字化应急预案系统。本次把全系统事故类型统一到强制性国标 GB 6441-2025（27 类）。本任务建立后端唯一事实源模块，后续任务会 import 它。接口必须与下方代码完全一致。

### 第 1 步：创建测试文件（红灯）

创建文件：`backend\tests\test_accident_types.py`，内容如下（完整粘贴，UTF-8）：

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

### 第 2 步：运行测试确认失败（必须亲眼看到失败）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_accident_types.py -v
```

预期：`ModuleNotFoundError: No module named 'app.services.accident_types'`。

### 第 3 步：创建实现文件（绿灯）

创建文件：`backend\app\services\accident_types.py`，内容如下（完整粘贴，UTF-8）：

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

### 第 4 步：运行测试确认通过（必须亲眼看到 PASS）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_accident_types.py -v
```

预期：4 passed。

### 第 5 步：提交（在 worktree 根目录）

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/services/accident_types.py backend/tests/test_accident_types.py
git commit -m "feat(accident-types): add shared GB 6441-2025 module with legacy mapping"
```

### 红线

- 只创建上述两个文件，禁止改动任何其他文件（包括 TASKS.md）
- 不要做状态汇报或计划总结，直接执行
- 中文文件内容保持 UTF-8 编码，不得使用转义
- 遇到意外情况（测试环境缺失、命令报错）先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 红灯输出摘要（一行）+ 绿灯结果（4 passed）
- commit SHA（git log -1 --format=%h）
- 确认 git status 只含本次两个文件（或干净）
