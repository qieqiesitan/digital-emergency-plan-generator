# Codex Custom Subagents task handoff v1

Task: task_final_review

## 最终整体审查：AI 标志审查功能（分支 codex/ai-sign-review）

这是功能开发的最终整体审查。你在独立验收整个「AI 审查安全标志」功能是否达到用户目标与设计规格，不要信任任何中间报告，必须自己读代码验证。审查只读：不修改源码、不提交、不部署。

### 用户目标（背景）

用户反馈安全标志规则匹配不合理（洗眼台出现在餐具清洗区、会议室出现安全帽等），提出「先按规则匹配，匹配完成后让 AI 审查，尽量使其合理准确」。经 brainstorm 确认设计：快照持久化 signs → AI 审查端点（规则匹配 + AI 审查）→ 前端差异对比 Modal → 采用/人工微调 → 来源 Tag。

### 规格文档

* `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\docs\superpowers\specs\2026-08-15-ai-sign-review-design.md`
* 实现计划：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review\docs\superpowers\plans\2026-08-15-ai-sign-review.md`

### 你的工作（worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`）

1. 通读规格文档与实现计划，列出功能验收清单（快照 signs 持久化、normalize 规范化、AI 审查服务与端点、前端类型/service、AI 审查按钮与差异对比、人工微调编辑、来源 Tag、catalog 中文名映射、限量约束每类≤2 总数≤8）。
2. 对每个验收项，读实际代码（backend/app/services/risk_notice_card_service.py、risk_notice_card_ai.py、routers/risk_notice_card.py、schemas/risk_notice_card.py；frontend/src/utils/riskNoticeCardSigns.ts、services/riskNoticeCardService.ts、types/riskNoticeCard.ts、components/enterprise/RiskNoticeCard.tsx、pages/Enterprise/RiskNoticeCardPreviewPage.tsx）验证实现与规格一致，重点核对：
   - 快照 signs 保存/读取/回填 signs_source 链路完整
   - AI 审查端点：候选库只能从现有库选、每类≤2 总数≤8、remove 限当前/add 限候选、解析失败 502
   - 前端编辑保存后 signs_source=manual、来源 Tag 正确显示、公开页不暴露编辑入口
   - 已知取舍是否可接受：候选库空态（未先运行 AI 审查时仅可移除已选，Modal 提示先运行审查）、catalog 实际 32 个 vs 规格「36」（instruction-goggles/notice-eyewash/notice-shower/warning-confined-space 未被组引用且不在 VALID_SVG_NAMES，属既有数据缺口）
3. 抽查门禁（不必全量重跑，可选择性复验关键项）：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -q`、`cd frontend && npx tsc -b`、`npx vitest run src/utils/riskNoticeCardSigns.test.ts`。
4. 报告：把最终审查报告追加写入 claimed 文件末尾——逐项验收结论、发现的问题（file:line + 级别：必须修复/建议修改/仅供参考）、已知取舍接受与否、整体结论 ✅ 通过可收尾 / ❌ 需修复。给出收尾建议（本地合并回 master、部署 Docker 等，供主控向用户确认）。

### 上下文

* 分支 codex/ai-sign-review，HEAD=e22d432，全部 13 个提交已通过各自任务双审 + 回归门禁（后端 441 passed、前端 tsc 0 错误 + vitest 74 passed）。
* TASKS.md 永不 commit（项目惯例）。

---

# 最终整体审查报告（task_final_review，claim 26848-190298fc572e，attempt a9f853dcab314f2c94582eca77503943）

> 审查人：deepseek_anthropic_worker（deepseek-v4-flash）｜日期：2026-08-16｜方式：独立读码验证 + 实测复跑，不信任中间报告。

## 一、验收清单逐项结论

### 1. 快照 signs 持久化（保存/读取/回填 signs_source 链路）— ✅（含 2 个边界问题见第四节）
- 后端 schemas：`RightColumn` 增加 `signs: list[SignItem]`、`signs_source: str|None`（backend/app/schemas/risk_notice_card.py:15-17）；`SnapshotSaveRequest.content: RightColumn` 天然透传。
- `save_snapshot`（backend/app/services/risk_notice_card_service.py:294-326）：signs 列表规范化后持久化，signs_source 非法值回退 rule；无快照建 v1，有快照 version+1。
- `build_card_data`（:246-286）：快照 signs 优先，缺省回退规则 `match_signs`，signs_source 回填（快照值/缺省 rule）；旧快照无 signs 向后兼容。
- 公开端点（backend/app/routers/public_risk_notice.py:59）与导出（risk_notice_card.py:246）复用 build_card_data，快照标志链路一致。
- 测试：test_build_card_data_prefers_snapshot_signs / signs_source_defaults_rule / missing_source / save_snapshot_normalizes_signs_and_signs_source / signs_missing_source_defaults_rule 全绿。

### 2. normalize_signs 规范化 — ✅
- backend/app/services/risk_notice_card_service.py:140-166：过滤 `VALID_SVG_NAMES` 之外、去重、按 SIGN_CATEGORY_ORDER（警告→禁止→指令→提示）排序、每类 ≤2、总数 ≤8；category 缺失/错配静默丢弃（读旧快照脏数据路径）。
- `VALID_SVG_NAMES` = SIGN_GROUPS 全部条目 ∪ DEFAULT_SIGN_GROUP，与端点候选库一致（32 个，见第五节）。
- 测试：test_normalize_signs_filters_and_limits（非法丢弃/排序/限量）、test_normalize_signs_max_total_truncates 通过。

### 3. AI 审查服务与端点 — ✅
- `review_signs`（backend/app/services/risk_notice_card_ai.py:69-135）：组装完整上下文（企业/风险点名称/类别/位置/事件事故类型·触发条件·后果/当前标志/候选库），输出约束「只能从候选库选、remove 限当前、每类≤2、总数≤8」；复用 `_parse_optimized_json` 容错；JSON 解析失败 → HTTPException 502；非 dict / 字段非 list 回落空列表。
- 端点 `POST /{object_id}/ai-review-signs`（backend/app/routers/risk_notice_card.py:292-372）：`_get_ent` 企业归属 404、对象 404；当前标志优先快照 signs（旧快照无 signs 时按快照 accident_types 回退，与卡片展示一致）；候选库 = SIGN_GROUPS 全组 + DEFAULT_SIGN_GROUP 去重；review 异常 502（HTTPException 透传）；无副作用。
- 响应结构 original_signs/suggestion/catalog 与规格 §7.1 一致（catalog 为规格后补充、用于人工微调与中文名映射，计划任务 8 推荐方案）。
- remove 限当前 / add 限候选：响应层为 AI 原样透传，约束落实在采用链路（前端 applySignSuggestion：remove 只删当前、add 去重且查候选库）与保存链路（save_snapshot → normalize_signs 丢弃库外），符合规格 §8「提示词 + 后端双保险」与 §10「非法/超量静默丢弃、截断」。
- 测试：test_review_signs_parses_suggestion / invalid_json_raises_502 / non_list_fields_fall_back；端点 success/404/502/HTTPException 透传/快照优先/旧快照回退/畸形建议 502/脏快照丢弃 全绿。

### 4. 前端类型 + service — ✅
- frontend/src/types/riskNoticeCard.ts：SignItem/SignSuggestion/AiSignReviewResponse（含 catalog）/CardData.signs + signs_source 联合类型，与后端 schema 一一对应。
- frontend/src/services/riskNoticeCardService.ts：`aiReviewSigns` POST 并解包 data；测试通过（riskNoticeCardService.test.ts 8 用例含 aiReviewSigns）。

### 5. AI 审查按钮 + 差异对比 Modal — ✅
- 预览页工具栏「AI 审查标志」按钮（RiskNoticeCardPreviewPage.tsx）：reviewing loading 防重入；失败提示「AI 审查失败，已保留原版」。
- SignReviewModal：建议删除（红删除线）/建议增加（绿）/保留（灰）三组 + 逐项理由；底部「采用建议并保存快照（版本 +1）」/「放弃，保留原版」。
- handleAdoptSigns：applySignSuggestion 应用建议 → 组装完整 content（右栏 + signs + signs_source=ai）→ saveSnapshot → refetch → 关闭 Modal；失败提示「保存快照失败，请重试」。

### 6. 人工微调编辑 — ✅
- RiskNoticeCard 标志区「编辑」入口仅在传入 onEditSigns 时渲染（RiskNoticeCard.tsx:333-335）；预览页传 `onEditSigns={() => setEditOpen(true)}`。
- SignEditBody：当前已选可移除 + 候选库网格（按类别分组）勾选添加；每类 ≤2、总数 ≤8 超限即时 message 提示；每次打开以当前 card.signs 重新初始化。
- 保存：组装完整 content + signs_source=manual → saveSnapshot → refetch → 版本 +1；取消不保存。

### 7. 来源 Tag + 公开页只读 — ✅
- RiskNoticeCard.tsx:158-165：signs_source=ai →「AI 审查」、manual →「人工调整」、rule/缺省不显示。
- 公开页 PublicRiskNoticePage.tsx:44 `<RiskNoticeCard card={card} />` 不传 onEditSigns → 不暴露编辑入口；来源 Tag 在公开页亦显示（规格 §9.4 未区分页面，属预期）。

### 8. catalog 中文名映射 — ✅
- 端点响应 `catalog: list[SignItem]`（name + svg_name）；SignReviewModal nameFor 优先候选库中文名、其次当前标志、兜底 svg_name；applySignSuggestion add 行取候选库 name/category（无候选时按前缀推断）；buildNameLookup/buildSignLookup 工具 + 测试覆盖。

### 9. 限量约束（每类 ≤2、总数 ≤8）— ✅
- 后端 normalize_signs 双上限 + 前端 MAX_SIGNS_PER_CATEGORY=2 / MAX_TOTAL_SIGNS=8 常量一致（riskNoticeCardSigns.ts + 测试断言）；编辑 Modal 即时校验，采用/保存均经后端规范化兜底。

## 二、门禁抽查结果（亲自复跑，非采信中间报告）

| 门禁 | 命令 | 结果 |
|------|------|------|
| 后端 API | `backend/.venv python -m pytest tests/test_risk_notice_card_api.py -q` | 36 passed |
| 后端服务 | `backend/.venv python -m pytest tests/test_risk_notice_card_service.py -q` | 26 passed |
| 后端全量 | `backend/.venv python -m pytest tests/ -q` | 441 passed（仅基线 unraisable GC 警告，exit 0） |
| 前端类型 | `cd frontend && npx tsc -b` | 0 错误 |
| 前端单测 | `npx vitest run` | 9 文件 74 passed（含 riskNoticeCardSigns 12 + riskNoticeCardService 8） |

## 三、发现的问题

### 【建议修改】1. AI 优化采用路径覆盖已采用的标志（跨流程，违背规格 §6「完整快照」）
- 位置：frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx:711-716（adoptOptimized 直接保存 `compare.optimized`，未携带 signs/signs_source）。
- 链路实证：RightColumn.model_dump() 含默认 `signs: []`、`signs_source: None` → save_snapshot（risk_notice_card_service.py:302-308）写入 `signs=[]` + `signs_source="rule"` → 用户先「AI 审查标志→采用」保存的 AI/人工标志被覆盖，卡片静默回退规则标志、来源 Tag 消失。
- 规格 §6 要求「任何保存（AI 优化文案 / AI 审查标志 / 人工微调）都写入当前展示的完整内容（右栏 + 标志），版本递增互不覆盖」——本路径违背。
- 修复建议：adoptOptimized 组装 content 时带上当前 `card.signs` / `card.signs_source`（复用 SignReviewContent 结构）；补 1 个回归测试（AI 优化采用后快照仍含此前采用的 signs）。

### 【建议修改】2. 显式空标志列表无法持久化「无标志」状态，且来源 Tag 与实际展示不一致
- 位置：backend/app/services/risk_notice_card_service.py:171-175（snapshot_signs 用 truthiness 判断 `content.get("signs")`）。
- 链路实证：人工微调移除全部标志 → 保存 content `signs=[]` + `signs_source=manual` → snapshot_signs 返回 None → build_card_data 回退规则 match_signs；卡片显示规则标志却带「人工调整」Tag（signs_source 仍回填 manual）。
- 规格 §6「signs：最终标志列表（规则 / AI 审查确认 / 人工微调，三者的结果都落这里）」——空列表应是合法最终状态。
- 修复建议：改为 `"signs" in content`（或 `content.get("signs") is not None`）区分「无键」（回退规则）与「显式空」（显示无标志 + EMPTY_TEXT）；ai-review-signs 端点快照优先分支（risk_notice_card.py:311）随之自然生效；补空列表持久化回归测试。

### 【仅供参考】3. AI 审查响应层 remove/add 未做服务端过滤
- 位置：backend/app/routers/risk_notice_card.py:352-360（SignSuggestion(**suggestion) 原样透传）。
- 影响：AI 若返回库外 svg_name 或不在当前标志的 remove，Modal 会短暂展示（中文名兜底为 svg_name），采用保存时才被丢弃/忽略。规格 §10 明确「AI 建议非法/超量 → 后端规范化静默丢弃/截断，不报错」，行为合规；若希望 Modal 展示即干净，可在端点响应前过滤（remove ∩ 当前、add ∩ 候选）。

### 【仅供参考】4. 测试基线警告
- 后端全量存在 PytestUnraisableExceptionWarning（asyncio 事件循环关闭），此前任务已 stash 对比确认为基线既有、与本分支无关，exit 0。

## 四、已知取舍评估

1. 候选库空态（未先运行 AI 审查时人工微调仅可移除已选、Modal 提示先运行审查）：✅ 接受。实测 SignEditBody 在 catalog 为空时显示「候选库未加载，请先运行『AI 审查标志』…（当前仍可移除已选标志）」且保留移除能力；signCatalog 在首次 AI 审查后缓存，后续可正常勾选。与规格 §13 简化方案一致。
2. catalog 实际 32 个 vs 规格「36」：✅ 接受。实测：backend/app/static/signs 共 36 个 SVG 资产；instruction-goggles / notice-eyewash / notice-shower / warning-confined-space 4 个未被 SIGN_GROUPS / DEFAULT_SIGN_GROUP 引用、不在 VALID_SVG_NAMES（候选库 = 32）；同时无「被引用但缺资产」的反向缺口，库一致性无裂缝。属既有数据缺口，非本分支引入，可在后续字典化时补齐。
3. 版本 Tag「V1.x · AI 优化」不区分标志审查来源：✅ 接受（规格 §13 明确本期以标志区 signs_source Tag 区分，版本 Tag 保持简单）。

## 五、整体结论

核心功能（快照 signs 持久化、normalize 规范化、AI 审查服务/端点、前端差异对比 + 人工微调、来源 Tag、catalog 中文名映射、限量约束）实现与规格一致，亲自复跑门禁全绿（后端 441 passed、前端 tsc 0 错误 + vitest 74 passed）。

但存在 2 个用户可见的边界行为违背规格 §6：① AI 优化采用会静默覆盖此前采用的标志；② 人工微调移除全部标志无法持久化「无标志」且来源 Tag 与实际展示不一致。二者均未被现有测试覆盖。

**结论：❌ 需修复**（2 处均为建议修改级、修复成本低、修复范围明确；修复并补回归测试后即可收尾）。

## 六、收尾建议（供主控向用户确认）

1. 修复第四节 2 个问题（各 1-3 行改动 + 1 个回归测试），重跑门禁：后端 `python -m pytest tests/ -q`、前端 `npx tsc -b && npx vitest run`。
2. 合并回 master：分支 13 提交、仅 TASKS.md 未提交（项目惯例）；建议 `git merge --no-ff codex/ai-sign-review` 后按项目惯例 `git finish` 推 GitHub + Gitee（推送前需用户确认）。
3. 部署 Docker：无 DB schema 变更（content JSONB 扩展，无迁移）；确认 static/signs 36 个 SVG 随镜像打包；上线后按规格 §11 手工冒烟（审查→对比→采用→版本+1；人工微调→保存→刷新保持；公开页显示快照标志与来源 Tag、无编辑入口）。
