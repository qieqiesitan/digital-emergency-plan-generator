# Codex Custom Subagents task handoff v1

Task: task_hazard_08_review_spec

## 目标

对隐患任务 8「APScheduler」提交 `3225ed2`（父 `8e69550`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`3225ed2`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.2、§5.12、§6、§13、§16）。

## 审查清单（逐项核验并给出证据）

1. **调度器结构**：`hazard_scheduler.py` 四个扫描函数独立（到期生成/记录超期/提前提醒/任务超期）+ `run_hazard_scans` 组合入口；注入 now/on_date 便于测试；单扫描函数不 commit、组合末尾统一 commit。
2. **① 到期生成**：enabled 计划全量扫后交 `generate_tasks_for_plan` 的 _is_due 判断（daily/weekly/custom/monthly 语义一致）；防重复用（同 plan 同日返回 None）。
3. **② 记录超期**：rectifying 且 deadline < 今天；同 record 已有 type=overdue 通知则跳过（防重）；接收人 rectification_user_id 为空兜底企业主；audit log action=overdue；deadline 未配置不扫描。
4. **③ 提前提醒**：pending/processing 且 due_at-2h <= now < due_at；message 含任务标题与期限；防重用 `reminder_notified_at`（幂等补列 + 模型补列 + 扫描 IS NULL 过滤 + 函数内防御）。
5. **④ 任务超期**：pending/processing 且 due_at < now → status=overdue + overdue_notified_at=now + overdue 通知（防重）；与记录超期明确两类。
6. **main.py lifespan**：启动注册 interval 5 分钟作业（async with async_session）；异常/依赖缺失 logger.warning 降级不阻塞；关闭 shutdown(wait=False)；最小改动。
7. **requirements**：apscheduler==3.10.4 加入。
8. **时区约定**：与 hazard_service 一致（naive 本地时间）。
9. **测试有效性**：16 个测试断言有效无空断言；覆盖到期生成/超期通知防重/提前提醒/任务超期/组合入口。
10. **无越界**：`git show 3225ed2 --stat` 恰 6 个清单文件（main.py、models/hazard_management.py、services/hazard_scheduler.py、db_migration_hazard_management.sql、requirements.txt、tests/test_hazard_scheduler.py），消息精确匹配「feat(hazard): scheduler for task generation and overdue notifications」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_scheduler.py -v`（预期 16 passed）
- `python -m pytest tests/ -q`（预期 852 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 3225ed2`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_08_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患调度器规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
