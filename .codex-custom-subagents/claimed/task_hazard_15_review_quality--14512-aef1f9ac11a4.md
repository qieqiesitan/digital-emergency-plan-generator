# Codex Custom Subagents task handoff v1

Task: task_hazard_15_review_quality

## 目标

对隐患任务 15「HazardRecordDetailPage」提交 `1100018`（父 `b572a59`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`1100018`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **页面结构**：932 行详情页——分层清晰（常量/类型/纯函数/子组件/query/mutation/JSX）；状态管理无 setState-in-effect 等反模式；handler 单一职责；无重复逻辑；eslint react-hooks 合规。
2. **按钮矩阵质量**：canShowAction 集中判定正确；身份推断（企业主=members 缺失、启用 admin）无误判路径；members 未加载完不渲染按钮的取舍合理。
3. **数据正确性**：时间线四路合并排序稳定；action 映射/review_type 区分/pass-fail 着色正确；治理方案重大必填与后端 _apply_grade 校验一致；reject 后重新分级预填；rectify 复查人过滤整改人；level_source 记录 ai/manual 语义正确。
4. **交互细节**：各 Modal 字段与后端 body 一致；404/403 Result 展示与重试/返回；操作成功 refetch+invalidate；loading/disabled 状态完整。
5. **门禁**：tsc -b/eslint/vitest/后端全量 pytest 全绿；git diff --check 干净。
6. **无过度工程**：改动最小化（2 文件）；无无关抽象。
7. **无越界**：`git show 1100018 --stat` 恰 2 个清单文件，消息精确匹配「feat(hazard): record detail with state machine actions」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed）
- `git show --check 1100018`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_15_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患记录详情页质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
