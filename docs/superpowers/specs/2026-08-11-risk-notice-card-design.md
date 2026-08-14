# 风险告知卡自动生成 — 设计规格

> **日期**：2026-08-11 | **状态**：设计中 | **依赖**：风险管理模块（风险分区/风险点/风险事件/管控措施）、docx 导出管线、AI 服务（DeepSeek）

---

## 1. 概述

在企业风险管理模块基础上新增「风险告知卡」能力：按**风险点（RiskObject）**自动生成符合监管要求的告知卡，支持网页预览、一键导出 Word（每卡一页 A4 + 二维码）、单卡 AI 优化（对比确认后存快照）以及现场扫码查看的公开只读页面。

硬性约束：**卡片必须印安全标志图形，且完全符合 GB 2894-2025《安全色和安全标志》**（2026-03-01 已实施）。标志图形按国标规范自绘 SVG 核心集，依据 GB 6441-1986 事故类型自动匹配。

全部生成逻辑为**规则为主（零 LLM 默认路径）+ AI 可选**：不点「AI 优化」时，卡片完全由库内风险数据 + 规则模板组装，稳定可审计。

---

## 2. 需求决策（用户已逐项确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 卡片粒度 | 按风险点（RiskObject）出卡，一张卡一页 A4 |
| 2 | 输出形式 | 网页预览 + 一键导出 Word（批量）；每卡一页，卡片右上角印二维码 |
| 3 | 生成方式 | 规则为主 + AI 可选（单卡「AI 优化」按钮） |
| 4 | 入口 | 风险管理 Tab 顶部「风险告知卡」按钮 → 卡片管理页 |
| 5 | 安全标志 | 必须印，且完全符合 GB 2894-2025；按国标自绘 SVG 核心集 |
| 6 | 责任信息 | 风险点新增「责任单位 / 责任人 / 联系电话」三字段，留空兜底企业安全负责人 |
| 7 | 应急处置 | 库内 `emergency` 类管控措施优先 + 事故类型标准模板兜底 |
| 8 | AI 优化结果 | 存「卡片快照表」`risk_notice_cards`（版本号 +1，不污染风险源数据） |
| 9 | 二维码指向 | 公开只读卡片页（URL 带随机 token 防遍历，无需登录） |
| 10 | 版式 | 左右排版 v5：左栏键值表格 + 安全标志区（深色标题条 + 56px 标志），右栏四信息块，标题=「{风险点名}安全风险告知卡」 |

---

## 3. 现状基础

| 组件 | 现状 |
|------|------|
| `risk_objects` | 风险点：name/category/location/zone_id/floor_id/is_risk_point 等；**无责任单位/责任人/电话、无编号字段** |
| `risk_events` | 风险事件：accident_type（GB 6441-1986）、trigger_conditions、consequences、risk_level、risk_score、method_type |
| `risk_measures` | 管控措施：measure_category ∈ `engineering\|management\|ppe\|emergency`、description、responsible_person、status |
| `risk_zones` | 分区：name、max_risk_level、effective_color（四色） |
| `Enterprise` | name/address/safety_officer/safety_officer_phone/credit_code 等（卡片抬头/兜底） |
| 四色等级 | 重大红 #ff4d4f / 较大橙 #fa8c16 / 一般黄 #fadb14 / 低绿 #52c41a（前后端一致；来自风险分级管控体系） |
| docx 导出 | `docx_template.py`（预案用）+ `/export/download/{file_key}`（EXPORT_DIR）；SVG→PNG 能力在 `mermaid_renderer` |
| AI 服务 | `risk_ai_service` 已有 DeepSeek 配置与调用模式 |
| 前端 | Ant Design + React Router；风险管理 Tab（`RiskManagementTab`）、风险对象表单（`RiskObjectForm` 520px Drawer）、移动端 /m |

**两个体系区分（重要）**：风险分级管控四色（红橙黄蓝）用于等级色块；GB 2894-2025 安全色（红黄蓝绿）仅用于安全标志图形，二者不混用。

---

## 4. 卡片版式规范（v5 + 二维码右上角，已确认）

**头部**：企业名称（小字居中）→ 主标题「{风险点名称}安全风险告知卡」（18px 800 加粗、字距 2px）→ 底部 3px 风险等级色装饰线；**二维码固定在头部右上角**（34px，带「扫码查看」小字），标题保持居中。

**主体左右分栏**：

- 左栏（40%，浅灰底 #fbfbfb，右分割线）：
  - 等级色带（全宽、白字、字距 6px，如「重大风险」）
  - 键值表格（6 行）：风险点名称 / 风险点编号 / 风险等级 / 责任单位 / 责任人 / 联系电话（标签列 62px 灰底，值列白底加粗）
  - 「安全标志」深色标题条（#434343 白字、字距 8px）+ 标志区（白底，3 个 56px 标志横排，各带名称小字）
- 右栏（60%）：四个信息块（深色标题条 + 红点 + 白底正文）：
  - 主要危险因素描述（风险事件 trigger_conditions + description 归并）
  - 主要事故类型（accident_type 去重，标注「GB 6441 事故类别」）
  - 主要风险控制措施（engineering / management / ppe 类措施归并，① ② ③ 编号）
  - 应急处置措施（emergency 类措施优先 + 模板兜底）

**页脚**：签发单位（取企业名称；无则省略）｜ 编制日期 ｜ 版本（V1.0 规则基线 / V1.1+ AI 快照）。

**公开移动端版式**：纵向堆叠——信息网格（两列）→ 安全标志（48px）→ 四个信息块 → 页脚（签发/版本）→ 底部提示条「公开只读页面 · 数据来自系统快照 · 无需登录」。

---

## 5. 架构与组件

```
frontend/
  src/pages/Enterprise/RiskNoticeCardPage.tsx   卡片管理页（列表/筛选/勾选/批量导出/单卡入口）
  src/components/enterprise/RiskNoticeCard.tsx  卡片渲染组件（预览与公开页共用，内联 SVG）
  src/pages/PublicRiskNoticePage.tsx            公开只读页（路由 /r/:token，无登录守卫）
  src/assets/signs/*.svg                        国标标志库（约 36 个 SVG）
  src/types/riskNoticeCard.ts                   类型定义
  src/services/riskNoticeCardService.ts         API 封装

backend/
  app/services/risk_notice_card_service.py      CardData 组装（规则）、标志映射、模板兜底
  app/services/risk_notice_card_docx.py         Word 渲染（A4 每卡一页、二维码、SVG→PNG）
  app/routers/risk_notice_card.py               6 个鉴权端点 + 1 个公开只读端点（见 §9）
  app/routers/public_risk_notice.py             公开只读数据端点（无鉴权，token 校验）
  app/schemas/risk_notice_card.py               CardSummary / CardData / 请求响应模型
  db_migration_risk_notice_card.sql             字段 + 快照表迁移
```

数据流：管理页列表（摘要 API）→ 勾选 → 单卡预览（详情 API）→ 导出（后端逐卡组装 + docx → `/export/download/{file_key}`）→ AI 优化（生成对比 → 确认 PUT 快照）→ 现场扫码（`/r/{token}` → 公开 API → 卡片页）。

---

## 6. 数据模型

### 6.1 `risk_objects` 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `responsible_unit` | String(255) NULL | 责任单位/部门（卡片左栏） |
| `responsible_person` | String(100) NULL | 责任人 |
| `contact_phone` | String(50) NULL | 联系电话 |
| `public_token` | String(64) UNIQUE NOT NULL | 公开页 token，迁移时对存量行生成随机值；可重置 |

生成卡片时取值优先级：对象字段 → 企业 `safety_officer` / `safety_officer_phone` 兜底；响应含 `fallback_used` 标记。

### 6.2 `risk_notice_cards` 快照表（AI 优化结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `enterprise_id` | UUID FK enterprises CASCADE | |
| `object_id` | UUID FK risk_objects CASCADE | 一对象最多一条最新快照（唯一约束） |
| `version` | Integer NOT NULL | 1 起；展示 V1.{version}，规则基线 V1.0 不落库 |
| `content` | JSONB NOT NULL | 右栏四块完整副本（hazard_description / accident_types / control_measures / emergency_measures）+ 保存时刻左栏字段副本（等级/责任单位/责任人/电话）；AI 优化只改写其中三块，事故类型不参与优化 |
| `source` | String(20) NOT NULL | 固定 `ai` |
| `created_by` | UUID FK users | |
| `created_at` / `updated_at` | DateTime | |

快照优先规则：预览/导出/公开页**有快照用快照**（含左栏副本），无快照实时组装。风险源数据变更后（`risk_objects.updated_at` / 事件 / 措施晚于快照）卡片标记「数据已变更」提示。

### 6.3 风险点编号

不新增持久化编号字段。卡片编号为展示用序号：按企业内风险点创建时间排序生成 `FX-{三位序号}`（FX-001…），供现场识别与口头引用；不随删除重排（新增点取 max+1，删除不补位）。

---

## 7. 安全标志库与匹配规则（GB 2894-2025 合规）

### 7.1 合规约束（硬性）

- 四类图形与安全色（对齐 ISO 3864/7010，GB 2894-2025 采用）：
  - 警告：黄底（#FFD100）黑边正三角形、黑图形
  - 禁止：白底红圈（#C8102E）红斜杠、黑图形
  - 指令：蓝底（#005EB8）白图形圆形
  - 提示：绿底（#009A44）白图形正方形
- 标志下方标注标准名称（黑体，如「当心爆炸」）；如加文字辅助，仅用「安全色底白字」或「白底黑字」，中文黑体。
- 卡片上标志排列顺序固定：**警告 → 禁止 → 指令 → 提示**。
- 图形仅使用 GB 2894-2025 体系内的标准图形（含新增的「当心有限空间/当心窒息/必须消除静电/禁止动火作业」等），不绘制非标图形。

### 7.2 SVG 资产清单（首版 36 个）

- 警告 warning-*（16）：explosion 当心爆炸、fire 当心火灾、electric 当心触电、machinery 当心机械伤人、fall 当心坠落、falling-object 当心坠落物、vehicle 当心车辆、crane 当心起重伤害、burn 当心烫伤、poison 当心中毒、suffocation 当心窒息、drowning 当心落水、collapse 当心坍塌、roof-fall 当心冒顶、water-inrush 当心透水、confined-space 当心有限空间
- 禁止 prohibition-*（6）：smoking 禁止烟火、hot-work 禁止动火作业、touch 禁止触摸、standing 禁止站人、pass 禁止通行、throwing 禁止抛物
- 指令 instruction-*（11）：helmet 必须戴安全帽、goggles 必须戴防护眼镜、gloves 必须戴防护手套、insulating-shoes 必须穿绝缘鞋、anti-static-clothes 必须穿防静电工作服、eliminate-static 必须消除静电、seatbelt 必须系安全带、gas-mask 必须戴防毒面具、lifejacket 必须穿救生衣、ventilate 必须通风、protective-suit 必须穿防护服
- 提示 notice-*（3）：exit 紧急出口、eyewash 洗眼台、shower 安全淋浴设施

> 注：资产清单含映射表未直接引用的预留图形（如当心有限空间），可手工用于有限空间等场景；实现时按映射表引用集绘制 + 预留图形补齐。

### 7.3 GB 6441 二十类事故 → 标志组映射

| 事故类型 | 标志组（警告→禁止→指令→提示） |
|----------|--------------------------------|
| 物体打击 | 当心坠落物 / — / 必须戴安全帽 / — |
| 车辆伤害 | 当心车辆 / 禁止通行 / — / —（安全出口与厂区道路车辆伤害无直接关联，不自动匹配） |
| 机械伤害 | 当心机械伤人 / — / 必须戴防护手套 / — |
| 起重伤害 | 当心起重伤害 / 禁止站人 / 必须戴安全帽 / — |
| 触电 | 当心触电 / 禁止触摸 / 必须穿绝缘鞋、必须戴防护手套 / 紧急出口 |
| 淹溺 | 当心落水 / — / 必须穿救生衣 / — |
| 灼烫 | 当心烫伤 / — / 必须穿防护服、必须戴防护手套 / —（洗眼台仅用于化学灼伤/腐蚀品溅眼场景，不放入通用灼烫组） |
| 火灾 | 当心火灾 / 禁止烟火、禁止动火作业 / — / 紧急出口 |
| 高处坠落 | 当心坠落 / 禁止抛物 / 必须系安全带 / — |
| 坍塌 | 当心坍塌 / 禁止通行 / — / — |
| 冒顶片帮 | 当心冒顶 / — / 必须戴安全帽 / — |
| 透水 | 当心透水 / — / 必须穿救生衣 / — |
| 放炮 | 当心爆炸 / 禁止烟火 / 必须戴安全帽 / — |
| 火药爆炸 | 当心爆炸 / 禁止烟火、禁止动火作业 / 必须消除静电 / — |
| 瓦斯爆炸 | 当心爆炸 / 禁止烟火 / 必须消除静电、必须穿防静电工作服 / — |
| 锅炉爆炸 | 当心爆炸 / — / — / 紧急出口（锅炉爆炸主因超压/缺水，非静电；配疏散出口） |
| 容器爆炸 | 当心爆炸 / 禁止烟火 / 必须消除静电 / — |
| 其他爆炸 | 当心爆炸 / 禁止烟火 / 必须消除静电 / — |
| 中毒和窒息 | 当心中毒、当心窒息 / — / 必须戴防毒面具、必须通风 / —（洗眼台不属吸入中毒通用设施，不自动匹配） |
| 其他伤害 | 当心机械伤人 / 禁止烟火 / 必须戴安全帽 / 紧急出口（默认组） |

匹配规则：`accident_type` 精确匹配映射表；未命中（含空值/自定义类型）→ **默认组**。一个风险点含多类事故时合并去重，按 警告→禁止→指令→提示 排序，每类最多取 2 个。

---

## 8. 应急处置模板（事故类型 → 标准步骤，模板兜底）

右栏「应急处置措施」组装顺序：① 该风险点下 `measure_category = emergency` 的措施归并（① ② ③ 编号）；② 若为空或少于 2 条，按事故类型模板补齐；③ 仍空则用通用模板（报警 119/120 → 疏散 → 现场急救）。

模板要点（实现时 20 类全量展开，示例）：

- 火灾/爆炸类：切断气源电源 → 撤离上风向清点人数 → 119/120 报警 → 喷淋冷却、禁火 → 配合消防处置
- 触电：切断电源 → 绝缘物脱离电源 → 判断意识呼吸 → 心肺复苏 → 120
- 中毒窒息：佩戴防护进入 → 通风 → 救出移至新鲜空气 → 120 → 禁止盲目施救
- 机械/起重伤害：停机断电 → 止血包扎固定 → 120 → 保护现场
- 高处坠落：保持伤者不动 → 固定搬运 → 120 → 保护现场
- 灼烫：立即冲水降温 15min → 脱除衣物 → 就医 → 洗眼台冲洗（涉及眼部）
- 淹溺/透水：救出 → 清理口鼻 → 心肺复苏 → 120
- 车辆伤害：制动熄火警戒 → 现场急救 → 120
- 坍塌/冒顶：警戒禁入 → 防二次坍塌搜救 → 120

---

## 9. API 设计

除公开端外均走现有鉴权（`get_current_user`）与企业归属校验（`_get_ent`）。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/enterprises/{eid}/risk-notice-cards` | GET | 摘要列表：id/name/zone_name/level/level_color/accident_types/signs/responsible_unit/snapshot/public_url/stale；筛选 `level` `zone_id` `keyword` |
| `/enterprises/{eid}/risk-notice-cards/{oid}` | GET | 单卡 CardData（快照优先） |
| `/enterprises/{eid}/risk-notice-cards/export` | POST | body `{object_ids: str[]}` → `{file_key}`；下载走 `/export/download/{file_key}` |
| `/enterprises/{eid}/risk-notice-cards/{oid}/ai-optimize` | POST | 无副作用：返回 `{original: RightColumn, optimized: RightColumn}` |
| `/enterprises/{eid}/risk-notice-cards/{oid}/snapshot` | PUT | body `{content: RightColumn}` → 保存 AI 快照 → `{version}` |
| `/enterprises/{eid}/risk-notice-cards/{oid}/token/reset` | POST | 重置 public_token → `{public_url}` |
| `/public/risk-notice-cards/{token}` | GET | 无鉴权公开只读：CardData（token 无效/过期→404） |

`CardData` 结构：object_id、enterprise_name、name、code（FX-序号）、level、level_color、responsible_unit/person/phone、fallback_used、signs[{category,name,svg_name}]、hazard_description、accident_types[]、control_measures[]、emergency_measures[]、snapshot{version,source}|null、stale、public_url、generated_at。

`RightColumn` 结构：hazard_description、control_measures[]、emergency_measures[]（accident_types 不参与优化）。

---

## 10. 页面交互（4 屏原型已确认）

### 10.1 卡片管理页（`RiskNoticeCardPage`）

- 风险管理 Tab 顶部「风险告知卡」按钮进入；顶部按钮「生成全部」「批量导出 Word」。
- 筛选：风险等级 / 所在分区下拉 + 关键词搜索 + 重置；统计行（总数 + 四色分布）。
- 列表列：勾选框、风险点名称（点击进预览）、所在分区、风险等级标签、主要事故类型、安全标志缩略（20px SVG）、责任单位、快照状态（「V1.1 AI」/「数据已变更」标签）、操作（预览 / AI 优化 / 链接复制）。
- 底部批量栏：勾选后显示「已选 N 项」+「导出选中卡片 Word」+ 清除选择；导出成功后提示并触发下载。

### 10.2 单卡预览 + AI 优化

- 预览页：面包屑、标题 + 版本标签、工具栏（返回列表 / 导出单张 Word / 复制公开链接 / AI 优化）、卡片渲染（v5 版式）。
- AI 优化：点击 → 加载态 → 左右对比面板（左「原版（当前版本）」右「优化版（AI 生成）」，右栏三块差异行黄色高亮并标注「已完善/已扩充」）→ 「采用优化版并保存快照（版本 → V1.x+1）」/「放弃，保留原版」；采用后版本 +1、卡片刷新、快照标签更新。
- 左栏信息（名称/等级/标志/责任信息）不参与 AI 优化。

### 10.3 公开只读页（`/r/:token`）

- 无登录守卫；URL 形如 `https://{host}/r/{token}`；token 无效或过期返回 404（不泄露卡片内容）。
- 移动端纵向布局：信息网格 → 安全标志（48px）→ 四信息块 → 页脚（签发/版本）→ 提示条「公开只读页面 · 数据来自系统快照 · 无需登录」。

### 10.4 风险对象表单

- `RiskObjectForm` 抽屉内新增「责任信息（用于风险告知卡）」分组：责任单位 / 责任人 / 联系电话（均可选）。
- 下方提示：「这三个字段会显示在风险告知卡左栏。留空时，卡片自动使用企业信息中的安全负责人及电话兜底。」

---

## 11. 导出与二维码

- **Word**：`risk_notice_card_docx.py` 渲染；A4 竖版、每卡分页；头部三区（企业名 / 居中标题 / 右上角二维码 PNG）；左栏键值表格 + 标志 PNG；右栏四块；页脚签发/日期/版本。文件名 `{企业名}-风险告知卡-{YYYYMMDD}.docx`。
- **二维码**：内容为公开页完整 URL（`{APP_BASE}/r/{public_token}`）。生成用后端 Python `qrcode` 库（若未安装则加入 requirements）；docx 内嵌 PNG（`qrcode` 直接输出 PNG）。
- **SVG→PNG**：复用 `mermaid_renderer` 的 SVG 转换能力（cairosvg），标志嵌入 docx 前转 PNG（约 160px）。
- **复制公开链接**：前端拼接当前部署 base + `/r/{token}`，复制到剪贴板。

---

## 12. AI 优化流程

1. 前端点「AI 优化」→ `POST /ai-optimize`（无副作用）。
2. 后端组装上下文：风险点名称/类别/位置、现有事件（描述/触发条件/后果）、现有措施（分类）、应急处置模板，调用 `risk_ai_service` 现有 DeepSeek 通道生成右栏三块优化文案；限制 JSON 输出，失败返回 502 语义错误（前端保留原版）。
3. 前端左右对比展示，用户确认后 `PUT /snapshot` 保存（version = max+1，source=ai，content 含右栏三块 + 左栏字段副本）。
4. 保存后预览/导出/公开页均用快照；风险源变更后卡片标记「数据已变更」。

AI 提示词约束：不修改事故类型；措施条目带 ① 编号；输出中文；单卡一次调用。

---

## 13. 错误处理

| 场景 | 行为 |
|------|------|
| 企业无风险点 | 管理页空态：「请先在风险管理中添加风险点」 |
| 风险点无事件/未评估 | 等级「未评估」灰底、默认标志组、右栏「暂无，请先完善风险评估数据」 |
| AI 调用失败/超时 | 提示「AI 优化失败，已保留原版」；不阻塞规则生成与导出 |
| 批量导出个别卡异常 | 跳过该卡，响应返回 `warnings` 列表，其余正常导出 |
| 公开页 token 无效 | 404，不返回任何卡片内容 |
| 导出文件不存在 | 沿用 `/export/download` 404 语义 |

---

## 14. 测试计划

**后端单元**
- CardData 组装：等级取最高事件等级；措施按 measure_category 归并；应急处置 emergency 优先 + 模板兜底；快照优先与 stale 判定；责任信息兜底。
- 标志映射：GB 6441 20 类全覆盖断言（每类非空、类别顺序 警告→禁止→指令→提示）；默认组兜底。
- 编号规则：FX-{max+1}，删除不补位。

**后端集成**
- 导出端点：生成 docx、每卡一页（分页符数量 = 卡数）、文件落 EXPORT_DIR、下载 200。
- 二维码：内容 = `/r/{token}`；token 重置后旧链接 404。
- 公开 API：有效 token 200、无效 404。
- AI 优化：mock AI 返回，快照保存后版本 +1、预览用快照。

**前端**
- 列表筛选/搜索/勾选批量参数；预览渲染；AI 对比面板展示与保存调用；公开页无登录守卫渲染；表单三字段提交。
- 合规检查：SVG 资产命名与映射表引用一致（脚本校验）。

---

## 15. 范围与里程碑

**首版包含**：字段迁移（6.1/6.2）、36 个 SVG 标志 + 20 类映射、组装服务、6+1 API、卡片管理页、单卡预览 + AI 对比、公开只读页、Word 导出（每卡一页 + 二维码）、错误处理、测试。

**首版不含**（后续可选）：批量 AI 优化、GB 2894-2025 全部 139 个标志、A3 汇总大卡、token 过期策略、移动端 App 内入口、快照历史多版本管理。

**里程碑**：① 数据层与迁移 → ② 标志库与映射 → ③ 组装服务 + API → ④ docx 导出 + 二维码 + 公开页 → ⑤ 前端页面与交互 → ⑥ AI 优化 → ⑦ 测试与回归。

---

## 16. 开放问题

- 公开页部署路径：`/r/:token` 需加入前端路由白名单（不要求登录），具体路由守卫改造在实现计划中细化。
- 二维码生成依赖 `qrcode` Python 包，需确认加入 backend requirements 并处理容器重装。
- 「数据已变更」的判定基准：以 `risk_notice_cards.updated_at` 与 `risk_objects/risk_events/risk_measures` 的 `updated_at` 最大值比较。
