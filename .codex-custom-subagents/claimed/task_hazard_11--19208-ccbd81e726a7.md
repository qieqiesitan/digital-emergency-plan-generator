# Codex Custom Subagents task handoff v1

Task: task_hazard_11

## 目标

实现隐患管理任务 11「驾驶舱 + 台账/监管导出」并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`e264815`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：新建 `backend/app/services/hazard_export_service.py`、`backend/app/routers/hazard_management.py`（追加 dashboard/export 端点）、新建 `backend/tests/test_hazard_dashboard_api.py`。openpyxl 若已在 requirements（管控清单导出用过）则复用，未加则补。

**1. `GET /dashboard`（驾驶舱）**（router 既有前缀 `/enterprises/{enterprise_id}/hazard-inspection`）

- 指标卡：
  - 未闭环隐患数（status != closed 记录数）+ 未闭环风险点数（去重 object_id 数）；
  - 整改及时率：按自然月滚动——本月应闭环（deadline 在本月内且已 closed 或超期）与按期闭环（closed_at <= deadline）口径，报告公式；
  - 重大挂牌数（level=major 且进入过 pending_approval 的记录数或当前 major 未闭环数，报告口径）；
  - 超期数（rectifying 且 deadline < 今天 或任务 overdue，报告口径）；
  - 月度隐患数（当月新增）+ 环比（与上月对比百分比）；
  - 扫码待确认数（source_type=report 且 status=registered 的记录数）。
- 图表：类型分布（hazard_type 分组计数）、月度趋势（近 6/12 月新增折线，报告窗口）、重大隐患专表（major 记录列表：code/title/deadline/status）、企业对比（同账号多企业：各企业未闭环数，report 实现）。
- 未读数：`hazard_notifications` 中该企业用户 read_at IS NULL 计数（按 user_id 当前用户，报告口径：本企业全部未读 vs 当前用户未读）。
- 权限：读=归属（404）。

**2. 台账导出** `GET /export/ledger.xlsx`（企业内用，含敏感字段）

- sheet1 台账：全部字段（code/title/description/level/status/hazard_type/source_type/object/measure/location/photo_urls/rectification_plan/deadline/rectification_user/reviewer_user/created_by/created_at/closed_at 等，按模型列合理选取并说明）；
- sheet2 超期清单：rectifying 且 deadline < 今天 的记录；
- sheet3 重大隐患：level=major 记录。
- StreamingResponse + openpyxl（复用既有导出先例，报告文件流方式与 filename）。

**3. 监管上报导出** `GET /export/report.xlsx`（脱敏）

- 字段：编号/名称/位置/等级/判定依据（grading_basis）/整改期限（deadline）/责任单位（整改责任人所在部门，经 enterprise_members/org 节点推导，缺省「—」）/整改进度（最近整改 content 或状态标签）。
- 不含责任人姓名/联系方式/照片等敏感信息。

**4. 测试**（`backend/tests/test_hazard_dashboard_api.py`，mock db 风格与既有一致，async 带 `@pytest.mark.asyncio`）

- 统计口径（整改及时率公式/平均整改周期 closed_at - created_at/月度环比）、导出内容（3 sheet 存在/监管字段白名单/脱敏字段不出现）、未读数、权限 404。
- 断言有效无空断言；提交前跑目标测试 + 全量回归。

**5. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §12、§14、§16。
- 模型：`backend/app/models/hazard_management.py`（HazardRecord/HazardNotification）、`backend/app/models/enterprise_org.py`（EnterpriseMember）、`backend/app/models/enterprise.py`。
- 既有导出先例：`backend/app/services/risk_control_list_service.py` 或同类 openpyxl 导出（查 `openpyxl` 使用处）、`backend/app/routers/risk_management.py` 导出端点（StreamingResponse 惯例）。
- 惯例：`backend/app/routers/hazard_management.py`（_get_ent/ApiResponse）、`backend/tests/test_hazard_grade_api.py`（mock 风格）。

## 验证

- `python -m pytest tests/test_hazard_dashboard_api.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/services/hazard_export_service.py backend/app/routers/hazard_management.py backend/tests/test_hazard_dashboard_api.py
git commit -m "feat(hazard): dashboard stats and ledger/report export"
```

若补 requirements（openpyxl）一并 add 并在报告中说明；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_11 --claim-id <claim_id> --exit-code 0 --summary "隐患驾驶舱与导出实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（指标口径/环比公式/导出 sheet 与脱敏/未读数）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
