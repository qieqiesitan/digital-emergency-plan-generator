# AI 审查安全标志 — 设计规格

> **日期**：2026-08-15 | **状态**：设计中 | **依赖**：风险告知卡（已上线）、AI 服务（DeepSeek）、快照机制

---

## 1. 概述

在风险告知卡的安全标志生成链路中新增「AI 审查」能力：规则匹配（GB 6441 事故类型 → 标志组）完成后，由 AI 结合风险点的**实际场景**（名称、类别、位置、事件详情）审查标志是否合理，给出「建议删除 / 建议增加 + 理由」的差异建议；用户对比确认后保存快照。同时提供**人工微调**：安全员可直接从 36 个国标标志库增删标志并保存。

核心原则：**规则保底、AI 纠偏、人工把关**。规则结果始终是默认基线；AI 审查与人工微调的结果都存入快照（版本 +1），可审计、可回看，不污染风险源数据。

---

## 2. 背景与问题

当前标志完全由 `SIGN_GROUPS`（20 类事故 → 标志组）规则匹配，粗粒度问题已多次暴露：

- 餐具清洗区（事故类型=灼烫，热水烫伤）被自动匹配「洗眼台」（化学灼伤专用设施）
- 会议室（事故类型=自定义「踩踏/人员伤害」）走兜底组被匹配「必须戴安全帽」「当心机械伤人」
- 锅炉爆炸被匹配「必须消除静电」（锅炉爆炸主因是超压/缺水，与静电无关）

规则无法感知具体场景（会议室 vs 车间、热烫伤 vs 化学灼伤），AI 审查是低成本高价值的补充。

---

## 3. 需求决策（用户已逐项确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 触发方式 | 单张卡手动触发（预览页「AI 审查标志」按钮） |
| 2 | AI 上下文 | 风险点完整上下文：名称/类别/位置/事件详情（事故类型/触发条件/后果）+ 当前标志 + 36 候选库 |
| 3 | 确认与持久化 | 差异对比确认后保存快照（版本 +1，复用现有快照机制） |
| 4 | 人工微调 | 本期包含：卡片标志可手动增删保存 |
| 5 | 实现方案 | 方案 1：后端 AI 审查服务 + 快照 content 扩展 |

---

## 4. 现状基础（可复用组件）

| 组件 | 现状 |
|------|------|
| `risk_notice_card_ai.py` | 已有 `optimize_right_column`（右栏文案 AI 优化）：llm_text_completion + _parse_optimized_json + HTTPException 透传 + logger |
| `risk_notice_cards` 快照表 | content JSONB（右栏四块），version 递增，object_id 唯一 |
| `match_signs` | 规则标志匹配（SIGN_GROUPS + EXTRA_SIGN_GROUPS + 默认组），每类最多 2 个、总数最多 8 个 |
| 36 个 SVG 资产 | `backend/app/static/signs/`，GB 2894 合规；`SIGN_GROUPS` 引用其 svg_name |
| 前端预览页 | 已有「AI 优化」对比 Modal、版本 Tag、快照保存流程 |

---

## 5. 架构与数据流

```
规则 match_signs / 快照标志（当前基线）
  → 预览页「AI 审查标志」按钮
  → POST /ai-review-signs（后端组装上下文 → DeepSeek → 差异建议，无副作用）
  → 前端差异对比 Modal（删除划线红 / 增加绿 / 保留灰 + 理由）
  → 「采用建议并保存快照」→ PUT /snapshot（content 含完整右栏 + signs + signs_source=ai）
  → 卡片刷新、版本 +1

人工微调：标志区「编辑」→ 从 36 库增删 → PUT /snapshot（signs_source=manual）→ 版本 +1
```

快照消费：`build_card_data` 读快照时支持 `signs` 字段——有快照标志用快照，否则用规则 `match_signs`。

---

## 6. 数据模型（无数据库变更）

复用 `risk_notice_cards.content`（JSONB），结构扩展：

```json
{
  "hazard_description": "...",
  "accident_types": ["..."],
  "control_measures": ["..."],
  "emergency_measures": ["..."],
  "signs": [{"category": "warning", "name": "当心爆炸", "svg_name": "warning-explosion"}],
  "signs_source": "rule | ai | manual"
}
```

要点：
- `signs`：最终标志列表（规则 / AI 审查确认 / 人工微调，三者的结果都落这里）
- `signs_source`：标志来源，前端据此显示「AI 审查 / 人工调整」小 Tag；缺省 `rule`
- **完整快照**：任何保存（AI 优化文案 / AI 审查标志 / 人工微调）都写入当前展示的完整内容（右栏 + 标志），版本递增互不覆盖
- 旧快照无 `signs` → `build_card_data` 回退规则标志（向后兼容）

---

## 7. API 设计

### 7.1 新增：POST `/enterprises/{eid}/risk-notice-cards/{oid}/ai-review-signs`

鉴权 + 企业/风险点归属校验（404 对齐现有）。无副作用。

响应：

```json
{
  "original_signs": [{"category": "...", "name": "...", "svg_name": "..."}],
  "suggestion": {
    "remove": [{"category": "...", "name": "...", "svg_name": "..."}],
    "add": [{"category": "...", "name": "...", "svg_name": "..."}],
    "reasons": [{"sign_name": "必须戴安全帽", "reason": "会议室为非生产区域，无坠落物/机械伤害风险"}]
  }
}
```

### 7.2 扩展：PUT `/enterprises/{eid}/risk-notice-cards/{oid}/snapshot`

`SnapshotSaveRequest.content` 增加可选 `signs: list[SignItem]` 与 `signs_source: str`。保存逻辑不变（版本 +1），人工微调共用此端点。

### 7.3 后端规范化（防 AI 乱来）

- AI 建议的标志不在 36 库 → 丢弃
- 建议 remove 不在当前标志 → 忽略
- 强制去重、按 警告→禁止→指令→提示 排序、每类最多 2 个、总数最多 8 个

---

## 8. AI 提示词与约束

system：「你是安全生产专家，熟悉 GB 2894-2025《安全色和安全标志》与 GB 6441-1986 事故分类。根据风险点的实际场景，审查告知卡上的安全标志是否合理，给出增删建议。」

user 内容：
1. 风险点完整上下文：企业名、风险点名称/类别/位置、事件列表（事故类型/触发条件/可能后果）
2. 当前标志列表（category/name）
3. 候选库：36 个国标标志（category/name/svg_name），明确「只能从这些中选择」
4. 输出要求：严格 JSON `{remove: [svg_name], add: [svg_name], reasons: [{sign_name, reason}]}`，中文、理由具体

硬约束（提示词 + 后端双保险）：只能从库选；remove 必须在当前标志、add 不得重复；每类 ≤2、总数 ≤8；后端规范化兜底。

容错：复用 `_parse_optimized_json`；AI 返回格式异常 → 502 + logger，不阻塞规则结果。

---

## 9. 前端交互

### 9.1 预览页工具栏

新增「AI 审查标志」按钮（与「AI 优化」并列），loading 防重入。

### 9.2 AI 审查差异对比 Modal

- 三组展示：建议删除（红色删除线 + 理由）、建议增加（绿色 + 理由）、保留（灰）
- 底部「采用建议并保存快照（版本 +1）」/「放弃，保留原版」
- 采用后 PUT 快照 → refetch → 标志区更新、版本 +1；失败提示「AI 审查失败，已保留原版」

### 9.3 人工微调

- 标志区「编辑」入口 → 编辑模式：当前标志可移除 + 36 候选标志网格勾选添加（每类 ≤2、总数 ≤8，超限即时提示）
- 保存：PUT 快照（signs_source=manual）→ 版本 +1；取消不保存

### 9.4 来源标记

标志区根据 `signs_source` 显示小 Tag：`ai` →「AI 审查」、`manual` →「人工调整」，规则结果不显示。

---

## 10. 错误处理

| 场景 | 行为 |
|------|------|
| 风险点不存在/无权限 | 404（对齐现有） |
| AI 失败/超时/格式异常 | 502「AI 审查失败，已保留原版」；HTTPException 透传；logger 记录 |
| AI 建议非法/超量 | 后端规范化静默丢弃/截断，不报错 |
| 快照保存失败 | 前端提示「保存失败，请重试」 |
| 人工微调超限 | 前端即时提示 |
| 旧快照无 signs | 回退规则标志 |

---

## 11. 测试计划

**后端**
- `review_signs` 服务：mock AI 合法/非法 JSON、字段缺失回落
- 规范化：非法标志丢弃、去重、排序、限量
- API：鉴权 / 404 / 成功响应结构 / AI 失败 502
- 快照：带 signs 存取；build_card_data 快照优先用 signs；旧快照兼容回退

**前端**
- service `aiReviewSigns` 调用与解包
- tsc + vitest 全绿（现有 61+ 用例无回归）

**手工冒烟**：审查 → 对比 → 采用 → 版本 +1 标志更新；人工微调保存刷新保持；公开页显示快照标志。

---

## 12. 范围与里程碑

**本期包含**：`review_signs` AI 服务、`ai-review-signs` 端点、快照 content 扩展（signs/signs_source）、前端「AI 审查标志」按钮 + 差异对比 Modal、人工微调编辑、来源 Tag、测试。

**本期不含**：批量 AI 审查（后续可加）、标志历史版本回滚（快照目前只存最新一条）、AI 对标志图形的自动绘制。

**里程碑**：① 快照 content 扩展 + build_card_data 兼容 → ② review_signs 服务 + 规范化 → ③ ai-review-signs 端点 → ④ 前端差异对比 + 人工微调 → ⑤ 测试与回归 → ⑥ 部署。

---

## 13. 开放问题

- AI 审查与「AI 优化」按钮同时存在，快照版本 Tag 文案（「V1.x · AI 优化」）是否需区分标志审查来源——本期通过标志区 `signs_source` Tag 区分，版本 Tag 保持简单。
- 人工微调编辑模式下候选库 36 个标志的展示效率（分页/搜索）——本期用网格勾选即可，如数量大再优化。
