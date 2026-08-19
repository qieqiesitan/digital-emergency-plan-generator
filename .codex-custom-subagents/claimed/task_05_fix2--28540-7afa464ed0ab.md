# Codex Custom Subagents task handoff v1

Task: task_05_fix2

## 目标

修复任务 5 规格复审发现的剩余必须修复：编辑模式「未改动保存」仍会覆盖/清空已存等级数据（提交层兜底空参数/null + 后端无条件重算 + DIRECT 未改动路径）。提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`26d49e8`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景（复审证据链）

- `RiskManagementTab.tsx` 提交层把未注册字段兜底为 `method_params: values.method_params || {}`、`inherent_risk_level: values.inherent_risk_level ?? null`，导致 LS/LEC 未改动保存实际发送 `{}` 与 `null`；
- `update_event` 先 setattr 落库，再因 `method_type` 恒存在用空参数重算 → 覆盖已存等级；
- DIRECT 未改动路径保留 `{level: 4}`，后端 DIRECT 读 `params.get("risk_level", "一般")` → 覆盖为「一般」。

## 修复清单

**1. `frontend/src/pages/Enterprise/RiskManagementTab.tsx`（提交层）**

- `method_params`：仅当表单显式提供时携带（去掉 `|| {}` 兜底；未提供则省略，不放入 payload）；
- `method_type`：参数未改动时不携带（与 method_params 一致，未改动则都省略）；
- `inherent_risk_level` / `inherent_risk_score`：仅当表单显式提供时携带（用 `?? undefined` 而非 `?? null`，序列化时省略）；
- `risk_level` / `risk_score`：仅当表单采用折算参考时携带（保持现行为）；
- 确认「未改动」判定与表单 `paramsUnchanged` 一致（表单与提交层需统一口径：表单负责判定并告知提交层哪些字段省略，或提交层按 values 是否有值决定）。

**2. `frontend/src/components/enterprise/RiskEventForm.tsx`**

- DIRECT：参数未改动时不提交 `method_params`（保持已存）；改动时才提交 `{risk_level: 等级}`；
- LS/LEC/COAL_LS：参数未改动时不提交 `method_params` 与 `method_type`（已实现部分，确认 method_type 也省略）；
- 采用折算参考时照常携带 `risk_level/risk_score`。

**3. `backend/app/routers/risk_management.py`（update_event 重算守卫）**

- 重算条件改为：`body.risk_level is None and (body.method_type is not None or body.method_params is not None)`——两者都未提供（未改动保存）时不重算、不覆盖已存 risk_level/risk_score/inherent_*；
- setattr 循环保持 `exclude_unset`（未提供字段不落库）；
- 保持既有「显式 risk_level 覆盖」「method_type/method_params 变更重算」「validate_dual_level 无条件校验」行为不变。

**4. 后端回归测试（`backend/tests/test_risk_dual_level.py` 追加）**

- 路由级用例 1：`PUT /events/{id}` 载荷仅含 `accident_type`/`description`（不含 method_type/method_params/risk_level/risk_score/inherent_*/control_level）→ 断言已存 `risk_level`/`inherent_risk_level`/`method_params` 不变（mock 事件带已存值，update 后未重算、未置空）；
- 路由级用例 2：同上但事件为 DIRECT（已存 `risk_level="重大"`、`method_params={"risk_level": "重大"}`）→ 未改动保存后等级保持「重大」。

## 验证

- 后端：`python -m pytest tests/test_risk_dual_level.py tests/test_risk_conversion_api.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；
- 前端：`npx tsc -b`、eslint（改动文件）、`npx vitest run` 全部通过；
- `git diff --check` 干净。

## Commit

```bash
git add frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/components/enterprise/RiskEventForm.tsx backend/app/routers/risk_management.py backend/tests/test_risk_dual_level.py
git commit -m "fix(risk): no-overwrite save omits unchanged params and skips recompute"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_05_fix2 --claim-id <claim_id> --exit-code 0 --summary "任务5未改动保存不覆盖修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明。

## 规则

- 用 `apply_patch` 编辑；只改列出的 4 个文件；阻塞时停下汇报。
