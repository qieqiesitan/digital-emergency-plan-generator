# 组织架构与应急组织拆分 — 设计规格（2026-09-18）

## 1. 背景与问题

用户反馈：系统里的「组织架构」把公司组织架构和应急组织混在一起，导致一人多岗无法表达。

已核实的代码与数据事实：

1. `enterprises.org_structure`（`backend/app/models/enterprise.py:30`）是一个 JSONB 字段，被两条写入路径共用且格式不同：
   - `PUT /enterprises/{id}/org-structure`（`backend/app/routers/enterprise_sub.py:38`）写「应急小组分组」`[{group_key, group_name, members:[{role,name,position,phone}]}]`，前端由 `frontend/src/pages/Onboarding/StepOrg.tsx` 使用。
   - `PUT /enterprises/{id}/org/nodes`（`backend/app/routers/enterprise_org.py:127`）写「组织树」`[{id,type:dept|team|position,name,parent_id,members}]`，前端由 `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx` 使用。
   两者写同一列，后保存者覆盖先保存者。
2. 企业组织页在组织树为空时自动播种应急组织（`EnterpriseOrgPage.tsx:201` `buildPresetOrgNodes()`、`:247-253` effect），并提供「应用预置应急组织」按钮（`:360` `applyPresetOrg`、`:743`）。预置内容为「应急组织机构 → 应急指挥部/抢险救灾组/疏散引导组/医疗救护组/通讯联络组/后勤保障组 → 总指挥/副总指挥/成员、组长/副组长/组员」，小组名单来自 `frontend/src/utils/constants.ts:1` `PRESET_EMERGENCY_GROUPS`。
3. 生产库实测（库 `emergency_plan`）存在**两种**存量形态：
   - 树格式（西安宝岳空间科技有限公司，37 节点）：其中 26 个是应急节点（`preset-org-root` 根 + 6 个应急小组 + 1 个 `node-5` 部门型「应急指挥部」+ 18 个岗位），11 个是真实公司节点（`公司` → `应急安全事业部`/`管网事业部`/`资规事业部` → `技术开发` → 6 个岗位）。`enterprise_members` 3 名成员（刘昕野/总经理、赵志龙/项目总监、程磊/项目经理）的 `org_node_id` 分别指向 `preset-headquarters-0/1/2`，即「应急指挥部/总指挥」「副总指挥」「成员」。公司职位与应急角色被压在同一棵树上。
   - 旧分组格式（陕西宝岳测绘有限公司，6 条 `{group_key, group_name, members:[{name, role: chief|deputy|leader|member, phone, position}]}`）：整棵都是应急组织，成员内嵌且**未登记到 `enterprise_members`**。
   - 另有延长壳牌石油有限公司（西安明光路加油站）25 节点 = 未编辑的完整预置（1 + 6 + 18），整棵都是应急组织。
   - `PUT /org-structure` 与 `/org/nodes` 就是分别往这两个形态写，所以同一家企业被两个入口编辑后会同时存在两种节点，前端渲染随即错乱。
4. `enterprise_members.org_node_id` 是单值列（`backend/app/models/enterprise_org.py`），一个人只能挂一个节点——这是一人多岗无法实现的直接原因，与页面交互无关。
5. 下游消费方各按各的假设取值（详见 §5），同一棵树同时承担公司组织架构、应急组织架构、预案署名名单三种语义。

结论：两件事必须拆开，且这是数据模型层面的改动。

## 2. 目标与非目标

### 2.1 目标

- 公司组织架构只表达「部门 → 班组 → 岗位」与人员任职，支持一人多岗（主岗 + 兼岗）。
- 应急组织独立成数据层，支持一人多任（同一人可同时担任多个应急角色）。
- 预案「应急组织机构及职责」章节、组织架构图、章节自动填充、导出签署页、预案质检统一从应急组织取数。
- 作业票会签、隐患责任人选择器、隐患报表部门列继续从公司组织架构取数，且兼岗人员也能被正确识别。
- 存量数据无损搬迁：现有应急组织节点与人员挂载关系转为应急组织数据，不丢信息。

### 2.2 非目标（明确不做）

- 不引入 BPMN 或审批流引擎改造应急指挥体系。
- 不重构作业票、隐患、风险模块自身的业务逻辑。
- 不做集团—子公司多级企业嵌套组织架构。
- 不给应急组织做版本管理或历史留痕。
- 不把旧 `OrgGroup` 分组格式保留为长期数据形态，迁移后即废弃。

## 3. 数据模型

### 3.1 公司侧

`enterprises.org_structure` 保留为组织树，只放公司口径：`[{id,type:dept|team|position,name,parent_id}]`。

- 节点内嵌 `members` 停止写入。生成预案时 `_merge_org_members`（`backend/app/routers/generation.py:406`）已用企业成员表覆盖节点内嵌成员，内嵌 `members` 已不是事实来源；字段保留仅为兼容旧读取方（如 `frontend/src/utils/orgMerge.ts`），新写入一律为空数组。
- 新增 `member_positions` 承载任职关系：

```sql
CREATE TABLE IF NOT EXISTS member_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES enterprise_members(id) ON DELETE CASCADE,
    org_node_id VARCHAR(64) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (member_id, org_node_id)
);
CREATE INDEX IF NOT EXISTS idx_member_positions_member ON member_positions(member_id);
CREATE INDEX IF NOT EXISTS idx_member_positions_node ON member_positions(org_node_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_member_positions_primary ON member_positions(member_id) WHERE is_primary;
```

- `enterprise_members.org_node_id` 保留，语义降级为「主岗镜像列」：始终等于 `member_positions` 中 `is_primary = true` 的那条，由服务层同步维护。只认主岗的消费方零改动；需要识别兼岗的消费方改走 `member_positions`。

### 3.2 应急侧

```sql
CREATE TABLE IF NOT EXISTS emergency_org_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    parent_id UUID NULL REFERENCES emergency_org_units(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    duties TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_units_ent ON emergency_org_units(enterprise_id, parent_id, sort_order);

CREATE TABLE IF NOT EXISTS emergency_org_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    unit_id UUID NOT NULL REFERENCES emergency_org_units(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    duties TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_roles_unit ON emergency_org_roles(unit_id, sort_order);

CREATE TABLE IF NOT EXISTS emergency_org_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES emergency_org_roles(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES enterprise_members(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (role_id, member_id)
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_assignments_role ON emergency_org_assignments(role_id);
CREATE INDEX IF NOT EXISTS idx_emergency_org_assignments_member ON emergency_org_assignments(member_id);
```

设计说明：

- 用两层（`parent_id` 自引用）表达「应急指挥部 / 各应急小组」，不再借用 dept/team/position 三层语义。`duties` 承载组级职责，直接喂预案「应急组织机构及职责」。
- 角色独立成表而非字符串，因为预案要求每个岗位有职责描述，且质检要能判断必填角色。`is_required` 标记质检必填角色，使企业自定义角色名（如「指挥长」）后质检仍可判断。
- 一人多任由 `emergency_org_assignments` 表达：同一 `member_id` 可出现在多条记录中。`UNIQUE (role_id, member_id)` 只防同角色重复指派。
- 应急组织只引用 `member_id`，不引用公司组织节点；公司部门/岗位仅作展示辅助信息（展示层 join，不落库），避免两套语义再次耦合。

## 4. 接口设计

### 4.1 新增 `backend/app/routers/emergency_org.py`

prefix `/enterprises/{enterprise_id}/emergency-org`：

- `GET /` → 整棵应急组织：units 含 roles，roles 含展开的成员信息（`name/phone/position/org_path`）。无数据返回 `[]`。
- `PUT /` → 整树覆盖（与 `/org/nodes` 同风格）：

```json
{"units": [
  {"id": "u1", "parent_id": null, "name": "应急组织机构", "duties": "", "sort_order": 0, "roles": []},
  {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "duties": "统一指挥现场应急处置", "sort_order": 0,
   "roles": [
     {"id": "r1", "name": "总指挥", "duties": "全面负责应急指挥", "sort_order": 0, "is_required": true,
      "member_ids": ["<enterprise_members.id>"]}]}]}
```

提交与返回都是平铺列表，靠 `parent_id` 表达层级，与 `/org/nodes` 完全同风格，前端复用现有组树逻辑（`buildTreeData`）。

校验规则：

- unit 名称非空、`id` 唯一、`parent_id` 存在且无环
- role 名称非空、`unit_id` 存在、同一 unit 内角色名唯一
- `member_ids` 必须属于该企业且 `enabled = true`，否则 422
- 同一 role 内成员不重复

### 4.2 可指派成员

复用现有 `GET /enterprises/{id}/org/members/available`（`backend/app/routers/enterprise_org.py:441`），已返回 `id/name/email/role/position/org_path`，无需新接口。

### 4.3 旧接口处置

- `GET /enterprises/{id}/org-structure`（`backend/app/routers/enterprise_sub.py:31`）：保留，返回应急组织的向后兼容视图 `[{group_key, group_name, responsibilities, members:[{name,position,phone,role}]}]`，供历史调用方兜底。
- `PUT /enterprises/{id}/org-structure`（`backend/app/routers/enterprise_sub.py:38`）：**下线**，返回 410 并提示改用应急组织接口。它是「两种格式互相覆盖」的根源。
- `frontend/src/services/enterpriseService.ts` 的 `getOrgStructure` 改调新接口，`updateOrgStructure` 删除。
- `frontend/src/components/enterprise/OrgStructureEditor.tsx`（旧分组手动编辑器）删除，职责由应急组织页与组织与人员页覆盖。

### 4.4 校验复用

`backend/app/services/enterprise_org_service.py:26` `validate_org_tree` 与 `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx:124` `validateNodes` 是同一套规则的重复实现。本次抽出后端通用校验（新建 `backend/app/services/org_tree_validate.py`）供公司树与应急组织共用，避免第三次抄写；前端保持现有实现，仅调整提示文案。

## 5. 消费方切源清单

已全量核实（`rg -n "org_structure" backend/app`），分为两组。

### 5.1 改为读应急组织（应急语义）

| 位置 | 现状 | 改法 |
|---|---|---|
| `backend/app/routers/generation.py:160` `_normalize_org_groups` | 从 `org_structure` 归一应急小组喂章节提示词 | 改从应急组织取组与成员 |
| `backend/app/routers/generation.py:209` `_build_org_chart_mermaid` | 组织架构图取 `org_structure` | 改从应急组织生成 |
| `backend/app/routers/generation.py:474` `_collect_enterprise_data` | `org_structure` 经 `_merge_org_members` 注入 AI | 应急组织以同一 key 注入，提示词模板不改 |
| `backend/app/routers/generation.py:612` | 用成员表补节点成员 | 删除，成员由应急组织指派提供 |
| `backend/app/routers/sections.py:14` `_render_org_structure_html`、`:72-77` autofill | 章节自动填充取 `org_structure` | 改取应急组织；为空时 400「请先维护应急组织」 |
| `backend/app/routers/export.py:282` `_build_signers_from_org`、`:380` | DOCX 签署人取 `org_structure` | 改取应急组织 |
| `backend/app/services/chat_dispatch.py:1092` | 同上（对话通道） | 改取应急组织 |
| `backend/app/services/plan_quality_service.py:182` | 人名一致性比对组织架构 | 改比对应急组织 |
| `backend/app/services/plan_quality_service.py:280` | 联系电话完整性检查 | 改查应急组织 |
| `backend/app/services/plan_quality_service.py:292` | 关键岗位（总指挥/副总指挥）覆盖 | 改查应急组织角色的 `is_required` |
| `backend/app/services/resource_investigation_service.py:84` | 资源调查报告 AI 入参带 `org_structure` | 改带应急组织 |
| `backend/app/services/prompt_cache.py:306` | `org_chart` 图模板变量 `{{org_structure}}` | 变量名保留，注入内容改应急组织 |
| `backend/app/services/onboarding_service.py:48/110` `_org_done` | 完成度判定找「总指挥」 | 改查应急组织角色；`:16/:28` 标签改「应急组织」 |
| `backend/app/services/enterprise_org_service.py:157` `suggest_org_tree` | 提示词为「企业组织架构专家」，产出含应急岗位 | 改纯公司口径（部门/班组/岗位） |

`prompt_cache.py` 的 `{{org_structure}}` 变量名保持不变，避免改动数据库中的提示词模板，缩小回归面。

### 5.2 保持读公司组织架构（公司语义）

| 位置 | 现状 | 改法 |
|---|---|---|
| `backend/app/services/work_ticket_service.py:379-429` | 按 `org_node_id` 沿组织树向上匹配会签单位 | 改走 `member_positions`，兼岗人员也能被认到 |
| `backend/app/routers/hazard_management.py:2441` | 隐患报表按 `org_node_id` 解析部门名 | 不改，主岗镜像列语义不变 |
| `backend/app/routers/enterprise_org.py:441` `/org/available` | 责任人选择器，返回 `org_path` | 保留主岗路径，是否追加兼岗路径由实现计划决定 |
| `backend/app/routers/enterprise_org.py:405-437` Excel 导入 | 部门/班组/岗位建节点 | 改为同时写 `member_positions` |

## 6. 页面变化

| 页面 / 入口 | 现在 | 拆开后 |
|---|---|---|
| 驾驶舱模块导航 `frontend/src/components/enterprise/cockpit/ModuleNav.tsx` | 仅「组织架构 ORG」入口 | 增加「应急组织 EMERGENCY」→ `/enterprises/:id/emergency-org` |
| 组织与人员管理 `/enterprises/:id/org` | 空树自动播种应急组织；有「应用预置应急组织」按钮；成员表「部门班组」单值 | 只放公司部门/班组/岗位；删除播种与预置按钮；成员表「部门班组」列改「任职」，显示主岗 + 兼岗标签；成员弹窗组织节点改多选（主岗必选）；「岗位」列保留为公司职位 |
| 应急组织页 `/enterprises/:id/emergency-org`（新增） | 不存在 | 左：应急组织树（指挥部 + 小组，可增删改、调序、填职责）；右：选中组的角色列表、各角色指派人员、可指派人员选择器；顶部：「应用预置应急组织」（复用 `PRESET_EMERGENCY_GROUPS`）与「保存」 |
| Onboarding「组织架构」步骤 `frontend/src/pages/Onboarding/StepOrg.tsx` | 提示语为「突发事件谁来指挥」；AI 候选为应急小组；采纳写旧 `org_structure` 格式 | 改名「应急组织」，采纳写新接口；交互与 UI 基本不变（用户已确认方案 A）。公司组织架构不在 onboarding 内建，由组织与人员页或 Excel 维护 |
| 预案章节编辑器 | 自动填充与生成取数来自 `org_structure` | 页面 UI 不变，仅取数改源 |
| 隐患、作业票页面 | 取数来自公司组织树 | 不变 |

## 7. 存量数据迁移

### 7.1 DDL

`backend/db_migration_20260918_emergency_org_split.sql`：建 §3.2 三张表与 `member_positions`，全部 `IF NOT EXISTS`，可重复执行。DDL 与数据搬迁分离。

### 7.2 数据搬迁

`backend/scripts/migrate_emergency_org_split.py`，按企业循环，幂等（已搬迁的企业跳过），支持 `--dry-run`。脚本先判定企业属于哪种存量形态，再走对应分支。

**形态 A：树格式（含 `preset-org-root` 根）**

1. 识别：查找 `org_structure` 中 `id == "preset-org-root"`（或 `parent_id` 为空且 `name == "应急组织机构"`）的子树。
2. 建 units：子树根节点 → 顶层 unit；根节点的**直接子节点一律建为 group unit**，不按 `type` 过滤（实测存在 `node-5` 这种 `type = dept` 但语义是应急小组的脏数据，按 type 过滤会漏迁）。
3. 建 roles：每个 group 下 `type == "position"` 的节点 → role；名称含「总指挥」「副总指挥」的置 `is_required = true`。
4. 建 assignments：查询该企业 `enterprise_members` 中 `org_node_id` 落在被搬迁子树内的成员，按角色建指派，一人多节点时全部保留。
5. 清理：把子树节点从 `org_structure` 移除；被移除节点上的 `enterprise_members.org_node_id` 置空；再按剩余公司树为成员重建 `member_positions`。

**形态 B：旧分组格式（含 `group_key`）**

1. 识别：`org_structure` 中存在带 `group_key`/`group_name` 的对象。
2. 建顶层 unit「应急组织机构」，6 条分组全部作为其下的 group unit，`group_name` 作为名称。
3. 建 roles：按成员 `role` 码映射派生角色，`chief → 总指挥`、`deputy → 副总指挥`、`leader → 组长`、`member → 组员`；同组同角色只建一条；`总指挥`/`副总指挥` 置 `is_required = true`。
4. 建成员与指派：该形态成员内嵌且未登记 `enterprise_members`，脚本按 `(name, phone)` 在企业内查重，不存在则新建 `enterprise_members` 记录（`name`/`phone`/`position`，`user_id` 为空，`enabled = true`），再按角色建 assignment。**这一步不能省**，否则形态 B 企业的人员会在迁移中丢失。
5. 清理：整个 `org_structure` 置空。

**共同收尾**：每企业输出比对日志——搬迁 units/roles/assignments/新建成员条数与剩余公司节点数，与迁移前快照逐项核对；同名兄弟单元（如实测中同时存在的部门型与班组型「应急指挥部」）**不自动合并**，在日志中单独列出，交用户在页面上处理。

### 7.3 迁移后的用户可见结果

生产库 4 家企业的实际结果（迁移前后节点数已逐项核对）：

| 企业 | 迁移前 | 迁移后：组织页 | 迁移后：应急组织页 |
|---|---|---|---|
| 西安宝岳空间科技有限公司 | 37 节点（26 应急 + 11 公司） | 11 个公司节点（公司 → 三个事业部 → 技术开发 → 6 个岗位） | 顶层「应急组织机构」+ 7 个子单元（6 个小组 + 1 个无角色的部门型「应急指挥部」）+ 18 个角色；3 条指派：总指挥=刘昕野、副总指挥=赵志龙、成员=程磊 |
| 延长壳牌石油有限公司（西安明光路加油站） | 25 节点（全部为未编辑的完整预置） | 0 个，需用户补建公司架构 | 顶层 + 6 个小组 + 18 个角色，无指派 |
| 陕西宝岳测绘有限公司 | 6 条旧分组、28 名内嵌成员 | 0 个 | 顶层「应急组织机构」+ 6 个小组 + 按 `role` 码派生的角色；新建 28 条 `enterprise_members` 与对应指派 |
| 两次编辑测试 | 1 条分组（测试数据） | 0 个 | 1 个小组，无成员 |

信息不减少，只是归位。需要注意的是：延长壳牌与陕西宝岳测绘迁移后公司架构为空，作业票会签与隐患责任人暂时无人可选，属于预期状态——这两家企业的公司架构本来就没建过，需要用户补录。

### 7.4 回滚

搬迁前把每家企业原始 `org_structure` 备份到 `output/migrations/org_split_<时间戳>.json`，回滚时按该文件还原即可。

## 8. 错误处理与边界

- 整树保存：unit/role 名称、唯一性、parent 存在、无环校验失败返回 422，并指出具体节点名。
- 指派校验：`member_ids` 含非本企业或已停用成员 → 422，并指明成员。
- 删除 unit/role：由 `ON DELETE CASCADE` 级联清理 roles 与 assignments；前端删除前二次确认并提示「将同时移除该组下的角色指派」。
- 停用成员：`enabled = false` 后该成员从可指派列表消失，已有指派保留（预案仍需显示历史任职）；预案质检对停用成员给提示级告警。
- 章节自动填充：应急组织为空 → 400「请先维护应急组织」。
- 预案质检：缺必填角色 → 沿用现有「档案缺岗位」告警，文案改为「应急组织缺总指挥/副总指挥」。
- 无 AI 配置：`suggest_org_tree` 降级行为不变。

## 9. 测试策略

### 9.1 后端新增

- `backend/tests/test_emergency_org.py`：三张表模型元数据、整树校验（名称/环/重复/跨企业成员）、整树覆盖幂等、一人多角色指派、删除级联、停用成员过滤。
- `backend/tests/test_member_positions.py`：一人多岗写入、主岗镜像列同步、唯一约束（同成员仅一个主岗、同节点不重复）。

### 9.2 后端改造

- `test_enterprise_org.py`：只接受公司树
- `test_plan_quality.py`：质检改读应急组织（必填角色缺失、人名不一致、缺电话）
- `test_plan_autofill.py`：章节自动填充改读应急组织 + 空数据 400
- `test_generation_enterprise_data.py`、`test_plan_diagram_prompts.py`、`test_plan_number.py`、`test_plan_review_routes.py`、`test_thinking_brief.py`、`test_chat_generate_plan.py`：注入点改源后更新断言
- 作业票会签测试：新增「兼岗人员参与会签」用例
- `test_onboarding_completion.py`、`test_onboarding_routes.py`：模块改名与完成度判定改查应急组织
- `test_hazard_dashboard_api.py`、`test_enterprise_update.py`、`test_risk_event_chemical.py`：确认主岗镜像列语义不变后回归

### 9.3 前端

- `frontend/src/services/emergencyOrgService.test.ts`（新增）：URL 与参数断言
- `frontend/src/services/enterpriseOrgService.test.ts`：更新 URL，删除 `updateOrgStructure` 相关断言
- `frontend/src/utils/orgMerge.test.ts`：`mergeOrgNodes` 保留用于公司树；新增应急组织预置合并 `mergeEmergencyUnits` 用例
- `tsc -b` exit 0、`eslint` 改动文件 exit 0、`vitest run` 全绿

### 9.4 验收

- 后端全量回归基线 1785 passed / 4 failed（4 个历史失败）不下降；前端 274 passed 基线不下降
- 真机冒烟（容器 `emergency-plan-frontend`）：组织页无应急节点；应急组织页数据齐全可编辑保存；Onboarding 步骤改名后 AI 候选可采纳；预案「应急组织机构及职责」自动填充取到正确人员；导出 DOCX 签署页人员正确；作业票会签在兼岗场景下能取到审批人
- 迁移脚本在 dev 库连跑两次（幂等），逐企业数字与迁移前快照一致

## 10. 涉及文件

新增：

- `backend/db_migration_20260918_emergency_org_split.sql`
- `backend/scripts/migrate_emergency_org_split.py`
- `backend/app/models/emergency_org.py`
- `backend/app/schemas/emergency_org.py`
- `backend/app/services/emergency_org_service.py`
- `backend/app/services/org_tree_validate.py`
- `backend/app/routers/emergency_org.py`
- `backend/tests/test_emergency_org.py`、`backend/tests/test_member_positions.py`
- `frontend/src/types/emergencyOrg.ts`
- `frontend/src/services/emergencyOrgService.ts`、`frontend/src/services/emergencyOrgService.test.ts`
- `frontend/src/pages/Enterprise/EmergencyOrgPage.tsx`

修改：

- `backend/app/main.py`（注册 router）
- `backend/app/models/enterprise_org.py`（`member_positions` 关系）
- `backend/app/routers/enterprise_sub.py`（PUT 下线、GET 兼容视图）
- `backend/app/routers/enterprise_org.py`（校验复用、导入写 `member_positions`、可指派列表）
- `backend/app/routers/generation.py`、`backend/app/routers/sections.py`、`backend/app/routers/export.py`
- `backend/app/services/chat_dispatch.py`、`plan_quality_service.py`、`onboarding_service.py`、`resource_investigation_service.py`、`work_ticket_service.py`、`enterprise_org_service.py`
- `frontend/src/components/enterprise/cockpit/ModuleNav.tsx`、`frontend/src/routes/index.tsx`
- `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`
- `frontend/src/pages/Onboarding/StepOrg.tsx`、`frontend/src/pages/Onboarding/OnboardingPage.tsx`
- `frontend/src/services/enterpriseService.ts`、`frontend/src/types/enterprise.ts`

删除：

- `frontend/src/components/enterprise/OrgStructureEditor.tsx`

## 11. 决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 应急组织存储形态 | 真表（3 张） | 需被预案生成、章节填充、导出、质检同时查询，且要引用完整性校验；再塞 JSONB 会重复现有混乱 |
| 公司一人多岗 | 新增 `member_positions`，`org_node_id` 降为主岗镜像 | 一次改动同时满足多岗需求与既有消费方零改动 |
| 旧 `PUT /org-structure` | 下线（410） | 它是两种格式互相覆盖的根源，保留即持续制造脏数据 |
| 旧 `GET /org-structure` | 保留兼容视图 | 外部或历史调用兜底，成本低 |
| 应急组织与公司节点关系 | 只引用 `member_id`，不引用公司节点 | 应急角色与公司岗位是两套语义，耦合会再次限制一人多岗 |
| `{{org_structure}}` 提示词变量名 | 不改名，只换注入内容 | 避免改动数据库提示词模板，缩小回归面 |
| Onboarding 处理 | 仅改名「应急组织」，不加公司架构步骤 | 用户已确认方案 A |

---

**规格文档** `docs/superpowers/specs/2026-09-18-org-vs-emergency-org-design.md`
**下一步** 用户审查通过后调用 writing-plans 技能生成实现计划
