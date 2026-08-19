# Codex Custom Subagents task handoff v1

Task: task_hazard_02_review_spec

## 目标

对「隐患排查治理」计划任务 2 的实现做**只读规格合规审查**（对照 B 规格 §5.13 状态机/§6-§10 流程与任务 2 契约），输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`4af71a0`（父 `eae50b4`）
- 文件：`backend/app/services/hazard_state_machine.py`、`backend/tests/test_hazard_state_machine.py`、`backend/app/models/enterprise.py`
- 规格：B 规格 §5.13（状态机）、§6-§10（计划/登记/分级/整改/复查/销号）、§5.10（企业配置）

## 审查要点

1. 状态机：TRANSITIONS/ROLE_GATE 与规格 §5.13 一致（一般/重大 × 标准/严格 × pass/fail、退回、二次复核、close）；worker 对契约「rectifying:{"review"}」等动作名错位的修正是否与规格一致；
2. `can_transition`：非法动作/角色/复查人=整改人 422/严格+重大 close 前 second_review；
3. `apply_transition`：grade（重大治理方案必填校验在哪一层？）、approve/reject 语义（reject→grading 的合理性）、rectify/review/close 字段更新、audit log 写入；
4. Enterprise 4 列补充与迁移一致；
5. 测试 44 条覆盖矩阵；
6. 无越界改动。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_02_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患任务2规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
