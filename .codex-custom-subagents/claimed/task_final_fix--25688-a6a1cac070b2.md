# Codex Custom Subagents task handoff v1

Task: task_final_fix

## 修复最终审查发现的 2 个问题（分支 codex/ai-sign-review）

worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=e22d432）。

最终整体审查（claim 26848-190298fc572e，报告在 `.codex-custom-subagents\claimed\task_final_review--26848-190298fc572e.md`）发现 2 个建议修改级问题，均需修复并补回归测试。修复后提交为新 commit（消息建议 `fix(risk-notice-card): preserve adopted signs on optimize save and support explicit empty signs`），不得 amend 旧提交。

### 问题 1：AI 优化采用路径覆盖已采用的标志（前端）

**位置**：`frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx:711-728`（adoptOptimized）

**现象**：adoptOptimized 直接把 `compare.optimized`（RightColumn，不含 signs/signs_source）传给 saveSnapshot。后端 RightColumn.model_dump() 含默认 `signs: []`、`signs_source: None`，保存后快照被写入空标志 → 用户先「AI 审查标志→采用」（或人工微调）保存的标志被静默覆盖，卡片回退规则标志、来源 Tag 消失。

**修复要求**：
1. 在 `frontend\src\utils\riskNoticeCardSigns.ts` 新增纯函数（如 `mergeOptimizedContent(optimized: RightColumn, signs: SignItem[], signs_source: "rule" | "ai" | "manual"): {右栏四块 + signs + signs_source}`），返回 `{...optimized, signs, signs_source}` 结构的完整 content（结构对齐 `SignReviewContent`：hazard_description/accident_types/control_measures/emergency_measures/signs/signs_source）。
2. adoptOptimized 改为调用该函数：`saveSnapshot(enterpriseId, objectId, mergeOptimizedContent(compare.optimized, card.signs, card.signs_source))`（signs 用当前卡片已展示的快照标志，来源沿用当前值；card.signs 恒为数组，signs_source 缺失时回落 "rule"）。
3. 在 `frontend\src\utils\riskNoticeCardSigns.test.ts` 补单测：传入带 signs/signs_source 的 optimized + 自定义 signs → 断言返回 content 含右栏原值 + 自定义 signs + 来源透传；另测 signs_source 缺失回落 "rule"。注意 `RightColumn` 类型从 `@/types/riskNoticeCard` 导入。
4. 不改 AI 优化请求/响应链路，只修采用保存组装。

### 问题 2：显式空标志列表无法持久化「无标志」状态（后端）

**位置**：`backend\app\services\risk_notice_card_service.py:171-176`（snapshot_signs）

**现象**：snapshot_signs 用 truthiness 判断 `if content and content.get("signs"):`，人工微调移除全部标志保存 `signs: []` + `signs_source=manual` 后，snapshot_signs 返回 None → build_card_data 回退规则 match_signs，卡片显示规则标志却带「人工调整」Tag，且 ai-review-signs 端点同样回退规则标志。规格 §6 要求空列表是合法最终状态。

**修复要求**：
1. snapshot_signs 改为键存在性判断（如 `if content is not None and content.get("signs") is not None:` 返回 `content["signs"]`），区分「无 signs 键」（回退规则）与「显式空列表」（返回 []，卡片显示空标志 + 来源 Tag 保持）。
2. 检查调用方（build_card_data :254、ai-review-signs 路由 :348）在返回 [] 时的行为是否自然正确：build_card_data 应展示空标志（EMPTY_TEXT 语义由前端处理）+ signs_source 保持快照值；ai-review-signs 端点 current_signs 应为 []（AI 看到空当前标志）。如有不自然之处一并修正。
3. 在 `backend\tests\test_risk_notice_card_service.py` 补回归测试：快照 content 含 `signs: []` + `signs_source="manual"` 时 build_card_data 返回 signs=[] 且 signs_source="manual"（不回退规则、不丢来源）；无 signs 键时仍回退规则（既有测试 test_build_card_data_prefers_snapshot_signs 覆盖，勿破坏）。
4. 如需要，在 `backend\tests\test_risk_notice_card_api.py` 补 1 条快照保存/读取空标志列表的端点级测试。

### 门禁（修复后必须全过再提交）

* `cd backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -q` 全绿
* `cd backend && python -m pytest tests/ -q` → 442 passed（原 441 + 新增，exit 0；proactor closed-pipe 为既有噪音）
* `cd frontend && npx tsc -b` → 0 错误
* `cd frontend && npx vitest run` → 75 passed（原 74 + 新增）
* `npx eslint` 改动文件 exit 0
* `git diff --check` 干净；新提交只含本次改动清单文件（TASKS.md 永不 commit）
* 行尾统一 CRLF、无 BOM

### 上下文

* 提交前用显式 `git add <文件>` + `git diff --check`（不要 git save，避免把 TASKS.md 带进提交）。
* 审查只读期已过，本次可改代码；但不得动其他功能文件、不得 amend 旧提交。
