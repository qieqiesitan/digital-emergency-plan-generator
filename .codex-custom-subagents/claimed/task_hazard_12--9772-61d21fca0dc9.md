# Codex Custom Subagents task handoff v1

Task: task_hazard_12

## 目标

实现隐患管理任务 12「AI 辅助端点」并提交：新增 plan-builder / schedule-suggestion / checklist / setup-wizard 四个文本通道端点，复用既有 grade / governance-plan / record-assist / checklist-template。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`2e4238b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：`backend/app/routers/hazard_management.py`（追加四个 AI 端点）、`backend/app/services/hazard_ai_service.py`（追加对应服务函数）、新建 `backend/tests/test_hazard_ai_api.py`。

**统一模式**（规格 §3.7 原则 + §16）：文本输入 → `llm_text_completion(messages, ai_config, timeout=60)` → `_parse_ai_json` → 返回结构校验 → 任何失败/未配置/非法返回 → `{available: false, note: ...}`（200 降级不阻塞）；每个端点至少一个 mock LLM ok 用例 + 一个 fallback 用例；不落库（页面确认后走既有 CRUD/流程端点）。

**1. `POST /ai/plan-builder`（排查计划 AI 一键生成，§3.7 #2）**

- body：`{areas, frequency_preference}`（区域清单文本、频次偏好文本，均必填非空 422）。
- 返回 `{available, plans, note}`；plans 数组元素 `{name, category, frequency, weekdays?, responsible_user_name?, zone_names?}`（名称/类别/频次/责任人建议/覆盖分区，责任人用建议姓名文本、分区用名称文本——页面确认后映射为企业成员与分区 id，docstring 说明）。
- prompt 要求返回 2-6 套计划，中文，覆盖日常/综合/专项/节假日类别。

**2. `POST /ai/schedule-suggestion`（AI 排程建议，§6）**

- body：`{plan_draft}`（计划草稿文本，必填非空）+ 可选 `{zone_risk_hints, history_hints}`（分区风险等级/历史隐患提示文本）。
- 返回 `{available, suggested_frequency, suggested_responsible_user_id, reason, note}`；suggested_frequency 用 daily/weekly/monthly/custom 码值；suggested_responsible_user_id 为建议用户 id（服务不校验存在性，页面确认后校验落库；若 AI 无法给出则 null + reason 说明）。

**3. `POST /ai/checklist`（AI 清单补全，§6）**

- body：`{task_context}`（任务上下文文本，必填非空，如任务标题/分区/既有清单项）。
- 返回 `{available, items, note}`；items 元素 `{content, expected_note}`（8 项以内建议新增项，页面勾选后与既有项合并去重）。

**4. `POST /ai/setup-wizard`（智能引导，§3.8/#7）**

- body：`{industry, areas, employee_count, frequency_preference}`（行业/主要区域/人数/频次偏好，industry+areas 必填，其余可空）。
- 返回 `{available, org_suggestion, plans_suggestion, checklist_suggestion, note}` 三块——org_suggestion 复用组织 AI 建树函数（enterprise_org_service.suggest_org_tree 同型）、plans_suggestion 复用 plan-builder 逻辑、checklist_suggestion 复用 checklist-template 逻辑（报告复用方式：直接调用既有服务函数或同构 prompt，避免重复实现）。

**5. 已有端点复用**：`/ai/grade`、`/ai/governance-plan`、`/ai/record-assist`、`/ai/checklist-template` 已实现（任务 4-6），本任务不改动，测试中回归即可。

**6. 测试**（`backend/tests/test_hazard_ai_api.py`，mock db/LLM 风格与既有 AI 测试一致，async 带 `@pytest.mark.asyncio`）

- 四端点各覆盖：ok（结构断言）、LLM 异常降级、未配置降级（跳过 LLM）、输入为空 422、返回结构非法降级（字段缺/类型错）；setup-wizard 三块结构断言。
- 断言有效无空断言；提交前跑目标测试 + 全量回归。

**7. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §3.7、§3.8、§6、§7、§16。
- 既有 AI 服务：`backend/app/services/hazard_ai_service.py`（checklist-template/record_assist/ai_grade/ai_governance_plan 模式）、`backend/app/services/enterprise_org_service.py`（suggest_org_tree）。
- 既有路由：`backend/app/routers/hazard_management.py`（AI 端点惯例）、`backend/app/routers/enterprise_org.py`（ai_suggest_org_tree）。
- 测试先例：`backend/tests/test_hazard_template_api.py`（AI mock 风格）、`backend/tests/test_hazard_grade_api.py`。

## 验证

- `python -m pytest tests/test_hazard_ai_api.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/routers/hazard_management.py backend/app/services/hazard_ai_service.py backend/tests/test_hazard_ai_api.py
git commit -m "feat(hazard): text-only AI assist endpoints"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_12 --claim-id <claim_id> --exit-code 0 --summary "隐患AI辅助端点实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（四端点返回契约/setup-wizard 复用方式/降级）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
