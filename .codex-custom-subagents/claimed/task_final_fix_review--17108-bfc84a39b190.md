# Codex Custom Subagents task handoff v1

Task: task_final_fix_review

## 复审：最终审查修复提交 fe0ac28（分支 codex/ai-sign-review）

worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`（分支 codex/ai-sign-review，HEAD=fe0ac28，父 e22d432）。

最终审查（claim 26848-190298fc572e）发现 2 个建议修改级问题，修复代理提交 fe0ac28（6 文件 138+/5-）。你独立复审该修复是否真正解决两个问题、是否符合原审查建议、门禁是否全绿。只读审查：不修改文件、不提交、不部署。

### 复审要点

**问题 1（前端覆盖标志）**：`frontend\src\pages\Enterprise\RiskNoticeCardPreviewPage.tsx` adoptOptimized 现调用 `mergeOptimizedContent(compare.optimized, card.signs, card.signs_source)` 组装完整 content 再 saveSnapshot；`frontend\src\utils\riskNoticeCardSigns.ts` 新增 mergeOptimizedContent（`{...optimized, signs, signs_source: signs_source ?? "rule"}`）。
- 核对：采用 AI 优化后快照仍含当前展示的标志与来源；`!card` 守卫已加；signs_source 缺失回落 "rule"。
- 核对单测：`frontend\src\utils\riskNoticeCardSigns.test.ts` 是否覆盖「右栏原值保留 + 自定义 signs + 来源透传」与「来源缺失回落 rule」。

**问题 2（显式空标志）**：`backend\app\services\risk_notice_card_service.py` snapshot_signs 改为 `content is not None and content.get("signs") is not None`。
- 核对：`signs: []` + `signs_source="manual"` 快照 → build_card_data 返回 signs=[] 且 signs_source="manual"（不回退规则）；无 signs 键仍回退规则；ai-review-signs 端点 current_signs 为 []（AI 看到空当前标志）。
- 核对回归测试：`backend\tests\test_risk_notice_card_service.py`（+35）与 `backend\tests\test_risk_notice_card_api.py`（+26）新增用例是否真实覆盖上述行为，而非仅装饰性断言。

**门禁实测（必须亲自跑）**：
* `cd backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -q` 全绿
* `cd backend && python -m pytest tests/ -q` → 443 passed 预期（exit 0；proactor closed-pipe 为既有噪音）
* `cd frontend && npx tsc -b` → 0 错误
* `cd frontend && npx vitest run` → 76 passed 预期
* `npx eslint` 6 个改动文件 exit 0
* `git show --check fe0ac28` 干净；提交恰 6 清单文件、父=e22d432、未 amend；工作区仅 TASKS.md 未提交；行尾 CRLF 无 BOM

### 报告

把复审报告追加写入 claimed 文件末尾：两个问题逐一结论（✅ 已解决 / ❌ 仍有问题带 file:line）、新增测试有效性评估、门禁证据、整体结论 ✅ 可收尾 / ❌ 需再修。

### 上下文

* 最终审查报告全文在 `.codex-custom-subagents\claimed\task_final_review--26848-190298fc572e.md`（第四节问题清单、第五节收尾建议）。
* TASKS.md 永不 commit（项目惯例）。

---

# 修复复审报告（task_final_fix_review，claim 17108-bfc84a39b190，attempt 9d2e9f0961b34b9c85eb0fa62c818d70）

> 复审人：deepseek_anthropic_worker（deepseek-v4-flash）｜日期：2026-08-16｜方式：只读独立复审 fe0ac28，逐条读码 + 亲自复跑门禁，不采信中间报告。

## 一、问题 1（AI 优化采用覆盖已采用标志）— ✅ 已解决

- 前端采用路径：`frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx:713` 增加 `!card` 守卫；`:718-724` 改为 `mergeOptimizedContent(compare.optimized, card.signs, card.signs_source)` 组装完整 content 后再 `saveSnapshot`，不再直接保存裸 `compare.optimized`。`card` 来自 `useQuery`（:638），守卫前为 `CardData | undefined`，guard 合法。
- 合并函数：`frontend/src/utils/riskNoticeCardSigns.ts:105-114` `mergeOptimizedContent` 返回 `{...optimized, signs, signs_source: signs_source ?? "rule"}`——右栏四块原值保留，signs/signs_source 显式覆盖，缺 source 回落 "rule"（与后端 `(content or {}).get("signs_source") or "rule"` 语义一致）。
- 类型核对：`compare.optimized` 为 `RightColumn`（AiCompareResult，:203-207）；`card.signs: SignItem[]`、`card.signs_source?: "rule"|"ai"|"manual"` 与函数签名精确匹配；返回值可赋给 `saveSnapshot` 的 `RightColumn` 参数，tsc 实测 0 错误。
- 后端兜底链路：save_snapshot 收到 list 类型 signs 即 normalize 后持久化（risk_notice_card_service.py:305-311），signs_source 合法值原样保留，采用后的快照不再被 RightColumn 缺省空值覆盖。

## 二、问题 2（显式空标志无法持久化）— ✅ 已解决

- `backend/app/services/risk_notice_card_service.py:171-177`：`snapshot_signs` 改为 `content is not None and content.get("signs") is not None`——显式 `signs: []` 返回 `[]`（不回退规则），无 signs 键返回 None（回退 `match_signs`），语义区分正确。
- 读链路：`build_card_data`（:254-257）`cached_signs is not None` 时直接采用快照值，空列表不回退规则；signs_source 从 content 回填 "manual"。
- 写链路：`save_snapshot`（:302-311）对 list 类型（含空列表）normalize 后持久化，signs_source="manual" 合法保留。
- AI 端点：`risk_notice_card.py:311-314` `current_signs = normalize_signs(cached_signs if cached_signs is not None else match_signs(...))`——快照显式空 → `[]`，AI 看到空当前标志，与卡片展示一致。

## 三、新增测试有效性评估 — ✅ 真实覆盖，非装饰性

### 后端 API（+26）
`test_snapshot_save_persists_explicit_empty_signs`（test_risk_notice_card_api.py:915-940）：真实 PUT 快照 `signs: [] + signs_source: "manual"`，断言落库 `content["signs"] == []` 且 `signs_source == "manual"`——直接验证写端「显式空 + 来源保留」。

### 后端服务（+35）
`test_build_card_data_persists_explicit_empty_snapshot_signs`（test_risk_notice_card_service.py:258-291）：构造「火灾」事故类型（规则会产出当心火灾/禁止烟火）+ 快照 `signs: [] + manual`，断言 `card.signs == []` 且 `card.signs_source == "manual"`——用「规则必有输出」的场景验证不回退规则、不丢来源，非装饰性断言。

### 前端单测（+41）
`mergeOptimizedContent` 两个用例（riskNoticeCardSigns.test.ts:135-174）：① optimized 自带缺省 `signs: [] / signs_source: null` 时被自定义 signs 与来源覆盖（toEqual 全量断言）；② signs_source 缺失回落 "rule"。正是原审查建议的「右栏原值保留 + 自定义 signs + 来源透传」与「来源缺失回落」两点。

### 覆盖缺口（仅供参考，不阻塞）
- ai-review-signs 端点「快照显式空 → current_signs=[]」未单独新增端点级断言，但该分支与 build_card_data 共用同一 `snapshot_signs` 函数（服务级已直测），端点既有 `test_ai_review_signs_prefers_snapshot_signs` 覆盖快照优先分支，代码路径贯通，可接受。
- adoptOptimized 组件处理器本身无端到端单测（React 组件未覆盖），但合并纯函数已直测 + tsc 编译通过 + 后端保存/读取链实测，足够。

## 四、门禁实测证据（全部亲自复跑）

| 门禁 | 命令 | 结果 |
|------|------|------|
| 后端重点文件 | `python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -q` | 64 passed，exit 0 |
| 后端全量 | `python -m pytest tests/ -q` | 443 passed，exit 0（仅既有 proactor closed-pipe 噪音） |
| 前端类型 | `npx tsc -b` | 0 错误，exit 0 |
| 前端单测 | `npx vitest run` | 9 文件 76 passed（riskNoticeCardSigns 14 含 2 个新增） |
| ESLint | `npx eslint`（3 个前端改动文件；后端 3 个为 .py 不属 eslint 范围） | exit 0 |
| 提交卫生 | `git show --check fe0ac28` | 干净，exit 0 |
| 提交结构 | `git diff-tree --name-only -r` | 恰 6 文件（后端服务 + 3 测试 + 2 前端源/测试），与声明一致 |
| 父提交 | `git rev-parse fe0ac28^` | e22d432c4a591439cdd02d6b54ce727ca928ffc3，未 merge、单父 |
| 工作区 | `git status --short` | 仅 `M TASKS.md`（项目惯例，永不 commit） |
| 行尾/BOM | 6 文件逐字节检查 | 全部 CRLF、无 BOM、无 LF-only 行 |

## 五、整体结论 — ✅ 可收尾

原最终审查的 2 个「建议修改」级问题均被 fe0ac28 实质性修复：问题 1 前端采用路径保留当前展示标志与来源（含 `!card` 守卫、source 缺失回落 rule）；问题 2 后端以「无键 vs 显式空」区分回退规则与空标志状态，写/读/AI 端点三链路一致。新增测试（后端 2 个、前端 2 个）均为真实行为断言，非装饰性。全部门禁亲自复跑全绿：后端 443 passed、前端 tsc 0 错误 + vitest 76 passed、eslint exit 0、提交卫生与格式符合要求。分支可收尾，建议按原报告第五节收尾建议执行（合并回 master 前向用户确认、部署 Docker 后手工冒烟）。
