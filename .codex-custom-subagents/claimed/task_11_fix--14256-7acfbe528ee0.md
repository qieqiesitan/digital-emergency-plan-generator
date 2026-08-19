# Codex Custom Subagents task handoff v1

Task: task_11_fix

## 目标

按任务 11 规格审查的 2 条建议修改修复，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`720d575`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1（建议）：prompt 与采用路径补原始参数**

- `backend/app/services/risk_dual_ai_service.py`：prompt 输出格式增加固有/现有各自的原始参数（LS/COAL_LS 为 `l/s`，LEC 为 `l/e/c`；DIRECT 为 `risk_level` 文案）：

```json
{"inherent": {"risk_level": "重大", "risk_score": "D=270", "params": {"l": 3, "e": 6, "c": 15}},
 "current": {"risk_level": "一般", "risk_score": "D=21", "params": {"l": 1, "e": 3, "c": 7}},
 "note": "调参理由"}
```

- 服务保留 `params`（缺省 `{}`）并随结果返回；测试更新（fake 增加 params，断言透传）。
- `frontend/src/components/enterprise/RiskEventForm.tsx`：`handleAdoptDual` 在建议含 `params` 时填入对应参数输入（固有参数组 + 现有参数组；DIRECT 填等级 Select）；无 params 时保持现状。

**2（建议）：DIRECT 固有采用覆盖一致性**

- `handleAdoptDual`：采用 AI 建议时，DIRECT 的 `payload.inherent_risk_level` 无条件取建议值（覆盖既有），并携带 `inherent_risk_score`（建议分值或 "-"）；LS/LEC/COAL_LS 同样在采用时以建议固有等级/分值透传（改固有参数计算值优先的现有逻辑保留）。
- 前端补 service/payload 相关单测（eventPayload 或新用例）覆盖「采用时固有等级/分值显式携带」。

## 验证

- 后端：`python -m pytest tests/test_risk_dual_level.py tests/test_risk_conversion_api.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；
- 前端：`npx tsc -b`、eslint（改动文件）、`npx vitest run` 全部通过；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/services/risk_dual_ai_service.py backend/tests/test_risk_dual_level.py frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/utils/eventPayload.ts frontend/src/utils/eventPayload.test.ts
git commit -m "feat(risk): AI suggestion params and consistent inherent adoption"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_11_fix --claim-id <claim_id> --exit-code 0 --summary "任务11 AI参数建议+固有采用修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明。

## 规则

- 用 `apply_patch` 编辑；只改上述文件（如需额外文件请说明理由）；阻塞时停下汇报。
