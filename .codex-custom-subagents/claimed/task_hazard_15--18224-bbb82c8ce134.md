# Codex Custom Subagents task handoff v1

Task: task_hazard_15

## 目标

实现隐患管理任务 15「HazardRecordDetailPage（时间线 + 状态机按钮按角色显示 + 治理方案表单 + 重大审批 Modal）」并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`b572a59`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：新建 `frontend/src/pages/Hazard/HazardRecordDetailPage.tsx`，修改 `frontend/src/routes/index.tsx`（records/:rid 占位替换为真实页面），按需扩展 `frontend/src/services/hazardService.ts`/`frontend/src/types/hazard.ts`（任务 13 已封装 records 端点，通常无需改，缺则补）。

**1. 详情页（规格 §15 + 任务 5-7/13 后端）**

- 数据：GET /records/{rid}（全部字段 + object/measure 名称 + rectifications/reviews/approvals/audit_logs 时间线 + 中文标签）。
- 展示：基本信息（code/title/description/level/status/source_type/hazard_type/location/photo_urls/deadline/rectification_user/reviewer_user/created_by/created_at/closed_at）、治理方案（rectification_plan 五键，重大未填时显示「未填写」）、时间线（audit_logs + rectifications/reviews/approvals 合并按 created_at 升序渲染，动作中文文案映射）。
- 404/403 提示（extractDetail 惯例）；加载态。

**2. 状态机操作（按角色/状态显示按钮）**

- 分级：status=registered 或 grading 且当前用户为企业主/启用管理员 → 「分级确认」按钮/Modal（level/grading_basis/hazard_type/rectification_user_id/rectification_plan 五键表单，重大必填；调 POST /records/{rid}/grade；可带 AI 分级建议按钮调 /ai/grade 预填）。
- 挂牌审批：status=pending_approval 且企业主/启用管理员 → 「审批通过」/「驳回」按钮（approve/reject Modal 含 comment + rectification_user_id 可选）。
- 整改：status=rectifying 且当前用户=整改责任人（或企业主/管理员）→ 「提交整改」Modal（content/evidence 照片/reviewer_user_id 选择 ≠ 整改人；调 POST /records/{rid}/rectify）。
- 复查：status=reviewing 或 second_review 且当前用户=复查人（或企业主/管理员）→ 「复查」Modal（result pass/fail/comment/evidence；调 POST /records/{rid}/review）；second_review 时文案「二次复核」。
- 销号：status=reviewing 或 second_review 且企业主/启用管理员 → 「销号」按钮（confirm → POST /records/{rid}/close）。
- 按钮显示逻辑集中一个 helper（按 status + 当前角色/身份 + 记录字段判定），报告实现；操作成功刷新详情 + invalidate 台账。

**3. 门禁**：`npx tsc -b` exit 0；eslint 改动文件 exit 0；`npx vitest run` 全绿（若扩展 service 补测试）；`git diff --check` 干净；后端全量 `python -m pytest tests/ -q` 无回归。

**4. 参考文件**（自行阅读）

- 后端端点与契约：`backend/app/routers/hazard_management.py`（GET /records/{rid}、grade/approve/reject/rectify/review/close 的 body 与权限）。
- 状态机语义：`backend/app/services/hazard_state_machine.py`（动作/角色/状态流转，前端按钮可见性需对齐）。
- 前端先例：`frontend/src/pages/Hazard/HazardInspectionTab.tsx`、`HazardPlanPage.tsx`（风格）；`frontend/src/types/hazard.ts`（类型）。
- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §9、§10、§15。

## Commit

```bash
git add frontend/src/pages/Hazard/HazardRecordDetailPage.tsx frontend/src/routes/index.tsx frontend/src/services/hazardService.ts frontend/src/types/hazard.ts
git commit -m "feat(hazard): record detail with state machine actions"
```

按实际改动文件调整 add 列表；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_15 --claim-id <claim_id> --exit-code 0 --summary "隐患记录详情页实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、门禁结果、设计决策说明（按钮可见性矩阵/时间线文案/治理方案表单/AI 预填）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
