# Codex Custom Subagents task handoff v1

Task: task_05_fix3

## 目标

修复任务 5 代码质量审查发现的 1 条必须修复 + 4 条建议修改，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`6659077`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**必须修复 1：DIRECT 固有等级显式清空被吞（`frontend/src/pages/Enterprise/RiskManagementTab.tsx` 约 300-303 行）**

`values.inherent_risk_level ?? undefined` 会把用户显式清空的 `null` 也转成 `undefined` 导致清空不生效。改为直接透传：

```typescript
inherent_risk_level: values.inherent_risk_level,          // null 发送清空，undefined 序列化省略
inherent_risk_score: values.inherent_risk_score,
risk_level: values.risk_level,
risk_score: values.risk_score,
```

（同步去掉 `?? undefined`；`method_type`/`method_params` 保持现有 truthy 条件展开。）

**建议修改 2：create 两路径重复的「当前等级解析」提取（`backend/app/routers/risk_management.py`）**

提取辅助函数并让 create_event/create_object_event 复用（行为不变）：

```python
def _resolve_current_level(body, config) -> tuple[str, str]:
    """显式 risk_level 优先；否则按 method_params 计算。返回 (level, score)。"""
    if body.risk_level:
        return body.risk_level, body.risk_score or "-"
    rating = compute_risk(body.method_type, body.method_params, config)
    return rating.risk_level, rating.risk_score
```

（update 路径可保持现状或同样复用，以不改变已通过测试为准。）

**建议修改 3：factor_map 构造加 value 类型防御（`backend/app/routers/risk_management.py` 折算端点）**

```python
    factor_map: dict[str, float] = {}
    for code, entry in factors.items():
        if code == "mode":
            continue
        value = entry.get("value") if isinstance(entry, dict) else None
        factor = value.get("factor") if isinstance(value, dict) else None
        if isinstance(factor, (int, float)):
            factor_map[code] = float(factor)
```

mode 同样防御：`mode_entry = factors.get("mode"); mode_value = mode_entry.get("value") if isinstance(mode_entry, dict) else None; mode = mode_value.get("mode", "min") if isinstance(mode_value, dict) else "min"`。

**建议修改 4：显式 risk_level 等级枚举校验（`backend/app/schemas/risk_management.py`）**

给 `RiskEventCreate`/`RiskEventUpdate` 的 `risk_level` 与 `inherent_risk_level` 加 `field_validator`：值非空时必须属于 `{"重大", "较大", "一般", "低"}`，否则 `ValueError("风险等级必须是 重大/较大/一般/低")`。`control_level` 同理限定 `{"企业", "部门", "班组", "岗位"}`（可选值校验，空值放行）。补 1-2 个 schema 测试。

**建议修改 5：前端 payload 构建抽纯函数 + 单测（`frontend`）**

- 新建 `frontend/src/utils/eventPayload.ts`：导出纯函数 `buildEventPayload(values, opts)`，把 `RiskEventForm.handleFinish` 的 payload 构建逻辑迁移过来（新建/编辑、方法未改动省略、DIRECT 特殊处理、折算采用携带 risk_level/risk_score、固有显式 null 透传等全部覆盖）；`RiskEventForm.tsx` 改为调用该函数（可保留表单内少量组装）；
- 新建 `frontend/src/utils/eventPayload.test.ts`，用 vitest 覆盖：①新建 LS 携带 method_params 小写键；②编辑未改动省略 method_type/method_params/risk_level/inherent_*；③DIRECT 未改动省略 method_params；④采用折算携带 risk_level/risk_score；⑤DIRECT 固有显式 null 透传（不清空场景不含该键）；
- 参考先例：`frontend/src/utils/zoneSubmit.ts` 及其测试。

## 验证

- 后端：`python -m pytest tests/test_risk_dual_level.py tests/test_risk_conversion_api.py tests/test_risk_conversion.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；
- 前端：`npx tsc -b`、eslint（改动文件）、`npx vitest run` 全部通过（新增 eventPayload 单测）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/routers/risk_management.py backend/app/schemas/risk_management.py backend/tests/test_risk_dual_level.py frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/utils/eventPayload.ts frontend/src/utils/eventPayload.test.ts frontend/src/components/enterprise/RiskEventForm.tsx
git commit -m "fix(risk): direct clear passthrough, level enum, payload util and dedupe helpers"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_05_fix3 --claim-id <claim_id> --exit-code 0 --summary "任务5第三轮质量修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复清单逐项说明。

## 规则

- 用 `apply_patch` 编辑；只改列出的文件（如抽函数需要新建测试文件，允许新增并说明）；阻塞时停下汇报。
