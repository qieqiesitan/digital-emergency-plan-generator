# 报告工作台设计方案（风险评估 / 应急资源调查报告）

日期：2026-09-03
状态：已获用户逐节批准
范围：桌面 Web 端（预案页面保持对外行为不变；移动端不在本轮范围）

## 1. 背景与目标

风险评估报告、应急资源调查报告此前是各自独立的简单页面：左侧章节列表 + 右侧
textarea（markdown 源码编辑），缺少预案编辑器具备的富文本所见即所得、单章 AI
生成/重新生成、AI 审查与修订、创作风格、版本快照等能力。

目标：让两份报告获得与应急预案一致的「章节化文档工作台」体验，并共用一套代码
（一个工作台组件 + 各自 adapter），避免再次出现 risk/resource 两份逻辑复制导致
漂移的问题（如 2026-09-03 修复的参数顺序 bug 即复制粘贴不一致所致）。

## 2. 非目标

- 不做预案特有语义：模板章节树、自动编号、附图管理、样章确认、预案状态流转。
- 不动预案编辑器对外行为（内部允许为复用而抽取编辑器内核）。
- 不动移动端报告页（后续另行评估）。
- 不把预案编辑器迁移到新工作台（后续可选）。

## 3. 总体架构

三层：

1. 后端补齐「报告章节级」能力：risk_assessment 与 resource_investigation 各自
   路由，内部共享同一服务层实现（单章生成函数由现有全量 generate 循环抽出，
   全量与单章只差“跑几章”）。
2. 前端新建通用 `ReportWorkspace` 工作台组件，两个报告 Tab 变薄壳，各自提供
   `ReportAdapter`。
3. 复用预案已有的可复用 UI 组件；将预案富文本编辑器内核抽为通用 `TiptapEditor`
   （预案组件改为内部使用它，行为不变）。

## 4. 后端接口契约

以下以 risk-assessment 为例，resource-investigation 对称提供（路径前缀：
`/api/v1/enterprises/{enterprise_id}/risk-assessment`）。

| 端点 | 作用 |
| --- | --- |
| `GET /chapters`（已有） | 章节定义 [{key, title}] |
| `GET /`（已有） | 报告详情（含 content、summary.chapters、style_preference） |
| `POST /generate`（已有） | 全量逐章生成（SSE） |
| `POST /generate/section` | 单章生成（SSE；body `{chapter_key, custom_instruction?}`） |
| `POST /sections/{key}/regenerate` | 单章重新生成（SSE） |
| `PUT /sections/{key}` | 单章内容保存（更新草稿 summary.chapters 中对应章节） |
| `POST /review` | AI 合规审查（body `{scope: "all" \| chapter_key}`），返回 issues |
| `POST /review/apply` | 按 diff 确认的修订应用（body `{changes:[{section_key, original, revised}]}`） |
| `GET /style` / `PUT /style` | 报告级创作风格偏好 |
| `POST /merge`、`GET /preview`、`GET /export`、版本接口（已有） | 合并定稿/预览/导出/版本快照 |

关键实现点：

- 单章生成复用既有 `build_chapter_prompt`、法规注入、完整数据注入与 LLM 流式
  空结果守卫；SSE 事件协议与现有 generate 一致（progress/chunk/section_done/
  error）。
- 审查端点的判定口径基于报告章节定义与法规上下文（本轮已修复法规注入，审查
  可复用同一 RegulationContextBuilder 检索结果）。
- 风格指令生成时拼入 user prompt（复用 `generate_style_instruction`）。
- 报告详情接口返回 style_preference，供工作台初始化风格面板。

## 5. 数据模型变更

- `risk_assessment_reports`、`resource_investigation_reports` 新增
  `style_preference JSONB NOT NULL DEFAULT '{}'`。
- 以幂等迁移脚本 `db_migration_*.sql` 提供，公司库升级时自动应用。
- 草稿模型保持不变：全量/单章生成结果写入报告行 `summary.chapters`
  （[{key, title, content}]），状态 draft；点「合并生成完整报告」后才定稿为
  completed。章节级编辑/保存作用于草稿 chapters。

## 6. 前端结构与复用边界

```
components/report/
  ReportWorkspace.tsx       通用工作台（顶部工具栏/左侧章节/右侧编辑器/全量进度）
  TiptapEditor.tsx          从预案 RichTextEditor 抽出的编辑器内核
  ReportChapterActions.tsx  单章生成/重新生成按钮（交互仿 AIGenerateButton）
  ReviewDrawer.tsx          审查面板（复用 DiffPreviewModal）
services/reportAdapters.ts  risk/resource 两个 adapter（同一接口）
types/reportWorkspace.ts    ReportChapter / ReportDocument / ReportAdapter 等类型
```

`ReportAdapter` 接口（抽象，防两份页面逻辑漂移）：

```
load(): ReportDocument
saveChapter(key, content): void
generateChapter(key, customInstruction?, onEvent): AbortController
regenerateChapter(key, customInstruction?, onEvent): AbortController
generateAll(onEvent): AbortController
review(scope, onEvent): Promise<issues>
applyReview(changes): void
getStyle() / saveStyle(style): void
merge(chapters): void
exportUrl / versions 操作
```

复用组件清单：

- 编辑器内核（TipTap：StarterKit + 表格 + 对齐 + 占位）→ 抽 `TiptapEditor`
- `MermaidRenderer`、`DiffPreviewModal`、`StylePanel`、AI 未配置引导
- 服务端既有 `md_to_html` / markdown-it 渲染管线

不复用（plan 绑定太深，报告侧新写但交互同款）：

- 预案 `AIGenerateButton`（内部直接调 `/plans/{id}/...`）
- 预案 `SectionTree`（模板树语义）

`RiskAssessmentTab` / `ResourceInvestigationTab` 改为薄壳：各自提供 adapter 与
元信息（标题/空态文案），主体渲染 `ReportWorkspace`。

## 7. 数据流

1. 工作台挂载 → adapter.load() → 左侧章节列表 + 右侧编辑器（若已有草稿 chapters
   则回填；否则空）。
2. 全量/单章生成 → SSE chunk 流式写入当前章节（所见即所得），失败章节计入列表
   可重试。
3. 编辑器编辑 → 1.5s 防抖自动保存章节（PUT /sections/{key}），状态栏显示保存
   状态。
4. AI 审查 → issues 列表 → 逐条 diff 预览 → 确认后 apply。
5. 「合并生成完整报告」→ merge（沿用现有模型）→ 预览/导出/版本。

## 8. 错误处理

- AI 调用：沿用流式空结果守卫（自动重试 1 次，仍空则错误事件计入失败章节）；
  AI 未配置/密钥问题复用 `aiErrorDisplay` / `AiNotConfiguredHint` 引导。
- 章节保存失败不打断编辑，状态栏提示“保存失败，点击重试”，以编辑器内存内容为
  准。
- 审查失败/法规检索为空给出可理解文案，不白屏。
- 离开页面前若存在未保存内容，提示确认。

## 9. 测试策略（TDD）

后端：

- 单章生成/重生成端点 SSE 事件序列；章节保存；审查端点；风格注入到 prompt；
  迁移脚本可重入。
- 回归：报告相关测试 + 预案侧测试（防共享改动破坏预案）。

前端：

- `reportAdapters` 两 adapter 行为一致性；`ReportWorkspace` 状态流转（加载/
  生成中/失败/编辑）；`TiptapEditor` 渲染与预案一致性。
- vitest 全量 + `tsc -b`。

手工验收：

- 预案编辑器回归（生成/编辑/保存/审查/导出）。
- 两份报告全流程走查（全量生成、单章生成、编辑保存、审查修订、风格、合并、
  预览、导出 Word、版本）。

## 10. 交付与实施顺序

1. TiptapEditor 抽取 + 预案 RichTextEditor 内部改用（预案回归）。
2. 后端：迁移加列 + 单章/保存/审查/风格端点 + 单测。
3. 前端：类型与 adapter → ReportWorkspace → ReportChapterActions/ReviewDrawer →
   两个 Tab 接入。
4. 端到端验证 + 重建 dist 同步宿主与 8082 + 后端重启。

## 11. 已确认决策

- 风格偏好存报告表（`style_preference` 列），不做全局共享配置。
- 草稿阶段章节内容存 `summary.chapters`，不新增独立章节表；merge 沿用现有模型。
- 富文本内核抽取为 `TiptapEditor`，预案编辑器对外行为不变（用户已批准）。
- 方案 A：组件级复用 + 报告工作台（用户选定）。
