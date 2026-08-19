# Codex Custom Subagents task handoff v1

Task: task_hazard_02_review_spec2

## 目标

对隐患任务 2 状态机修复提交 `16b3656`（父 `4af71a0`）做只读规格合规复审，核对修复是否全部落地且与 B 规格一致，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`16b3656`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §3.5、§5.13、§10）。

## 审查清单（逐项核验并给出证据）

1. **必须项**：`TRANSITIONS["pending_approval"] = set()`，rectify 经 can_transition 拦截返回 409，重大隐患无法绕过挂牌审批门；有对应测试。
2. **grading 允许集**：`TRANSITIONS["grading"] = {"grade"}`（rectify 已移除）；grading 下 rectify → 409、grade → 通过，均有测试。
3. **reject 后重新定级**：grade 动作在 grading 状态生效——更新 level/grading_basis/rectification_plan/deadline，一般→rectifying / 重大→pending_approval；有 reject 后一般/重大重定级测试。
4. **销号语义统一**：review pass 不再直接 closed——标准/一般 pass 停留 reviewing（写 first_review 记录）；严格+重大 pass→second_review；second_review pass 停留；close（仅 enterprise_admin）从 reviewing/second_review→closed（写 review_type=close + closed_at）；测试矩阵同步更新（原「pass 即 close」用例改为「pass 停留 + close 销号」）。
5. **整改人本人校验**：grade/approve 设置 rectification_user_id（来自 payload）；rectify 校验 actor==整改人（enterprise_admin 例外），与 review 身份校验对称；有非整改人 rectify 拒绝、admin 例外、grade/approve 设整改人测试。
6. **ORM token 索引**：enterprise.py 已补 `uq_enterprises_hazard_public_token`/`uq_enterprises_hazard_report_token` 部分唯一索引（与 public_risk_token 一致，迁移层已有）。
7. **规格一致性**：修复后状态机行为与 B 规格 §5.13 图、§10 销号定义、§3.5 企业管理员=销号一致。
8. **测试有效性**：目标测试 56 个断言有效无空断言；矩阵/边界/权限均有真实断言。
9. **无越界**：`git show 16b3656 --stat` 恰 3 个清单文件（backend/app/services/hazard_state_machine.py、backend/tests/test_hazard_state_machine.py、backend/app/models/enterprise.py），消息精确匹配「fix(hazard): enforce approval gate and admin close semantics in state machine」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_state_machine.py -v`（预期 56 passed）
- `python -m pytest tests/ -q`（预期 635 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 16b3656`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_02_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "隐患状态机修复规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
