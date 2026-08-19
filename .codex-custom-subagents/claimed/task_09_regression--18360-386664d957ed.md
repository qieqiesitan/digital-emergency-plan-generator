# Codex Custom Subagents task handoff v1

Task: task_09_regression

## 回归门禁：AI 标志审查功能全量回归

你在对 AI 标志审查功能（分支 codex/ai-sign-review，worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\ai-sign-review`）做整体回归。不要信任实现者报告，必须独立实测。

### 背景

功能已完成 9 个提交（HEAD=e22d432，父 b0a5e1e），每任务均有规格+质量双审通过：

* b4dbf07 任务1：快照 signs 优先读取
* 5157f5e/2539e11 任务2：normalize_signs 规范化
* 101c8ae/79f0f96 任务3：review_signs AI 服务
* dcbc54d/06191b3 任务4：ai-review-signs 端点
* 8d6fe18/ee59902 任务5：快照透传 signs + signs_source 回填
* e7f0ac3 任务6：前端类型 + service
* b0a5e1e 任务7：AI 审查按钮 + 差异对比 Modal
* e22d432 任务8：人工微调 + 来源 Tag + catalog

### 你的工作（在 worktree 内，只读回归，不改源码不提交）

1. **后端全量**：`cd backend && python -m pytest tests/ -q`，预期 441 passed（基线 432+任务新增；proactor closed-pipe ValueError 为既有非失败噪音，exit code 0 即可）。逐条确认新增的 AI 审查相关测试都在且通过：review_signs 解析/非法 JSON/非 list 回落、快照保存规范化、ai-review-signs 端点、catalog 断言。
2. **前端全量**：`cd frontend && npx tsc -b`（0 错误）+ `npx vitest run`（预期 74 passed，9 文件：基线 62 + riskNoticeCardSigns 12 条）。
3. **lint**：`npx eslint` 本功能 6 个改动文件（types/riskNoticeCard.ts、services/riskNoticeCardService.ts、components/enterprise/RiskNoticeCard.tsx、pages/Enterprise/RiskNoticeCardPreviewPage.tsx、utils/riskNoticeCardSigns.ts、services/riskNoticeCardService.test.ts）exit 0。
4. **SVG 资产核验**：`git show e22d432 --stat` 确认提交恰 9 清单文件；前端引用的 `/signs/{svg_name}.svg` 资产路径存在于 `frontend/public/signs/`（抽查 3-5 个 svg_name，如 warning-fire、prohibition-smoking、instruction-wear-helmet 等，确认文件在且非空）。
5. **分支历史核验**：`git log --oneline master..codex/ai-sign-review` 应为上述 9 个提交（或含计划文档提交 e105d83 共 10 个）；`git show --check` 最近 3 个提交干净；工作区仅 TASKS.md 未提交（项目惯例）。
6. **手工冒烟（可选，能起栈就做，起不来就说明原因不阻塞）**：本地起后端+前端，预览页点「AI 审查标志」→ 差异对比 → 采用 → 版本 +1、标志更新；人工微调增删 → 保存 → 刷新保持；公开页显示快照标志与来源 Tag。
7. **报告**：把回归结果追加写入 claimed 文件末尾（含每项门禁实测输出摘要 + 结论 ✅ 通过 / ❌ 发现问题带 file:line）。

### 上下文

* worktree 独立分支，只读回归，不修改文件、不提交、不部署。
* TASKS.md 永不 commit（项目惯例）。


---

## 回归结果（2026-08-16，deepseek_anthropic_worker 独立实测，只读）

task_id=task_09_regression claim_id=18360-386664d957ed attempt_id=fdff195a6cdb464d85adcc4a7482a361

### 1. 后端全量测试 ✅

`cd backend && python -m pytest tests/ -q` → **441 passed in 20.53s，exit 0**（proactor closed-pipe ValueError 为既有非失败噪音）。

新增 AI 审查相关测试逐条确认在且通过（两文件单跑 62 passed in 1.82s，exit 0）：
- review_signs 解析/非法 JSON/非 list 回落：test_review_signs_parses_suggestion（api:585）、test_review_signs_invalid_json_raises_502（api:828）、test_review_signs_non_list_fields_fall_back（api:856）
- 快照保存规范化：service test_save_snapshot_normalizes_signs_and_signs_source（:355）、test_save_snapshot_existing_with_signs_increments_and_normalizes（:391）、test_save_snapshot_signs_missing_source_defaults_rule（:438）、test_save_snapshot_without_signs_keeps_content_unchanged（:465）、test_normalize_signs_filters_and_limits（:310）、test_normalize_signs_max_total_truncates（:337）；API test_snapshot_save_with_signs（:881）、test_snapshot_save_invalid_sign_category_422（:915）、test_snapshot_save_invalid_signs_source_falls_back_rule（:939）
- ai-review-signs 端点：test_ai_review_signs_endpoint_returns_suggestion（:620）、object_not_found_404（:660）、failure_502（:671）、http_exception_passthrough（:691）、prefers_snapshot_signs（:712/:746）、malformed_suggestion_502（:776）、drops_malformed_snapshot_signs（:796）
- catalog 断言：api:646-655 全量去重（len==set 长）、三类代表（warning-fire/prohibition-smoking/notice-exit）、字段完整（category/name/svg_name）、类别映射正确

### 2. 前端全量 ✅

- `npx tsc -b` → **exit 0，0 错误**
- `npx vitest run` → **74 passed（9 文件），exit 0**；src/utils/riskNoticeCardSigns.test.ts 12 条通过（基线 62 + 12 = 74 吻合）

### 3. lint ✅

`npx eslint` 6 个改动文件（types/riskNoticeCard.ts、services/riskNoticeCardService.ts、components/enterprise/RiskNoticeCard.tsx、pages/Enterprise/RiskNoticeCardPreviewPage.tsx、utils/riskNoticeCardSigns.ts、services/riskNoticeCardService.test.ts）→ **exit 0，无输出**

### 4. SVG 资产核验 ✅（附架构说明）

- `git show e22d432 --stat` → 恰 **9 个清单文件**（613+/56-），与 handoff 一致
- 实际资产目录为 `backend/app/static/signs/`（36 个 svg），而非 `frontend/public/signs/`；前端经 vite proxy `/signs → API_TARGET`（vite.config.ts server.proxy），后端 main.py:42 挂载 `/signs → StaticFiles(static/signs)`，链路完整
- 程序化比对：规则库 risk_notice_card_data.py 引用 32 个 svg_name 全部有资产文件（缺失 0）；前端 src 引用 5 个全部覆盖；36 个资产无空文件
- 抽查非空：warning-fire.svg(398B)、prohibition-smoking.svg(479B)、notice-exit.svg(493B)、warning-fall.svg(495B)、warning-electric.svg(256B)、instruction-helmet.svg(274B) 均存在且非空
- 注意：handoff 示例名 instruction-wear-helmet / warning-electric-shock 在库中实际命名为 instruction-helmet / warning-electric（以代码真实引用为准，无缺失）

### 5. 分支历史核验 ✅

- `git log --oneline master..codex/ai-sign-review` 共 13 个提交：e105d83（计划文档）+ 12 个功能/修复提交（b4dbf07、5157f5e、2539e11、101c8ae、79f0f96、dcbc54d、06191b3、8d6fe18、ee59902、e7f0ac3、b0a5e1e、e22d432），消息与 handoff 逐条吻合（handoff 文字「9 个提交」与实际 12 个功能提交有出入，以实际提交为准）
- HEAD=e22d432，父=b0a5e1e，未 amend
- `git show --check` e22d432 / b0a5e1e / e7f0ac3 三个最近提交均干净（exit 0）
- 工作区仅 TASKS.md 未提交（项目惯例）

### 6. 手工冒烟 ✅（API 级；UI 起栈说明见下）

用进程内 TestClient + dev 库（localhost:5438）独立实测（登录 test@test.com）：
- 列表端点：企业 94804158-… 下 13 张卡全部带 signs（7/4/1 项），快照透传生效 ✅
- 详情端点：signs_source=rule、signs 7 项，字段完整（category/name/svg_name）✅
- SVG 服务：GET /signs/warning-fire.svg → 200，398 bytes ✅
- POST /ai-review-signs → 500「AI 配置密钥解密失败」：dev 库系统 AI 配置密钥与本地环境不匹配（既有 llm_client 解密路径），非本功能回归；该端点正常/异常路径均有测试覆盖（见第 1 项）
- 未执行完整 UI 冒烟（起 vite + 浏览器 + 真实 LLM key 成本高且 AI 密钥环境不可用）；「采用 → 版本+1 → 保存刷新保持」保存路径由后端 test_save_snapshot_* 覆盖

### 结论 ✅ 通过

全部 6 项门禁独立实测通过，未发现功能性问题。两点说明：SVG 资产目录位置与 handoff 描述不同（后端 static 而非 frontend public），但引用链路完整、无缺失资产；AI 端点冒烟受环境密钥限制返回 500 属既有行为，不阻塞。
