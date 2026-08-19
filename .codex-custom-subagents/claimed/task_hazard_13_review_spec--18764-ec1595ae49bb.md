# Codex Custom Subagents task handoff v1

Task: task_hazard_13_review_spec

## 目标

对隐患任务 13「HazardInspectionTab+hazardService」两个提交（`60e12e6` 后端列表/详情、`cfd2cbd` 前端）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`cfd2cbd`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §14、§15、§16）。

## 审查清单（逐项核验并给出证据）

1. **后端列表**：`GET /records`——筛选（status/level/source_type/scope=overdue/关键词 q ilike title/description/code）；created_at 倒序；items+stats（total/open/major/overdue 企业全量口径，stats=false 跳过）；读=归属 404；状态/来源/等级中文标签（level 字典优先+内置 major→重大/general→一般 兜底）。
2. **后端详情**：`GET /records/{rid}`——全部业务字段 + object/measure 名称 + rectifications/reviews/approvals/audit_logs 时间线（created_at 升序）；读=归属 404。
3. **前端 service/类型**：hazardService.ts 封装端点与后端一致（URL/方法/解包）；types/hazard.ts 字段与后端响应一致；hazardService.test.ts 12 用例断言有效。
4. **HazardInspectionTab**：台账页——统计条（dashboard metrics）、筛选、新建 Modal（POST /records 字段 + AI record-assist 预填不落库）、导出按钮（axios blob）、各页入口；EnterpriseDetailPage 接入新 Tab。
5. **路由**：6 企业内占位路由 + /h/:token、/h/report/:token 公开占位；与任务 14-16 页面规划一致。
6. **门禁**：后端全量 952 passed；前端 tsc -b/eslint/vitest 109 passed；git show --check 两提交干净。
7. **无越界**：`git show 60e12e6 --stat` 恰 2 文件（routers/hazard_management.py、tests/test_hazard_record_api.py）、`git show cfd2cbd --stat` 恰 7 文件（前端），消息精确匹配「feat(hazard): record list and detail endpoints」「feat(hazard): inspection tab and hazard service」，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_record_api.py -v`（预期 44 passed）
- `python -m pytest tests/ -q`（预期 952 passed，Event loop ResourceWarning 为既有非失败噪音）
- `npx tsc -b` exit 0、`npx vitest run` 全绿
- `git show --check 60e12e6`、`git show --check cfd2cbd`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_13_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患台账Tab规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
