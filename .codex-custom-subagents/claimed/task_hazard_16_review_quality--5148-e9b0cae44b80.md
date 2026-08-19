# Codex Custom Subagents task handoff v1

Task: task_hazard_16_review_quality

## 目标

对隐患任务 16「驾驶舱/模板/公示/公开页」提交 `c8dff5b`（父 `1100018`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`c8dff5b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **页面结构**：5 个新页面组件分层清晰、状态管理无 setState-in-effect 等反模式（eslint react-hooks 合规）；handler 单一职责；无重复逻辑；SVG 自绘图表正确（饼图扇形 path/折线/条形计算）。
2. **数据正确性**：dashboard 指标口径与后端一致（及时率 None、环比 None、重大双口径）；模板 items 动态表单与后端 items 结构一致；token localStorage 企业隔离（key={enterpriseId} 重挂载）；nonce 生成与提交（uuid 兜底、隐藏字段）；免登录照片 data URL 取舍说明（后端原样存储）；公开页仅消费后端脱敏字段。
3. **交互细节**：scope 过滤/复制链接/打印样式/409/404 Result/loading/disabled 完整；导出 blob 与既有惯例一致。
4. **测试质量**：service 新增 2 用例断言有效（URL/body/nonce/scope/解包）。
5. **门禁**：tsc -b/eslint/vitest/后端全量 pytest 全绿；git diff --check 干净。
6. **无过度工程**：改动最小化；零新依赖（图表自绘）。
7. **无越界**：`git show c8dff5b --stat` 恰 9 个清单文件，消息精确匹配「feat(hazard): dashboard, templates, publicity and public pages」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed）
- `git show --check c8dff5b`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_16_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患驾驶舱模板公示公开页质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
