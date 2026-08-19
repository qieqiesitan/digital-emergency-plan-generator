# Codex Custom Subagents task handoff v1

Task: cockpit_01_spec_review

你正在审查「企业驾驶舱」任务 1 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 1 规格，已修正口径）

创建 `backend/app/services/enterprise_cockpit_service.py` 与 `backend/tests/test_enterprise_cockpit.py`，内容要点：

1. 纯函数：
   - `_classify_level(level)`：重大/较大/一般/低 映射 major/larger/general/low；缺失或未知映射 "general"；
   - `_risk_index(counts)`：归一化加权平均口径 `min(100, round((major*100 + larger*70 + general*40 + low*10) / total))`，total<=0 时返回 0；
   - `aggregate_events(events)`：返回 risk_counts（major/larger/general/low/total）、zone_risks（按 zone_name 聚合 counts+total，按 total 降序）、top_risks（按风险点 object 聚合，取 score 最高者，最多 3 条，含 name/level/score/responsible_unit）、risk_index；
   - `derive_todos(reports, open_hazard_count, due_hazard_count, overdue_hazard_count, completion_modules)`：最多 3 条，优先级排序（报告未生成 high、已逾期 high、即将到期 medium、整改中 low、周边环境未更新 low）。
2. `_fetch_events(db, enterprise_id)`：RiskEvent 经 RiskUnit/RiskObject 到 RiskZone 关联企业，dict.fromkeys 去重；
3. `build_cockpit_summary(db, enterprise_id, enterprise=None)`：返回 {risk_counts, zone_risks, top_risks, risk_index, hazard_counts:{open,due,overdue}, todos, completion:{percent,modules:[{key,label,done}]}, recent_activities}；企业不存在抛 ValueError("企业不存在")；复用 compute_completion(enterprise_id, db, enterprise=ent)；报告 completed 计数用 RiskAssessmentReport/ResourceInvestigationReport；隐患 open 为 status != "closed"，due 为 deadline <= today+3 天，overdue 为 deadline < today。
4. 测试 5 条：classify_level、risk_index（{2,4,18,10} 期望 38、{5,0,0,0} 期望 100）、aggregate（{1,1,1,1} 期望 risk_index 55、zone/top 断言）、derive_todos（3 条且首条为风险评估报告未生成、含 2 条隐患即将到期）、derive_todos 空。
5. Commit 消息：`feat(cockpit): enterprise cockpit summary aggregation service`；不提交 TASKS.md；只改这 2 个文件。

## 实现者声称构建了什么
- 状态 DONE；commit 499a7a4（worktree 分支 codex/enterprise-cockpit）；测试 5 passed；
- 两个文件与任务正文逐字一致；TASKS.md 未提交。

## 关键：不要信任报告

实现者的报告可能不完整、不准确或过于乐观。你必须独立验证：

- 阅读 worktree 中实际代码（工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit，用 `git show 499a7a4 --stat` 与 `git show 499a7a4` 或直接读文件）；
- 逐行对比实际实现与上面「要求的内容」；
- 检查缺失的需求、多余的功能、理解偏差（尤其 risk_index 口径是否为归一化加权平均、derive_todos 优先级顺序、hazard_counts 字段、completion.modules 的 key/label/done 结构、_fetch_events 去重）；
- 验证测试是否真实断言行为（不是空断言），并实际运行：
  - 测试命令（注意：worktree 无 venv，用主仓库的解释器）：`C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe -m pytest tests/test_enterprise_cockpit.py -v`（工作目录为 worktree 的 backend）
- 检查提交只含 2 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（实际运行的测试输出、git show 核验结果、发现的任何问题）
