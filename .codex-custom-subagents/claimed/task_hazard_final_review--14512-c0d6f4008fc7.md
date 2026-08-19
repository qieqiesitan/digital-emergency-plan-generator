# Codex Custom Subagents task handoff v1

Task: task_hazard_final_review

## 目标

对隐患管理完整批次（分支 `codex/dual-prevention`，hazard 20 commit `076e4f9`→`c8dff5b`）做最终整体审查：对照计划文档 17 个任务逐项验证完成度与一致性，输出整体审查报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`c8dff5b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 计划文档：`C:\Users\55061\Documents\数字化预案自动生成 2\docs\superpowers\plans\2026-08-15-hazard-management.md`。
- 规格文档：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention\docs\superpowers\specs\2026-08-14-hazard-management-design.md`。

## 审查清单（逐项核验并给出证据）

1. **计划任务 1-17 逐项核对**：对照计划文档每个任务的「文件/功能/commit 消息」，用代码与 git 证据验证：
   - 任务 1 迁移+模型（10 表+企业配置+B 字典种子+5 系统模板）→ commit 076e4f9/eae50b4
   - 任务 2 状态机 → 4af71a0/16b3656
   - 任务 3 计划/任务/清单项端点 → 5af505b/96e2c71
   - 任务 4 检查表模板+AI → b1bc6b2
   - 任务 5 隐患登记三渠道+AI 摘要 → e924dd3
   - 任务 6 分级/治理方案/挂牌审批 → 079a5f0
   - 任务 7 整改/复查/销号端点 → 8e69550
   - 任务 8 APScheduler → 3225ed2
   - 任务 9 派生联动+四色图 → 25e3328
   - 任务 10 隐患公示 → e264815
   - 任务 11 驾驶舱+导出 → 2e4238b
   - 任务 12 AI 辅助端点 → eb846dc
   - 任务 13 台账 Tab+service → 60e12e6/cfd2cbd
   - 任务 14 计划页+任务页 → b572a59
   - 任务 15 记录详情页 → 1100018
   - 任务 16 驾驶舱/模板/公示/公开页 → c8dff5b
   - 任务 17 回归门禁（952 后端/前端门禁/迁移幂等/字典种子）
2. **功能完整性**：规格 §14 接口清单中 hazard 相关端点是否全部存在（router 路由扫描）；§15 页面清单是否全部实现（frontend/src/pages/Hazard 扫描）。
3. **无缺口**：重点核对容易遗漏的——records 列表/详情（任务 13 补）、publicity-token、public/hazard 两个公开端点、dashboard 导出、调度器防重、派生计数在四个视图的注入。
4. **最终门禁抽验**：后端 `python -m pytest tests/ -q`（预期 952）；前端 `npx tsc -b`、`npx vitest run`（预期 111）；`git diff master..HEAD --check` 干净。
5. **结论**：✅ 可交付 / ❌ 有缺口（列清单）。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_final_review --claim-id <claim_id> --exit-code 0 --summary "隐患批次最终整体审查通过"
```

最终回复报告：task_id、claim_id、17 任务逐项核对证据表、端点/页面完整性扫描、门禁抽验结果、结论。

## 规则

- 全程只读；不修改任何源码/测试文件；阻塞时停下汇报。
- 全程用简体中文交流。
