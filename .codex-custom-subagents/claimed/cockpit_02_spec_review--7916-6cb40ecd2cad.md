# Codex Custom Subagents task handoff v1

Task: cockpit_02_spec_review

你正在审查「企业驾驶舱」任务 2 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 2 规格）

1. 新建 `backend/app/schemas/enterprise_cockpit.py`，包含 9 个 Pydantic 模型：RiskCounts（major/larger/general/low/total 默认 0）、TopRisk（name/level/score: float|None/responsible_unit: str|None）、ZoneRisk（zone_name/counts: RiskCounts/total）、CockpitTodo（priority/title/note）、CompletionModule（key/label/done）、CockpitCompletion（percent/modules）、ActivityItem（actor 默认"系统"/action/time）、HazardCounts（open/due/overdue 默认 0）、CockpitSummary（risk_counts/zone_risks/top_risks/risk_index/hazard_counts/todos/completion/recent_activities，全部带默认值）。
2. 修改 `backend/app/routers/enterprises.py`：新增 `GET /{enterprise_id}/cockpit-summary`，response_model=ApiResponse[CockpitSummary]；企业归属校验（id + user_id）不存在返回 404「企业不存在」；调用 build_cockpit_summary 后包 CockpitSummary。
3. 修改 `backend/app/services/enterprise_cockpit_service.py`：`_fetch_events` 增加显式 selectinload（RiskEvent.object→RiskObject.zone、RiskEvent.unit→RiskUnit.object→RiskObject.zone）。
4. 测试 `backend/tests/test_enterprise_cockpit.py`：追加 2 个端点测试（缺失企业 404、200 payload 且 risk_index 55 / completion.percent 50）+ 2 个边界用例（aggregate_events([]) 全零/空、unit 级回退与坏值：level=None 归 general、score="abc" 归 0、top_risks 按 score 降序且含球罐区条目 score==0.0/responsible_unit==生产部）。
5. Commit：`feat(cockpit): enterprise cockpit summary endpoint`；只改这 4 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit 170e0ab（父 499a7a4）；4 文件 163 insertions；9 passed；全量 994 passed；
- 修正了任务文本 2 处笔误：①边界测试 top_risks 断言改为在列表中定位球罐区条目（因规格定义 TOP 按 score 降序，办公室 score 10 排第一）；②User 构造字段 password_hash（非 hashed_password）。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；用 `git show 170e0ab --stat`、`git show 170e0ab` 或直接读文件核验；
- 逐项比对上面「要求的内容」：schema 字段/默认值、端点路由与 404 语义、selectinload 链、测试断言（尤其 top_risks 排序与球罐区断言是否符合规格"按 score 降序"语义、User 字段与既有测试惯例一致）；
- 检查是否有多余功能或范围外改动；
- 实际运行测试（worktree 无 venv，用主仓库解释器，工作目录 worktree\backend）：
  `C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe -m pytest tests/test_enterprise_cockpit.py -v`
- 检查提交只含 4 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（测试输出、git show 核验、发现的任何问题）
