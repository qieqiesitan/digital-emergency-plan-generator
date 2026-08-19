# Codex Custom Subagents task handoff v1

Task: task_hazard_06_review_spec

## 目标

对隐患任务 6「分级/治理方案/挂牌审批」提交 `079a5f0`（父 `e924dd3`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`079a5f0`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.4、§9、§14、§16、§5.13 状态机）。

## 审查清单（逐项核验并给出证据）

1. **grade 端点**：`POST /records/{rid}/grade`——level major/general 校验、重大缺 grading_basis/治理方案五键 422（状态机抛）、rectification_user_id 校验 enabled 成员、deadline_rules 从数据字典读取后按 major/general 天数计算 deadline（状态机内部）、level_source 落库；一般→rectifying、重大→pending_approval；权限=企业主/启用 enterprise_admin（403）；读=归属 404；接线 apply_transition 正确。
2. **AI grade**：`POST /ai/grade`——description 必填、judgment_points 可选（内置 JUDGMENT_POINTS 常量 fallback，来源标注「参考提示，以现行有效判定标准为准」）、suggested_level=major/general 码值、basis/confidence；失败/未配置/非法返回 → available:false（200）。
3. **approve/reject**：`POST /records/{rid}/approve`——仅 pending_approval（409）、仅企业主/启用 enterprise_admin（403）、写 HazardApproval+audit（状态机）、状态→rectifying；reject 实现（若含）→ grading，语义与状态机一致。
4. **AI governance-plan**：`POST /ai/governance-plan`——description 必填、返回五键 plan、失败降级 available:false、不落库。
5. **actor_role 映射**：企业主映射为 enterprise_admin 传给状态机（报告说明）；与 ROLE_GATE 一致。
6. **测试有效性**：43 个测试断言有效无空断言；覆盖 grade 成功两分支/校验失败/权限/404/deadline 计算/level_source、AI 成功与降级、approve/reject 语义。
7. **无越界**：`git show 079a5f0 --stat` 恰 3 个清单文件（routers/hazard_management.py、services/hazard_ai_service.py、tests/test_hazard_grade_api.py），消息精确匹配「feat(hazard): grading, governance plan and major hazard approval」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_grade_api.py -v`（预期 43 passed）
- `python -m pytest tests/ -q`（预期 809 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 079a5f0`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_06_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患分级/审批规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
