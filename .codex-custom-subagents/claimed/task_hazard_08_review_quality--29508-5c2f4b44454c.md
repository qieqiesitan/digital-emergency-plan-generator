# Codex Custom Subagents task handoff v1

Task: task_hazard_08_review_quality

## 目标

对隐患任务 8「APScheduler」提交 `3225ed2`（父 `8e69550`）做只读代码质量复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`3225ed2`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 审查清单（逐项核验并给出证据）

1. **服务层结构**：`hazard_scheduler.py` 228 行四个扫描函数+组合入口职责清晰；SQL 过滤与内存防御不重复冗余；now/on_date 注入设计一致；无重复逻辑；docstring 说明时区/防重/语义。
2. **防重实现质量**：`reminder_notified_at` 补列（模型+迁移幂等对齐）；upcoming 防重（IS NULL + 防御性跳过）；overdue 通知防重（通知存在性）；任务超期 overdue_notified_at 防重；四类防重无互相污染。
3. **数据正确性**：通知字段（enterprise_id/user_id/record_id/type/message）正确；接收人兜底（整改人→企业主）；audit log（user_id=None 系统扫描）与既有状态机 audit 写法一致；deadline/due_at 比较时区口径一致。
4. **lifespan 质量**：main.py 最小改动；启动异常降级不阻塞；关闭清理；局部导入避免依赖缺失时 import 失败。
5. **测试质量**：16 个测试断言有效无空断言；mock 风格一致（async 带 @pytest.mark.asyncio）；覆盖三扫描+任务超期+组合；防重场景（重复扫描不再创建）有断言。
6. **无过度工程**：改动最小化；无无关抽象。
7. **无越界**：`git show 3225ed2 --stat` 恰 6 个清单文件，消息精确匹配「feat(hazard): scheduler for task generation and overdue notifications」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_scheduler.py -v`（预期 16 passed）
- `python -m pytest tests/ -q`（预期 852 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 3225ed2`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_08_review_quality --claim-id <claim_id> --exit-code 0 --summary "隐患调度器质量复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
