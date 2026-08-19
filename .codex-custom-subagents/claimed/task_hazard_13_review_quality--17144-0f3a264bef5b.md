# Codex Custom Subagents task handoff v1

Task: task_hazard_13_review_quality

## 目标

对隐患任务 13「HazardInspectionTab+hazardService」两个提交（`60e12e6`、`cfd2cbd`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`cfd2cbd`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **后端质量**：列表/详情端点 handler 单一职责；复用 _get_ent/ApiResponse/字典标签 helper；筛选与统计实现正确（stats 口径与 dashboard 一致）；详情时间线组装无 N+1 明显问题；错误消息中文可读。
2. **前端 service/类型质量**：hazardService.ts 函数式风格与 riskManagementService 一致；类型与后端字段对齐；URL/方法无笔误。
3. **页面质量**：HazardInspectionTab 413 行组件结构清晰、状态管理合理、无状态反模式；新建表单字段与 POST /records 一致；AI 预填降级不阻塞；导出 blob 下载正确；统计条/筛选/分页取舍说明。
4. **路由/接入质量**：EnterpriseDetailPage Tab 接入正确；占位路由与规划一致；无重复路由冲突。
5. **测试质量**：后端新增 10 用例断言有效；前端 service 12 用例断言有效；无空断言。
6. **无过度工程**：改动最小化；无无关抽象。
7. **无越界**：两提交文件清单精确匹配；`git show --check` 干净；TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_record_api.py -v`（预期 44 passed）
- `python -m pytest tests/ -q`（预期 952 passed，Event loop ResourceWarning 为既有非失败噪音）
- `npx tsc -b` exit 0、`npx eslint` 改动文件 exit 0、`npx vitest run` 全绿
- `git show --check 60e12e6`、`git show --check cfd2cbd`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_13_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患台账Tab质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
