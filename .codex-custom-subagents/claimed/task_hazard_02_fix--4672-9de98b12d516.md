# Codex Custom Subagents task handoff v1

Task: task_hazard_02_fix

## 目标

按隐患任务 2 规格审查的 1 条必须修复 + 4 条建议修改修复状态机，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`4af71a0`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1（必须）：`pending_approval` 不允许 rectify**

`TRANSITIONS["pending_approval"] = set()`；`apply_transition` 的 rectify 分支在 pending_approval 下返回 409（can_transition 拦截）。补测试：pending_approval 下 rectify → (False, ...)。

**2（建议）：grading 允许集只保留 grade**

`TRANSITIONS["grading"] = {"grade"}`（移除 rectify）；补测试：grading 下 rectify → 409、grade → 通过。

**3（建议）：reject → grading 后可通过 grade 重新定级**

`grading` 允许集含 grade（与 2 合并）；`apply_transition` 的 grade 分支在 grading 状态同样生效（更新 level/grading_basis/rectification_plan/deadline，重新决定 一般→rectifying / 重大→pending_approval）。补测试：reject 后 grade 重新定级。

**4（建议）：销号语义统一为管理员 close**

按规格 §10/§3.5「销号 = 管理员确认（review_type=close）」统一：`review` pass **不再直接 closed**——标准模式 review pass 后 record 留在 `reviewing`（写入 first_review pass 记录）；严格+重大 review pass → `second_review`；second_review pass → 留在 `second_review`；`close` 动作（仅 enterprise_admin）从 reviewing/second_review → closed（写 review_type=close 记录 + closed_at）。同步更新测试矩阵（原「pass 即 close」用例改为「pass 停留 + close 销号」）。

**5（建议）：rectify 校验整改人本人**

`grade`/`approve` 时设置 `rectification_user_id`（payload 指定整改责任人）；`rectify` 时校验 actor == rectification_user_id（enterprise_admin 例外），与 review 身份校验对称。补测试：非整改人 rectify → 403/拒绝。

**参考项**：严格模式 close 拦截 409→422 语义、audit 中文 action、token 索引 ORM 声明、deadline 时区——按可实现性处理：token 索引补 ORM `__table_args__`（与 public_risk_token 一致）；其余记录为债务不阻塞。

## 验证

- `python -m pytest tests/test_hazard_state_machine.py -v` 全部 PASS（含更新后矩阵）；`python -m pytest tests/ -q` 无回归；`git diff --check` 干净。

## Commit

```bash
git add backend/app/services/hazard_state_machine.py backend/tests/test_hazard_state_machine.py backend/app/models/enterprise.py
git commit -m "fix(hazard): enforce approval gate and admin close semantics in state machine"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_02_fix --claim-id <claim_id> --exit-code 0 --summary "隐患状态机审批门+销号语义修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明（含语义变更对照）。

## 规则

- 用 `apply_patch` 编辑；只改列出的 3 个文件；阻塞时停下汇报。
