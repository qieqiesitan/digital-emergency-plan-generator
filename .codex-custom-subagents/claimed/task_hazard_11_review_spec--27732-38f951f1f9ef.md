# Codex Custom Subagents task handoff v1

Task: task_hazard_11_review_spec

## 目标

对隐患任务 11「驾驶舱+台账/监管导出」提交 `2e4238b`（父 `e264815`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`2e4238b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §12、§14、§16）。

## 审查清单（逐项核验并给出证据）

1. **指标卡**：未闭环隐患数/风险点数、整改及时率（本月应闭环中 closed_at<=deadline 占比、分母 0 返回 None）、平均整改周期（closed_at-created_at 均值）、重大挂牌数（major_count 当前未闭环 + major_approved 累计，双口径说明）、超期数（rectifying 超期 + overdue 任务）、月度环比（(本月-上月)/上月，上月 0 返回 None）、扫码待确认（source_type=report 且 registered）——口径与规格 §12 一致。
2. **图表**：类型分布（hazard_type 分组）、月度趋势、重大专表（major 记录）、企业对比（同账号多企业，含 0 企业）——字段齐全。
3. **未读数**：hazard_notifications read_at IS NULL——total/mine/by_type 口径合理（消息角标）。
4. **台账导出**：ledger.xlsx 3 sheet（台账 19 列/超期清单含超期天数/重大隐患）；对象/措施/用户名解析未命中回退 id；状态/类型走字典中文标签。
5. **监管导出**：report.xlsx 8 列白名单脱敏（编号/名称/位置/等级/判定依据/整改期限/责任单位/整改进度）；不含责任人姓名/联系方式/照片；责任单位经 org 节点推导缺省「—」。
6. **文件流**：BytesIO + StreamingResponse，filename 对齐既有惯例；权限读=归属 404。
7. **测试有效性**：19 个测试断言有效无空断言；覆盖统计口径（及时率/平均周期/环比）、导出内容与脱敏、未读数、权限。
8. **无越界**：`git show 2e4238b --stat` 恰 3 个清单文件（services/hazard_export_service.py、routers/hazard_management.py、tests/test_hazard_dashboard_api.py），消息精确匹配「feat(hazard): dashboard stats and ledger/report export」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_dashboard_api.py -v`（预期 19 passed）
- `python -m pytest tests/ -q`（预期 904 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 2e4238b`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_11_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患驾驶舱导出规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
