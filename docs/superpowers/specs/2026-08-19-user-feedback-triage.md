# 用户反馈 21 项需求分析与实施方案（2026-08-19）

> 本文档针对用户 2026-08-19 提交的 21 项反馈做逐项代码定位、根因分析与方案建议。
> 状态：待用户确认批次与个别设计取舍后进入实现计划。

## 总览

| # | 主题 | 类型 | 定位结论 | 建议方案 | 量级 | 优先级 |
|---|------|------|---------|---------|------|--------|
| 1 | 成员可不绑定账号 | 需求/设计 | `enterprise_members.user_id` NOT NULL，添加成员必须选账号 | user_id 可空 + name/phone/email 列，双模式添加，非绑定为默认 | 中 | 高 |
| 2 | 组织树节点类型可设置 | 需求 | 类型由父子推导、重命名不能改类型 | 弹窗加类型 Select，编辑可改类型 | 小 | 高 |
| 3 | 管控清单出现 engineering | Bug | `risk_control_list_service._row` 直接输出英文键 | 后端/前端统一中文映射 | 小 | 高 |
| 4 | 完成度指标移入驾驶舱 | 需求 | Dashboard CompletionCard 未指明企业 | 工作台重构时移除/显示企业名；驾驶舱已有该面板 | 小 | 中 |
| 5 | 快捷新建弹窗加筛选 | 需求 | 弹窗纯列表，后端已支持 search/industry | 弹窗加搜索框 + 行业下拉 | 小 | 中 |
| 6 | 工作台重构（企业为主线） | 设计 | Dashboard 以预案统计为主线 | 企业门户化设计（见 §6） | 中 | 高 |
| 7 | 企业基本信息页扩容 | 需求 | 编辑页仅基本资料+GIS | 增加完成度/统计/快捷入口 | 中 | 中 |
| 8 | 楼层带分区允许删除 | 需求 | 后端 409 拒绝，前端树删除 floor 分支缺失 | 级联删除 + 二次确认（数量警告） | 中 | 高 |
| 9 | 智能引导补充/去重不覆盖 | 需求 | 生成已带 existing_names；导入仅分区名去重 | 层级路径合并 + 合并预览 | 中大 | 高 |
| 10 | 楼层平面图菜单重复 | 需求 | 侧栏「楼层平面图」与风险树「楼层管理」同一抽屉 | 删除侧栏入口 | 小 | 中 |
| 11 | 风险与隐患配置挪位 | 需求 | 企业级字典放在风险管控菜单下错位 | 移入企业管理模块/并入系统字典 | 小 | 中 |
| 12 | 四色热区偏移 | Bug | 总览按内容包围盒缩放，工作台按整画布 fit | 统一整画布 fit + 底图 | 小 | 高 |
| 13 | 工作台删除平面图 | 需求 | 无删除平面图端点/按钮 | 新增 DELETE plan 端点 + 按钮 | 小 | 中 |
| 14 | 现有/固有风险图作用 | 提问 | 仅着色差异 | 文档答复（见 §14） | 无 | 低 |
| 15 | 驾驶舱文案改名 | 需求 | ModuleNav 文案「风险评估/资源调查」 | 改为「风险评估报告/资源调查报告」 | 小 | 中 |
| 16 | 报告可编辑+版本 | 需求 | 查看页只读，无版本表 | 复用预案版本模式（快照表+回滚） | 中大 | 高 |
| 17 | 逐级返回 | Bug | PlanEditorPage 返回固定 `/plans` | 携带 enterprise_id 上下文返回 | 小 | 高 |
| 18 | 质量提示正文标注 | 需求 | 校验只有章节级提示，无正文定位 | 校验返回锚点 + 预览 mark + docx 高亮 | 中 | 中 |
| 19 | 章节序号/大标题混乱 | Bug | docx 未剥离正文开头标题；提示词强制编号 | 剥离+提示词调整+编号统一 | 中 | 高 |
| 20 | 版本回滚无效 | Bug | 回滚不更新 current_version，前端不失效 plan | 后端更新版本号 + 前端标记当前版本 | 小 | 高 |
| 21 | 法规源文件弹窗查看 | Bug | 新 tab 无鉴权头（401）+ 硬编码 /api/v1 前缀 | 弹窗内 fetch + 预览 | 小 | 中 |

---

## §1 成员可不绑定账号（设计重点）

### 现状
- `backend/app/models/enterprise_org.py`：`EnterpriseMember.user_id` NOT NULL + FK users，唯一约束 `(enterprise_id, user_id)`。
- `backend/app/routers/enterprise_org.py`：`create_member` 必须传 user_id 并校验账号存在；`import_members` 邮箱必填且账号必须存在；`list_members` INNER JOIN users。
- 组织树 JSON（`enterprise.org_structure`）的 `members` 本就支持无账号成员（`OrgMember.name` 必填、`user_id` 可空），AI 建树/预置组织均产出 name-only 成员。
- `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`：添加成员弹窗必须先「按邮箱搜索 → 选择账号」。

### 方案（两者兼顾，非绑定为主）
1. 数据模型（迁移脚本）：
   - `user_id` 改可空；新增 `name VARCHAR(100) NOT NULL DEFAULT ''`、`phone VARCHAR(30)`、`email VARCHAR(255)`。
   - 原唯一约束改为 Postgres 部分唯一索引 `WHERE user_id IS NOT NULL`（同账号只绑一次；未绑定成员允许多部门同名）。
   - 存量数据回填 `name = users.name`。
2. API：
   - `MemberCreate`：`user_id` 可空 + `name` 必填（未绑定时）+ phone/email 可选；绑定账号时仍校验账号存在/查重。
   - `list_members` / `available`：改 LEFT JOIN users，未绑定成员 name 取成员表。
   - `import_members`：邮箱列改可选；无邮箱行按「姓名+部门/班组/岗位+角色」导入为未绑定成员；有邮箱但账号不存在 → 报错提示（防拼写错误静默入库）。
3. 前端：
   - 添加成员弹窗默认「仅登记人员信息」（姓名/手机号/岗位/角色/组织节点）；可切换「绑定已有账号」（邮箱搜索）。
   - 成员表格增加姓名/手机号列，未绑定成员加「未绑定」标记。
4. 下游兼容：隐患责任人选择器（`/members/available`）、风险对象责任人为字符串字段，LEFT JOIN 后未绑定成员仍可选中。

**取舍点**：组织树 JSON 中的 name-only members 是否统一并入 `enterprise_members`？建议统一（成员列表以 enterprise_members 为准，树内 members 保留展示），避免双数据源。

---

## §2 组织树节点类型可设置

现状：`OrgNode.type` 数据模型/校验已支持 dept/team/position；前端仅「添加根部门/添加根岗位」两个入口，子节点类型由父节点推导（dept→team→position），重命名弹窗无类型字段。

方案：
- 节点新增/编辑弹窗增加「节点类型」Select（部门/班组/岗位），重命名改为「编辑节点」。
- 后端 `validate_org_tree` 已允许任意父子组合，无需改；前端提示推荐结构但不强制。
- 涉及 `EnterpriseOrgPage.tsx` 的 `nodeModal`（openAddNode/openRenameNode/submitNodeModal）。

---

## §3 管控清单出现 engineering

根因：`backend/app/services/risk_control_list_service.py` `_row()`：
```python
measures = "；".join(f"{m.measure_category}:{m.description}" ...)
```
`measure_category` 是英文键（engineering/management/ppe/emergency）。

方案：
- 后端新增 `MEASURE_CATEGORY_LABELS = {"engineering": "工程技术", ...}`，管控清单与 Excel 台账统一输出中文。
- 前端 `RiskManagementTab.tsx:405` 详情面板「措施类别」同样改用 `MEASURE_CATEGORY_LABELS`（已存在 `frontend/src/utils/riskMethodEngine.ts:31`）。

---

## §4 企业数据完成度移入驾驶舱

现状：`frontend/src/pages/Dashboard/CompletionCard.tsx` 基于 `useCurrentEnterprise` 展示完成度，未标明企业名；驾驶舱已有 `CockpitCompletionPanel`（按企业展示）。

方案：工作台重构（§6）时移除 Dashboard 的 CompletionCard；若保留，标题显示企业名。驾驶舱面板不动。

---

## §5 快捷新建弹窗筛选

现状：`DashboardPage.tsx` 快捷新建弹窗为纯企业列表；`listEnterprises` 已支持 `search`（name ilike）与 `industry`（精确匹配）参数。

方案：
- 弹窗顶部加搜索框（名称关键词，防抖 300ms）+ 行业下拉（从已加载企业去重生成或数据字典）。
- 搜索/筛选走后端参数（page_size 100 + search/industry），空结果显示「无匹配企业」。

---

## §6 工作台重构（企业信息/内容为主线）

现状：Dashboard = 全局统计卡（企业数/预案数/完成/风险事件）+ 完成度卡 + 快捷新建 + 最近编辑，以预案为主线。

建议设计（企业门户化）：
1. 顶部：欢迎区 + 全局统计（企业数、预案总数、待整改隐患、重大风险数）。
2. 主区：企业卡片网格——每卡含企业名、行业、地址、数据完成度环、风险/预案数量摘要，操作：进入驾驶舱、编辑信息、新建预案、风险管控。
3. 快捷新建：改为「为企业新建预案」→ 先选企业（复用 §5 筛选弹窗）→ 选预案类型。
4. 最近编辑：保留，展示「企业 → 预案」层级并可直接跳转。
5. 企业数据完成度：不再做全局指标，移入驾驶舱（§4）。

需用户确认：卡片网格 vs 当前企业聚焦（左画像右列表）两种布局偏好。

---

## §7 企业基本信息页扩容

现状：编辑页 `EnterpriseEditPage` = `EnterpriseInfoWorkspace`（基本资料 + GIS/平面图 + 导入）；基本信息模块页（`EnterpriseModulePage` info）只读卡片 + 编辑按钮。

方案（信息中心化）：
- 完成度模块清单（哪些模块缺数据，可点击跳转补齐）。
- GIS 定位与厂区平面图预览。
- 关键档案字段摘要（信用代码/法人/安全负责人/员工数/行业）。
- 组织/风险/预案统计卡片与快捷入口（组织与人员、风险管控、预案列表、四色图工作台）。

---

## §8 楼层带分区允许删除（警告+二次确认）

现状：
- `backend/app/routers/risk_management.py` `delete_floor`：分区/对象计数 > 0 时 409 拒绝。
- 前端 `FloorManagementDrawer` / `EnterpriseFloorManager` 删除时提示「后端会拒绝」。
- 附带 Bug：`RiskManagementTab.tsx` `confirmDelete` 的 switch 缺少 `floor` 分支（树中删楼层静默无效）。

方案：
- 后端改为级联删除（RiskZone → RiskObject/Unit/Event/Measure），删除前统计并返回 `{zone_count, object_count}`；仍保留「企业至少一个默认楼层」约束。
- 前端二次确认：Modal 显示「将删除该楼层、N 个分区、M 个风险点及全部风险数据，不可恢复」，需输入楼层名或勾选确认。
- 修复树节点删除 floor 分支。

---

## §9 智能引导补充/去重（不覆盖）

现状：
- 生成：`risk_ai_service.smart_guide` 已接收 `existing_names`（zones/objects 名称列表）并禁止重复生成分区。
- 导入：`RiskSmartGuideModal` 仅按分区名过滤（`buildImportPlan`），对象/单元/事件/措施全部无条件新建；无层级合并。

方案：
- 导入改为「层级路径合并」：分区重名 → 并入现有分区；对象按名称去重（同级同名跳过）；事件按事故类型去重；措施按类别+描述去重。
- 预览树增加「合并结果」标记（新增/跳过/合并计数），默认合并模式，可切覆盖模式。
- 生成侧把现有层级摘要从名称列表升级为路径摘要（父链），提升语义去重准确率。

---

## §10 楼层平面图菜单重复

现状：`enterpriseNavConfig.ts` 侧栏「楼层平面图」`/risk-management?floor=1` 与风险树编辑「楼层管理」按钮打开同一个 `FloorManagementDrawer`。

方案：删除侧栏「楼层平面图」入口，保留风险树「楼层管理」按钮；抽屉底部文案改为提示平面图上传在四色图工作台。

---

## §11 风险与隐患配置挪位

现状：`EnterpriseDictConfigPage` 实为企业级字典（管控层级映射/整改期限/隐患类型/评估折算系数/公示范围/隐患状态标签/隐患来源），挂在风险分级管控「数据编辑」组下。

方案（二选一，待用户确认）：
- A（推荐）：移入企业驾驶舱模块导航，独立「字典配置」模块，命名「风险隐患字典配置」。
- B：并入系统管理「数据字典管理」，增加企业维度切换。

---

## §12 四色分布热区偏移

根因：`RiskDistributionStage.tsx`（可视化总览）用「内容包围盒 contentBounds」自适应缩放并居中；`WorkbenchCanvas.tsx`（四色图工作台）按整张画布（floor.canvas_width/height）fit。两者坐标同为百分比，但投影方式不同 → 总览中风险点/分区相对底图整体偏移；且总览不绘制底图。

方案：
- `RiskDistributionStage` 改为与工作台一致的「整画布 fit + 居中」，并绘制 `floor_plan_url` 底图（KonvaImage）。
- 两端共用同一 view-transform 工具函数，杜绝再次分叉。

---

## §13 四色图工作台删除平面图

现状：`EnterpriseFloorManager` 有上传/替换，无删除；后端无删除端点。

方案：
- 后端新增 `DELETE /floors/{floor_id}/plan`：清空 floor_plan_url/canvas_width/height，删除文件；默认楼层时同步清 enterprise.floor_plan_url。
- 前端工作台工具栏「删除当前楼层平面图」按钮（Popconfirm，注明仅清除底图、不影响分区/风险点数据）。

---

## §14 现有风险图 vs 固有风险图

结论：仅改变地图着色，不改变任何数据。
- 现有风险图：分区/区域按「现有风险等级」最大等级着色（`effective_color`）。
- 固有风险图：按「固有风险等级」着色（`inherent_effective_color`，无固有等级时回退现有）。
- 用途：直观对比采取管控措施前（固有）后（现有）的风险分布变化。

已知小缺陷：风险点图标（`WorkbenchRiskPointLayer`）始终蓝色，不随模式变化；如需风险点也按等级着色可列为增强项。

---

## §15 驾驶舱文案

`ModuleNav.tsx`：`风险评估` → `风险评估报告`；`资源调查` → `资源调查报告`（与 `EnterpriseModulePage` MODULE_MAP 标题一致）。

---

## §16 风险评估/资源调查报告可编辑 + 保存版本

现状：报告 Tab（`RiskAssessmentTab`/`ResourceInvestigationTab`）支持生成与合并保存；查看页（`RiskAssessmentPreview`/`ResourceInvestigationPreview`）只读 + 下载 Word；无版本概念（模型见 `report_base.py`）。

方案（复用预案版本模式）：
- 后端新增 `report_versions` 表（report_id/version_number/content/summary/created_by/created_at），主表加 `current_version`。
- 端点：`POST .../versions`（保存快照）、`GET .../versions`、`POST .../versions/{vid}/rollback`、`PUT .../content`（保存编辑正文）。
- 前端查看页加「编辑」→ 富文本编辑（复用 RichTextEditor）→ 保存 + 保存版本；版本历史弹窗/抽屉支持查看、对比、回滚。

---

## §17 逐级返回

根因：`PlanEditorPage.tsx` `onBack={() => navigate("/plans")}` 固定跳全局列表；从企业预案列表（`/enterprises/:enterprise_id/plans`）进入后返回丢失层级。其余返回链基本正确（预览→编辑→列表、版本历史→编辑）。

方案：
- 进入编辑页的入口（企业预案列表、卡片列表、快捷新建）统一携带 `enterprise_id` 查询参数。
- `PlanEditorPage` 依据参数返回 `/enterprises/{eid}/plans`，无参数时维持 `/plans`。
- 审查所有列表→详情→返回链路（含移动端）是否都满足逐级返回。

---

## §18 质量提示在正文标注

结论：可以实现。

方案：
- `plan_quality_service` 每条 issue/warning 增加定位信息：占位符位置、匹配片段（如「（待补充）」、Mermaid 代码块、缺失档案字段名），返回 `{section_key, issue, evidence}`。
- 预览（`ExportPreviewPage` + `_build_preview_section_html`）：对 evidence 包 `<mark class="quality-issue">`，提示列表可点击滚动定位到对应章节段落。
- docx 导出（`generate_plan_docx`）：对匹配文本 run 加高亮（python-docx `font.highlight`）并在段落尾追加「【质量提示：…】」文字；Word 批注（comment）可作为进阶项。

---

## §19 章节序号与大标题混乱

根因：
1. `generate_plan_docx`（`docx_template.py`）写标题后未剥离正文开头标题；`export.py` 的预览路径有 `_strip_section_heading`，docx 路径没有 → 导出 docx 出现「编号标题 + 正文自带标题」重复。
2. `generation.py` `_build_section_prompt` 兜底路径的 `num_hint` 明确要求正文使用「N.」编号 → AI 正文自带编号与导出编号冲突；DB 模板路径无「不要重复章节标题」约束。
3. 编号函数在 export.py 与 docx_template.py 各有一份（逻辑一致），建议收敛。

方案：
- 将 `_strip_section_heading` 抽到公共模块，docx 导出前同样剥离。
- 生成提示词：去掉/改写 `num_hint` 为「正文不要输出章节标题与编号，编号由导出自动生成」；DB 模板路径统一追加同款约束。
- 编号逻辑收敛为一个工具函数并补导出回归测试。

---

## §20 版本回滚后页面无变化

根因：
1. `versions.py rollback_version` 恢复 content/style 但**不更新** `plan.current_version` 与 `updated_at`。
2. 前端 `VersionListPage` 回滚成功只 invalidate `versions` + `planSections`，编辑器依赖的 `plan` 未失效；版本列表也没有「当前版本」标记，视觉上无变化。

方案：
- 后端：回滚时 `p.current_version = v.version_number`、`p.updated_at = now()`，响应返回新版本号。
- 前端：版本列表标记当前版本行（V 徽标 + 仅非当前行可回滚）；回滚后 invalidate `plan`/`planSections`/`versions`；`PlanEditorPage` 标题区显示「当前版本 V{n}」。

---

## §21 法规源文件弹窗查看

根因（新 tab 报错）：
- 新 tab 打开 `/api/v1/regulations/{id}/source` 不带 Authorization 头，后端 `Depends(get_current_user)` 返回 401。
- `regulationService.getSourceDownloadUrl` 硬编码 `/api/v1` 前缀，部署在子路径（VITE_BASE_PATH）下会 404。

方案：
- 不再新开 tab：源文件改为 Modal 内预览——用带鉴权的 api 客户端 fetch（响应式 Blob/文本），PDF/图片/文本直接内嵌预览，Office 格式提示下载。
- `getSourceDownloadUrl` 改用应用 base 拼接或移除（仅保留下载场景）。

---

## 建议实施批次

- **批次 A（快速 Bug 修复，可先行）**：§3 engineering、§17 逐级返回、§20 版本回滚、§12 热区偏移、§15 文案、§21 法规弹窗、§10 菜单去重、§13 删除平面图、§2 节点类型。
- **批次 B（风险管控增强）**：§8 楼层级联删除、§9 智能引导合并、§11 字典挪位。
- **批次 C（成员与报告）**：§1 成员不绑定账号（含迁移）、§16 报告编辑+版本。
- **批次 D（工作台与企业页）**：§6 工作台重构、§7 企业信息页扩容、§5 弹窗筛选、§4 完成度迁移、§18 质量标注、§19 章节序号。

## 待用户确认
1. §1：组织树内 name-only 成员是否并入 enterprise_members（建议并入）。
2. §6：工作台布局偏好（卡片网格 vs 当前企业聚焦）。
3. §11：字典配置放企业管理模块（A）还是并入系统数据字典（B）。
4. 批次执行顺序（默认 A → B → C → D）。
