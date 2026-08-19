# Codex Custom Subagents task handoff v1

Task: task_hazard_14_review_spec

## 目标

对隐患任务 14「HazardPlanPage+HazardTaskPage」提交 `b572a59`（父 `cfd2cbd`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`b572a59`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §6、§15）。

## 审查清单（逐项核验并给出证据）

1. **HazardPlanPage**：计划列表（名称/类别/频次含星期/责任人/分区数/启用 Switch/编辑/软删）；新建/编辑 Modal 字段（name/category/frequency/weekdays weekly/custom/zone_ids 多选/template_id/responsible_user_id/enabled）与 POST/PUT /plans 契约一致；责任人选择器数据源（listMembers 过滤 enabled、值传 user_id——与后端 _validate_responsible 按 EnterpriseMember.user_id 校验一致）；分区数据源（listZones）；AI 排程建议卡（调 /ai/schedule-suggestion、采纳回填、降级不阻塞）。
2. **HazardTaskPage**：任务列表筛选（责任人/状态/超期）、超期标红（status=overdue 或 pending/processing 且 due_at<now）；详情 items 逐项核对（result/remark/photo_urls）；PUT /tasks/{id} 提交（部分→processing、全部→done 由后端判定）；一键转隐患（仅 abnormal 项、先提交核对后转、预填 title/description/photo_urls、成功后刷新）；任务 done 后清单只读。
3. **路由**：plans/tasks 占位替换为真实页面；其余占位保留；无路由冲突。
4. **门禁**：前端 tsc/eslint/vitest 109 passed；后端全量 952 passed（本批不改后端）。
5. **无越界**：`git show b572a59 --stat` 恰 3 个清单文件（pages/Hazard/HazardPlanPage.tsx、pages/Hazard/HazardTaskPage.tsx、routes/index.tsx），消息精确匹配「feat(hazard): plan and task execution pages」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check b572a59`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_14_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患计划任务页规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
