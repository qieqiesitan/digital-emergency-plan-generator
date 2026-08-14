# 风险分级管控增强（固有/现有双等级、四色图切换、管控清单、重大风险公示）— 设计规格

> **日期**：2026-08-14 | **状态**：设计中 | **依赖**：风险管理模块（`risk_events` / `risk_zones` / `risk_objects` / `risk_measures`）、四色分布图工作台与导入、风险总览、风险告知卡、AI 服务（DeepSeek）、`openpyxl`

---

## 1. 概述

在现有「风险分级管控」模块上补齐双重预防机制第一支柱的四个能力，与「隐患排查治理」模块（另一份规格）共同构成完整闭环：

1. **风险事件双等级**：固有风险（不考虑管控措施有效性）与现有（剩余）风险（考虑管控措施有效性）分开记录与展示；
2. **四色分布图双模式**：工作台 / 总览 / 公示支持「固有风险四色图 / 现有风险四色图」切换；
3. **风险分级管控清单**：按 分区 → 风险点 → 单元 → 事件 展平的责任清单（管控层级、责任单位/人、管控措施），支持筛选与 Excel 导出；
4. **重大风险公示**：企业内公示页（四色图 + 重大风险清单，可打印）+ 公开只读 token 页（脱敏）。

硬性约束：**不破坏现有单等级数据的语义**。现有 `risk_level` / `risk_score` 明确为「现有（剩余）风险」，迁移时把存量等级回填为固有等级，存量企业立即可用、可逐步重评。

---

## 2. 需求决策（用户已确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 固有 / 现有双等级 | 风险事件新增固有等级/分值；现有 `risk_level` 语义定为「现有（剩余）风险」；存量数据迁移回填固有 = 现有 |
| 2 | 现有风险算法 | 默认「双参数评估」（同一方法两套参数，人工/AI 辅助判断）；另提供「自动折算参考」工具：按管控措施类别系数给参考现有风险，人工确认后采用 |
| 3 | 四色图双模式 | 支持「固有 / 现有」切换；`manual` 手动色两模式共用，`auto` 自动色按模式计算 |
| 3 | 管控层级 | 按现有等级默认映射（重大→企业、较大→部门、一般→班组、低→岗位），事件级可覆盖 |
| 4 | 风险管控清单 | 新增清单页 + Excel 导出（复用 `openpyxl`） |
| 5 | 重大风险公示 | 企业内页面（可打印）+ 公开只读 token 页（仅清单、脱敏联系方式） |
| 6 | 风险告知卡 | 等级色带与键值表展示固有/现有双等级 |
| 7 | 配置化（补审） | 常量和规则统一收进通用数据字典表 `data_dicts`（系统默认 + 企业覆盖，界面维护、即时生效）；状态机/权限等安全关键逻辑不进表 |
| 8 | 范围边界 | 本次不做：未闭环隐患写入预案生成、监管平台真实对接（二期） |

---

## 3. 现状基础

| 组件 | 现状 |
|------|------|
| `risk_events` | 风险事件：accident_type、trigger_conditions、consequences、**单一** `risk_level`、`risk_score`、method_type、method_params |
| `risk_zones` | 分区：`max_risk_level`、`effective_color`（四色）；`floor_plan_polygon` v2 `{color_source: auto\|manual, color, polygons[]}` |
| `risk_mapping_service` | `max_risk_level(zone)` 从事件等级取 max；`effective_color(polygon, max_level)`；`LEVEL_ORDER` / `LEVEL_COLORS`（重大红 #ff4d4f / 较大橙 #fa8c16 / 一般黄 #fadb14 / 低绿 #52c41a / 未评估灰） |
| `risk_objects` | 风险点：name/category/location/zone_id/floor_id/is_risk_point、责任单位/责任人/电话（告知卡已加） |
| `risk_measures` | 管控措施：measure_category（engineering/management/ppe/emergency）、description、responsible_person、status、check_items |
| 评估引擎 | `compute_risk(method_type, params, config)` 纯函数：LS / LEC / COAL_LS / DIRECT，按阈值区间输出等级/分值/处置/期限 |
| 前端 | 工作台 `RiskMappingWorkbenchPage`、总览 `RiskOverviewPage`（四象限/分布图/数据三视图）、告知卡 `RiskNoticeCard.tsx` 均单等级 |
| 导出 | `openpyxl` 已在依赖（`resources_ext.py` 模板导出先例）；docx 导出管线已有 |

**关键事实（核查结论）**：全库无「固有 / 现有」区分字段，四色图只有单一版本。本规格即补齐该缺口。

---

## 4. 概念定义

- **固有风险**：不考虑管控措施是否有效的风险。评估时使用未施加管控修正的参数（如 LEC 的 L/E/C 取无管控状态，LS 的 L/S 同理）。
- **现有（剩余）风险**：考虑当前管控措施有效性的风险。现有 `risk_level` / `risk_score` 即此语义。
- **默认约束**：现有风险等级不应高于固有风险等级；违反时保存拦截并提示（AI 或人工录入出现时同样校验）。

---

## 5. 数据模型

### 5.1 `risk_events` 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `inherent_risk_level` | String(20) NULL | 固有风险等级：重大/较大/一般/低 |
| `inherent_risk_score` | String(50) NULL | 固有风险分值表达式（R=… / D=…） |
| `control_level` | String(20) NULL | 管控层级：企业/部门/班组/岗位；NULL 时按现有等级默认映射 |

迁移 `db_migration_risk_control_enhancement.sql`：

```sql
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inherent_risk_level VARCHAR(20);
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inherent_risk_score VARCHAR(50);
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS control_level VARCHAR(20);
UPDATE risk_events SET inherent_risk_level = risk_level WHERE inherent_risk_level IS NULL;
UPDATE risk_events SET inherent_risk_score = risk_score WHERE inherent_risk_score IS NULL;
```

### 5.2 评估方法引擎

`compute_risk` 保持纯函数不变。现有风险计算提供两种方式，**默认双参数评估为主，自动折算仅作参考**：

**方式一：双参数评估（默认）**。固有 / 现有 = 同一方法的两套参数：

- LS / LEC / COAL_LS：表单新增「固有参数」区块（l/s 或 l/e/c 取无管控状态），保存时分别计算两组结果；
- DIRECT：直接录入两个等级（`risk_level` + `inherent_risk_level`）。

方法预览接口（`MethodPreviewRequest`）增加可选 `scenario: "inherent" | "current"`，用于表单实时预览，默认 `current`。

**方式二：自动折算参考（工具）**。由固有风险 × 管控措施类别系数得到「参考现有风险」，仅作参考对比，人工确认后才落库：

- 系数表来自数据字典 `measure_factors`（系统默认 + 企业覆盖，见 §5.4）：

| 措施类别（`measure_category`） | 系数 |
|------|------|
| engineering 工程技术 | 0.50 |
| management 管理措施 | 0.70 |
| ppe 个体防护 | 0.85 |
| emergency 应急措施 | 0.90 |

- 综合系数口径（默认保守）：`综合系数 = 已配置类别系数的最小值`（最有效类别主导，不叠加）；`mode` 存于字典 value，企业可切换为「乘积」模式（取各类别系数连乘）；
- 参考分值 = 固有分值数值 × 综合系数（解析 `R=…` / `D=…` 数值；DIRECT 方法不适用，由 AI 给等级参考）；
- 参考等级 = 参考分值落入该企业方法阈值区间（复用 `compute_risk` 的阈值匹配逻辑，抽成 `level_from_score(method_type, score, config)`）；
- AI 解释：`hazard_ai_service`（或复用 `risk_ai_service` 通道）可选输出文字说明（如「报警器+联锁为主，综合系数 0.5，参考现有风险 一般」）；
- UI：事件表单「自动折算参考」按钮 → 展示参考结果卡片 → 「采用为现有风险」一键填入（用户仍可修改）或仅作对比。

**方式三：AI 双等级参数建议（文本通道，用户已确认）**：

- 接口 `POST /enterprises/{id}/risk-management/events/{event_id}/ai-dual-level-suggestion`：输入 = 事件描述 + 管控措施文本（仅文本，**不依赖图像识别**）；
- 输出 JSON：`{inherent: {l, e, c 或 l, s, risk_level, risk_score}, current: {...}, note}`，由 DeepSeek 建议两套参数与等级；
- 前端：事件表单「AI 建议参数」按钮 → 展示对比 → 「采用」填入固有/现有区块（仍可改）；
- AI 失败/超时 → 返回「无 AI 建议」，降级为纯人工或折算参考，不阻塞。

### 5.4 数据字典表 `data_dicts`（公共基础，随 A 落地）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| dict_type | String(50) NOT NULL | 字典类型：hazard_type / measure_factors / control_level_map / judgment_points / deadline_rules / publicity_scope / source_type / record_status_label |
| code | String(50) NOT NULL | 条目 code（如 equipment / engineering / major） |
| label | String(100) NOT NULL | 展示文案 |
| value | JSONB NOT NULL 默认 {} | 结构化值（系数、映射、天数等） |
| scope | String(10) NOT NULL | system / enterprise |
| enterprise_id | UUID FK NULL | enterprise 范围记录所属企业 |
| sort_order | Integer 默认 0 | |
| enabled | Boolean 默认 true | |
| is_system | Boolean | 系统默认条目标记 |
| description | Text NULL | |
| created_at / updated_at | DateTime | |
| 唯一约束 | (dict_type, enterprise_id, code) | enterprise_id 为 NULL 表示系统默认 |

**合并与生效规则**：

- 读取顺序：企业条目（enterprise_id = 当前企业）> 系统默认（enterprise_id IS NULL）；同 code 企业条目覆盖系统条目 value / label；
- 企业可新增字典类型内条目、覆盖同 code 条目、禁用条目；
- 进程内短缓存（60s）+ 变更失效；数据量小，读取成本可忽略；
- **安全关键逻辑不进表**：状态机流转、权限校验、复查人≠整改人保持代码强类型。

**管理界面**：系统设置「数据字典管理」（超级管理员维护系统默认）；企业设置「风险与隐患配置」（企业管理员维护覆盖值，含「重置为系统默认」）。

**迁移**：`db_migration_data_dicts.sql`——建表 + 种子数据（系统默认：hazard_type 6 项、measure_factors 4 类系数 + mode、control_level_map 4 映射、deadline_rules、publicity_scope、source_type / record_status_label 文案；B 规格的字典类型在其迁移中扩展）。

### 5.3 分区四色双模式

`floor_plan_polygon` JSONB 结构不变：

- `color_source = manual`：单一 `color` 两模式共用（明确为设计约束，避免双色存储复杂度）；
- `color_source = auto`：按模式分别取该模式 max 风险等级的色值。

响应模型扩展：

- `RiskZoneResponse` / `HierarchyZoneResponse` 新增 `inherent_max_level`、`inherent_effective_color`；
- 现有 `max_risk_level` / `effective_color` 语义 = 现有模式（兼容存量前端）。

`risk_mapping_service.max_risk_level(zone, mode="current")` 增加 `mode` 参数（`inherent` / `current`），遍历对象/单元事件时按模式取对应等级字段。

---

## 6. 四色图双模式

- **工作台**（`RiskMappingWorkbenchPage`）：顶部 Segmented「固有风险图 / 现有风险图」。切换后按模式计算区域颜色渲染；风险点绑定、多边形保存逻辑不变（polygon 不存双色，模式只影响展示）。
- **风险总览**（`RiskOverviewPage`）：同样加切换；四象限 / 分布图 / 数据视图三种视图同步切换。
- 色值沿用 `LEVEL_COLORS`，前后端一致。

---

## 7. 风险分级管控清单

**数据源**：floor → zone → object → unit → event → measures + object 责任字段。

**行字段**：

| 列 | 来源 |
|----|------|
| 分区 / 风险点 / 单元 | 层级链 |
| 事故类型 | event.accident_type |
| 固有等级 / 现有等级 | event.inherent_risk_level / event.risk_level |
| 管控层级 | event.control_level（NULL 时按默认映射） |
| 管控措施 | event.measures（category + description） |
| 责任单位 / 责任人 / 联系电话 | object.responsible_unit / responsible_person / contact_phone |

**默认映射**（来自数据字典 `control_level_map`，系统默认 + 企业覆盖，见 §5.4）：

| 现有风险等级 | 管控层级 |
|-------------|----------|
| 重大 | 企业 |
| 较大 | 部门 |
| 一般 | 班组 |
| 低 | 岗位 |

**筛选**：楼层 / 分区 / 等级（固有或现有）/ 管控层级 / 关键字。

**接口**：

- `GET /enterprises/{id}/risk-management/control-list`（分页 + 筛选）
- `GET /enterprises/{id}/risk-management/control-list/export` → xlsx（sheet1 清单、sheet2 按等级/层级汇总；`openpyxl`）

---

## 8. 重大风险公示

**企业内公示页**（`RiskPublicityPage`）：

- 现有模式四色图（复用总览分布图组件）；
- 重大风险清单表：风险点 / 位置 / 事故类型 / 现有等级 / 管控层级 / 责任单位 / 主要措施 / 告知卡入口；
- 口径：现有等级 = 重大 **或** 管控层级 = 企业；
- 打印样式（`@media print`，A4 一页清单 + 图）。

**公开只读页**：

- `enterprises` 新增 `public_risk_token` String(64) UNIQUE NULL；企业详情页「生成 / 重置公示链接」按钮（复用 `secrets.token_hex(32)` 模式）；
- 公开端点 `GET /public/risk/{token}`：返回重大风险清单（**脱敏：不返回责任人姓名、电话等联系方式**）+ 企业名称 + 生成时间；数据动态组装（非快照）；
- 前端公开页 `/p/risk/:token`，无登录守卫，复用风险告知卡公开页框架（移动端适配）。

---

## 9. 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/enterprises/{id}/risk-management/control-list` | 管控清单（分页/筛选） |
| GET | `/enterprises/{id}/risk-management/control-list/export` | xlsx 导出 |
| GET | `/enterprises/{id}/risk-management/risk-publicity` | 公示数据（含 token、清单、四色图数据） |
| POST | `/enterprises/{id}/risk-management/risk-publicity/token` | 生成/重置公示 token |
| GET | `/public/risk/{token}` | 公开公示（脱敏） |
| 扩展 | hierarchy / workbench / overview / zone 响应 | 增加 `inherent_max_level` / `inherent_effective_color` |
| 扩展 | event create / update | 接受 `inherent_risk_level` / `inherent_risk_score` / `control_level` |
| 扩展 | method preview | `scenario` 参数 |

---

## 10. 前端页面

| 页面 | 变更 |
|------|------|
| `RiskEventForm` | 新增「固有风险参数」区块（按方法渲染）+ 管控层级选择（带默认映射提示）+「自动折算参考」按钮（展示参考现有风险卡片，可一键采用） |
| `RiskMappingWorkbenchPage` | Segmented 固有/现有切换 |
| `RiskOverviewPage` | Segmented 固有/现有切换（三视图同步） |
| `RiskControlListPage`（新） | 清单表 + 筛选 + 导出；入口：风险管理 Tab「管控清单」按钮 |
| `RiskPublicityPage`（新） | 公示预览/打印 + 生成链接 |
| `PublicRiskPage`（新，路由 `/p/risk/:token`） | 公开只读公示 |
| `RiskNoticeCard.tsx` | 等级色带/键值表显示「固有 / 现有」双等级 |
| 系统设置「数据字典管理」/ 企业「风险与隐患配置」 | 维护 `data_dicts`（折算系数、层级映射等，企业可覆盖/重置） |

---

## 11. 错误处理与边界

- 现有等级 > 固有等级：保存返回 422「现有风险等级不应高于固有风险等级」；
- 无事件数据：清单 / 公示空态展示，不报错；
- token 无效：404「链接已失效」；
- 公开页脱敏：后端数据层过滤敏感字段（不依赖前端隐藏）；
- 迁移幂等：`IF NOT EXISTS` + 条件回填，可重复执行。

---

## 12. 测试策略

- **pytest**：双等级计算与迁移回填；自动折算（系数表/最小值与乘积口径/分值解析/阈值映射/DIRECT 不适用）；数据字典（系统种子/企业覆盖合并、同 code 覆盖、禁用、重置）；`max_risk_level(mode)` 正确性；清单展平/筛选/导出；token 生成/重置/404；脱敏断言；现有>固有校验；
- **前端 vitest**：双模式切换渲染、清单筛选、公示打印样式类、公开页渲染；
- **回归**：告知卡 / 总览 / 工作台既有用例不破坏（响应新增字段向后兼容）；
- **门禁**：tsc / eslint / vitest / pytest 全绿 + `git diff --check`。

---

## 13. 部署与迁移

- 应用 `db_migration_risk_control_enhancement.sql` 与 `db_migration_data_dicts.sql`；
- 无新依赖（`openpyxl` 已有）；
- 后端容器重建即可（`docker compose build backend`）。

---

## 14. 验收标准

1. 风险事件可分别录入/计算固有与现有等级，存量数据自动回填；
2. 「自动折算参考」可给出参考现有风险（含系数说明），人工确认后采用；
3. 折算系数/管控层级映射等字典项可配置并即时生效（企业覆盖 > 系统默认，可重置）；
4. 工作台与总览四色图可切换固有/现有模式且颜色正确；
5. 管控清单可按条件筛选并导出 xlsx；
6. 公示页企业内可打印；公开 token 可打开且无敏感信息；
7. 风险告知卡展示双等级；
8. 全部门禁通过。

---

## 15. 二期（本次不做）

- 未闭环重大隐患写入预案生成章节/附件；
- 与监管平台真实系统对接上报；
- 岗位/班组风险告知卡（按岗位/班组汇总风险点出卡，与「企业组织与成员管理」联动）。
