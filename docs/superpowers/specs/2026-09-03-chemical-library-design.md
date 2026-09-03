# 危险化学品公共库（选择预填）设计

日期：2026-09-03
状态：已获用户逐节批准（决策：A 系统级公共库 / 方案 1 快照复制 / C 管理员维护+台账收录 / 形态 1 两步式选择 / 方案甲 强类型新表）
范围：桌面 Web（企业详情"危险化学品"Tab + 新企业引导同组件复用 + 系统设置管理员页）；移动端不在本期范围

## 1. 背景与目标

现状：危化品是企业级数据（`hazardous_chemicals`，挂在 `enterprise_id` 下），
添加时手动填写 18 个字段或走 AI 生成批量导入。数据库实况（31 条 / 3 企业）
显示同类化学品在不同企业重复录入（如次氯酸钠溶液出现 2 次），品名命名混乱
（"乙醇"与"乙醇（酒精）"并存、存在乱码名）。MSDS 属性（闪点、爆炸极限、
健康危害、急救措施等）本质是公共标准数据，不应每家企业各录一份。

目标：建立系统级公共危化品库；企业添加时从库中选择，选中后标准字段自动预填
（可再编辑），用户只补企业私有信息（存放位置、最大储存量）即可保存。

## 2. 已确认决策

1. **定位**：系统级公共化学品库（跨企业共享），管理员维护，参照系统设置中
   "法规库管理 / 数据字典管理"的既有模式（admin/super_admin 角色 + 设置菜单）。
2. **数据关系（快照复制）**：库条目负责预填；保存时把标准属性复制成企业台账
   记录，同时记 `library_id` 来源。库条目后续修订不自动改动企业已有记录。
   企业侧现有链路（添加/编辑/删除、预案注入、报告数据加载）零改动。
3. **增长机制**：管理员后台维护 + 从企业台账"一键收录"；企业搜不到时照旧手动
   填写，不设企业"建议入库"审核流。
4. **企业侧交互（两步式）**：点"添加危险化学品"→ 打开"化学品库选择"弹窗 →
   选中 → 进入预填表单（标准字段可改）→ 补私有字段 → 保存。
5. **存储（强类型新表）**：新建 `chemical_library` 表，字段与企业台账对齐但
   去掉企业私有字段；企业表加 `library_id`（FK，`ON DELETE SET NULL`）。

## 3. 数据模型

新表 `chemical_library`（系统级，无 `enterprise_id`）：

| 分组 | 列 | 类型 | 约束 |
|---|---|---|---|
| 标识 | `id` | UUID | PK，默认 uuid4 |
| 标识 | `name` | VARCHAR(200) | NOT NULL |
| 标识 | `cas_no` | VARCHAR(50) | 可空；部分唯一索引（非空时唯一） |
| 标识 | `un_no` | VARCHAR(20) | 可空 |
| 理化 | `physical_state` | VARCHAR(200) | 可空 |
| 理化 | `flash_point` | VARCHAR(50) | 可空 |
| 理化 | `explosion_limit` | VARCHAR(50) | 可空 |
| 理化 | `ignition_temp` | VARCHAR(50) | 可空 |
| 理化 | `density` | VARCHAR(50) | 可空 |
| 理化 | `boiling_point` | VARCHAR(50) | 可空 |
| MSDS | `health_hazard` | TEXT | 可空 |
| MSDS | `fire_hazard` | TEXT | 可空 |
| MSDS | `leak_response` | TEXT | 可空 |
| MSDS | `storage_transport` | TEXT | 可空 |
| MSDS | `first_aid` | TEXT | 可空 |
| MSDS | `protective_measures` | TEXT | 可空 |
| 审计 | `created_at` / `updated_at` | TIMESTAMPTZ | server_default now |

企业表 `hazardous_chemicals` 增加一列：

- `library_id`：UUID 可空，FK → `chemical_library.id`，`ON DELETE SET NULL`，
  带索引。表示该企业记录来自哪条库条目（快照来源追溯）。
- `location`、`max_storage` 仍是企业私有字段，只存在于企业表，不入库。

迁移脚本：`backend/db_migration_20260903_chemical_library.sql`
（建表 + 部分唯一索引 + 加列 + 外键 + 回滚注释，沿用项目 db_migration 惯例）。
模型与 schema 同步新增/修改；`main.py` 注册新 router。

## 4. 查重规则

- CAS 非空的库条目：对 `cas_no` 建部分唯一索引（`WHERE cas_no IS NOT NULL`），
  同一 CAS 全库只允许一条——CAS 是标准化学品的稳定标识。
- CAS 为空（混合物，如玻璃水、化油器清洗剂）：应用层按 `name` trim 后精确
  匹配判重，重复则拒绝新增/收录。
- 新增与收录统一走后端校验（不依赖前端）；冲突返回 409 + 可读文案：
  "库中已存在该 CAS 的条目（{name}），可改为编辑该条目"。
- 收录时宁可拒绝让管理员人工判断，也不自动合并，保数据质量。

## 5. 后端 API

新 router `chemical_library`（注册前缀 `/api/v1`，路径 `/chemical-library`）：

| 方法与路径 | 权限 | 说明 |
|---|---|---|
| `GET /chemical-library` | 所有登录用户 | 分页列表；`keyword` 同时匹配 name/cas_no/un_no（`ilike`）；返回完整字段供预填，无需单独详情端点 |
| `POST /chemical-library` | require_admin | 新增库条目；查重冲突 409 |
| `PUT /chemical-library/{id}` | require_admin | 编辑库条目（不可改名到与既有条目冲突） |
| `DELETE /chemical-library/{id}` | require_admin | 删库条目；企业快照不受影响（`library_id` 被 FK 置空） |
| `POST /chemical-library/collect` | require_admin | 收录企业台账：body `{enterprise_id, chemical_id}`；查重通过则建库条目并回填该企业记录的 `library_id`；企业记录不存在 404，冲突 409 |

现有企业侧端点仅做最小扩展：

- `POST /enterprises/{enterprise_id}/chemicals` 与
  `PUT .../chemicals/{chemical_id}`：body 增加可选 `library_id`，原样透传存储。
- `HazardousChemicalResponse` 与前端类型增加 `library_id`。

## 6. 前端改动

### 6.1 管理员：化学品库管理页

新增 `frontend/src/pages/Settings/ChemicalLibraryManagePage.tsx`：

- 入口：系统设置菜单"化学品库管理"（仅 admin/super_admin 可见，对齐
  法规库管理菜单的 proMode + hasMenu 注册方式；需要同时更新 menuMap 与权限）。
- 库条目表格：品名 / CAS / UN / 物理状态 / 闪点 / 更新时间 / 操作
  （编辑、删除带 Popconfirm，文案注明"仅删除库条目，企业已添加数据不受影响"）。
- 新增 / 编辑：Drawer 表单，字段按"标识 / 理化性质 / MSDS"分组两栏排布，
  形态对齐企业侧 HazardousChemicalsTab 表单（名称必填，其余选填）。
- "从企业台账收录"：按钮 → 弹窗选择企业（可搜索）→ 列出该企业危化品台账
  （名称 / CAS / 存放位置 / 最大储存量）→ 每条"收录"操作；后端 409 冲突时
  弹出明确提示，409 文案带库中已有条目名称；收录成功 toast 并刷新列表。

### 6.2 企业侧：危险化学品 Tab（两步式添加）

组件：新增 `ChemicalLibraryPickerModal`（可放
`frontend/src/components/enterprise/`），改造 `HazardousChemicalsTab`：

1. 点"添加危险化学品"→ 打开选择弹窗，不再直接打开空表单。
2. 选择弹窗：顶部关键字搜索框（名称/CAS/UN 模糊搜索）+ 分页列表；每行展示
   品名、CAS、物理状态、闪点，帮助确认；点击行选中。
3. 选中后：关闭选择弹窗，打开现有编辑表单，并把库条目的标准字段 `form.setFieldsValue`
   预填（字段可改），`library_id` 随提交携带。
4. 弹窗空库 / 搜索无结果：展示空态 + "未找到？手动填写"按钮 → 关闭弹窗打开
   空表单（同现状，不携带 `library_id`）。
5. "编辑已有记录"维持现状：直接打开表单回填。
6. 列表对 `library_id` 非空的行显示小标签"标准库"（低成本；如后续觉得噪音可去掉）。

新企业引导（Onboarding StepRiskChemical）复用同一 `HazardousChemicalsTab`
组件，自动获得该能力，不做单独改动。

### 6.3 服务层

`hazardousChemicalService.ts` 或新增 `chemicalLibraryService.ts`：

- `listChemicalLibrary(keyword?, page?)`（企业选择器用）
- 管理端：`createLibraryItem / updateLibraryItem / deleteLibraryItem /
  collectFromEnterprise`（对应 5 节 API）

类型：`HazardousChemicalCreate/Update/Response` 增加 `library_id`；
新增 `types/chemicalLibrary.ts`（库条目类型 = 无 location/max_storage、
无 enterprise_id 的条目结构 + id/created_at/updated_at）。

## 7. 错误处理

- 库条目删除：只影响库本身，页面文案明确企业数据不受影响（FK SET NULL）。
- 收录：企业记录不存在 404；库冲突 409 带库中已有条目信息。
- 新增/编辑库条目查重冲突：409 可读文案。
- 企业选择器：加载失败可重试；空库/无结果显示空态 + 手动填写兜底，不阻塞用户。
- 非管理员调用管理端点：沿用 require_admin 的 403。

## 8. 测试与验收

后端（容器内 pytest）：

- `chemical_library` CRUD（增改查删）+ 权限（普通用户访问管理端点 403）。
- 查重：CAS 相同（无论名称写法是否一致，如"乙醇"与"酒精"同 CAS 67-56-1）
  重复新增 409；CAS 均为空且 trim 后名称相同（如"玻璃水"）重复新增 409；
  编辑改名导致与既有条目冲突同样 409。
- 收录：成功建条目 + 回填源企业记录 `library_id`；重复收录 409；企业记录
  不存在 404。
- 企业创建/更新携带 `library_id` 透传成功；删除库条目后企业记录 `library_id`
  自动置空（FK SET NULL）。

前端（tsc + vitest）：

- 选择器"选中 → 预填"与"手动填写兜底"分支（组件逻辑抽可测函数）；
- service 新函数返回结构；类型透传编译通过。

端到端冒烟：

1. 管理员建一条库条目（含 CAS/MSDS 字段）。
2. 企业侧"添加危险化学品"→ 搜索命中 → 选中 → 表单预填 → 补存放位置/最大储存量
   → 保存 → 台账列表带"标准库"标签。
3. 管理员"从企业台账收录"该企业另一条无来源记录 → 成功，源记录回填来源。
4. 再次收录同一 CAS → 409 提示。

## 9. 范围外（YAGNI）

- 库条目修订后对企业已有记录的一键同步/更新提示（本期只存 `library_id`，不做联动；
  后续可在列表对库版本变更加提示）。
- AI 生成结果自动匹配库条目（本期生成结果不带 `library_id`；后续让生成结果附带
  `library_id` 即可复用选择器链路）。
- 企业"建议入库"审核流（已由决策 C 排除）。
- 移动端适配（当前移动端无危化品编辑入口；如存在另行评估）。
- 库条目"参考存放位置/典型储量"等企业私有字段的库级模板值。

## 10. 上线数据整理

不写死种子脚本。管理员用"从企业台账收录 + 手工新增"把现有 31 条中规范条目
整理入库（乱码、重名条目由人工筛除/修正），库从真实数据自然增长。

## 11. 预计改动文件

后端：

- `backend/app/models/chemical_library.py`（新）
- `backend/app/models/hazardous_chemicals.py`（加 library_id 列）
- `backend/app/schemas/chemical_library.py`（新）
- `backend/app/schemas/hazardous_chemicals.py`（加 library_id）
- `backend/app/routers/chemical_library.py`（新，含 collect）
- `backend/app/routers/hazardous_chemicals.py`（body 透传 library_id）
- `backend/app/main.py`（注册 router）
- `backend/db_migration_20260903_chemical_library.sql`（新）
- `backend/tests/test_chemical_library.py`（新）
- `backend/tests/test_hazardous_chemicals.py`（若存在则补 library_id 用例）

前端：

- `frontend/src/types/chemicalLibrary.ts`（新）
- `frontend/src/types/hazardousChemical.ts`（加 library_id）
- `frontend/src/services/chemicalLibraryService.ts`（新，或并入现有 service）
- `frontend/src/services/hazardousChemicalService.ts`（create/update 带 library_id）
- `frontend/src/components/enterprise/ChemicalLibraryPickerModal.tsx`（新）
- `frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx`（两步式改造）
- `frontend/src/pages/Settings/ChemicalLibraryManagePage.tsx`（新）
- `frontend/src/layouts/MainLayout.tsx` / `frontend/src/utils/menuMap.ts` /
  `frontend/src/routes/index.tsx`（管理员菜单与路由）
- 对应单测文件
