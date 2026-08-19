# Codex Custom Subagents task handoff v1

Task: task_hazard_07_review_spec

## 目标

对隐患任务 7「整改/复查/销号端点」提交 `8e69550`（父 `079a5f0`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`8e69550`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.5-5.8、§10、§14、§16）。

## 审查清单（逐项核验并给出证据）

1. **rectify 端点**：`POST /records/{rid}/rectify`——content 必填、evidence 可选、reviewer_user_id 必填且 ≠ 整改人（422）、校验 enabled 成员；执行=整改人本人或企业主/启用 admin（其余 422/403 分层）；接线 apply_transition（状态机写 HazardRectification + 设置复查人 + 状态→reviewing）；复查期限提醒（rectify 成功后按 deadline_rules.review 天数创建 review_due 通知给复查人，含「请于 YYYY-MM-DD 前完成复查」文案 + record_id，响应含 review_deadline；字典缺天数时不创建说明）。
2. **review 端点**：`POST /records/{rid}/review`——result pass/fail 必填、comment/evidence 可选；执行=指定复查人或企业主/启用 admin；接线 apply_transition（standard 一般 pass 停留 reviewing、strict+重大 pass→second_review、second_review pass 停留、fail→rectifying）；非指定复查人 422。
3. **close 端点**：`POST /records/{rid}/close`——仅企业主/启用 admin（403）；状态非 reviewing/second_review 409；strict+重大未 second_review 拦截；接线 apply_transition（review_type=close + closed_at + audit log）。
4. **actor_role 映射**：整改人→rectifier、复查人→reviewer、企业主/启用 admin→enterprise_admin（_map_actor_role 实现与 ROLE_GATE 一致）。
5. **测试有效性**：27 个测试断言有效无空断言；覆盖全路径 API 级、权限 403、退回、二次复核、销号留痕。
6. **无越界**：`git show 8e69550 --stat` 恰 2 个清单文件（routers/hazard_management.py、tests/test_hazard_review_api.py），消息精确匹配「feat(hazard): rectify, review and close endpoints wired to state machine」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_review_api.py -v`（预期 27 passed）
- `python -m pytest tests/ -q`（预期 836 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 8e69550`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_07_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患整改/复查/销号规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
