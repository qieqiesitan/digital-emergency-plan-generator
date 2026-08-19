# Codex Custom Subagents task handoff v1

Task: task_hazard_15_review_spec

## 目标

对隐患任务 15「HazardRecordDetailPage」提交 `1100018`（父 `b572a59`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`1100018`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §9、§10、§15）。

## 审查清单（逐项核验并给出证据）

1. **详情数据展示**：GET /records/{rid} 全字段 + 名称 + 时间线（四路合并 created_at 升序）+ 治理方案卡（未填「未填写」）；404/403 extractDetail 提示 + Result 重试/返回。
2. **按钮可见性矩阵**：canShowAction 与状态机 TRANSITIONS/ROLE_GATE 对齐——grade=registered/grading+管理员、approve/reject=pending_approval+管理员、rectify=rectifying+整改人（或管理员）、review=reviewing/second_review+复查人（或管理员）、close=reviewing/second_review+管理员；身份推断（企业主=成员列表缺失、启用 admin 判定）正确；members 未加载完不渲染按钮。
3. **各操作 Modal 契约**：grade（level/grading_basis/hazard_type/rectification_user_id/rectification_plan 重大必填五键+deadline 由后端算）、approve/reject（comment/rectification_user_id）、rectify（content/evidence/reviewer_user_id ≠ 整改人）、review（result pass/fail/comment/evidence、second_review 文案二次复核）、close（Popconfirm）——body 与后端契约一致；操作成功 refetch+invalidate。
4. **AI 预填**：/ai/grade 预填 level+grading_basis+置信度、level_source 按沿用与否记 ai/manual；/ai/governance-plan 回填五键；降级不阻塞。
5. **时间线文案**：action 中文映射（分级确认/挂牌通过/驳回/提交整改/复查判定/销号）、review_type 区分、pass/fail 着色、audit 附操作人+from→to。
6. **门禁**：tsc -b/eslint/vitest 109/后端 952 全绿；git show --check 干净。
7. **无越界**：`git show 1100018 --stat` 恰 2 个清单文件（pages/Hazard/HazardRecordDetailPage.tsx、routes/index.tsx），消息精确匹配「feat(hazard): record detail with state machine actions」，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 1100018`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_15_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患记录详情页规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
