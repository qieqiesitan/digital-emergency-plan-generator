# 情景化批量开票设计（规格 2 / 共 2 份）

> 范围：C 层（同一作业地点、同一时间段的连开票）
> 依赖：**规格 1**（`values_meta` 来源留痕、措施三态、人员选择器、作业地点锚点、AI 通道）——本规格不重复实现
> 状态：待用户审查

## 1. 背景与目标

### 1.1 背景

现场确认：一次检修通常在同一地点、同一时间段需要**连开多张票**（典型组合：动火 + 受限空间 + 吊装/高处/临时用电）。当前系统里这 N 张票彼此完全独立：同样的申请单位、作业单位、地点、时段、作业内容、风险辨识要填 N 遍；票与票之间没有任何关联记录。而 GB 30871 动火票措施第 15 条明确要求"其他相关特殊作业已办理相应安全作业票"——本应互相印证的信息，现在靠人脑和纸质传递。

实测：真库 8 类票均有实例（28 张），措施种子 584 条，`related_tickets` 字段在 28 张票中全部为空。

### 1.2 目标

1. 一次检修的 N 张票，**共享信息填 1 遍**，开票输入量降到约 1/3
2. 同批票自动互相登记票号（`related_tickets`），并可被措施确认引用
3. 同一地点同一时段的气体检测**录一次、多票共享**，但不豁免 30 分钟时效
4. 各票仍走各自的法定审批流程与门禁——批量只作用于"生成与填写"，**不作用于审批**

### 1.3 非目标（本规格明确不做）

- 不做"作业包模板"（常用组合预设）：先验证作业包本身的使用频率，避免为一个未验证的假设建数据结构
- 不做跨企业/跨时段的票归组；作业包严格限定"同企业 + 同地点 + 同一时段"
- 不做审批合流：包内各票审批链相互独立，不合并会签、不合并待办
- 不做群签/一键批准（触碰法定审批，红线）
- 不做气体检测时效豁免（合规红线）
- 不修改打印票面字段集合：GB 30871 附录 A 的票面样式不变，包信息不新增到法定票面上

## 2. 核心机制

### 2.1 作业包（WorkTicketBatch）

作业包是"一次检修任务"的容器，承载 N 张作业票与共享信息。

```
作业包（同一地点 + 同一时段）
├── 共享信息：申请单位 / 作业单位 / 地点 / 时段 / 作业负责人 / 作业任务描述 / 风险辨识基础
├── 包级气体检测记录（动火与受限空间共享）
└── 作业票 × N（各自类型、级别、专有字段、审批链、状态）
```

状态机：

| 状态 | 含义 | 允许操作 |
|---|---|---|
| `draft` | 包已建，票为草稿 | 改共享信息、增删票、提交票、作废包 |
| `active` | 至少一张票已提交 | 改共享信息（仅影响未提交票）、增票、提交剩余票 |
| `closed` | 包内所有票进入终态（归档/作废） | 只读 |
| `cancelled` | 包被作废 | 只读 |

约束：包内**存在已提交票时不可作废包**（避免已进入审批的票失去上下文）；需先作废对应票。

### 2.2 共享槽位（本规格的规格表）

作业包不按"字段名"共享，而按**语义槽位**共享，再映射到各票种的实际 `field_key`：

| 槽位 | 语义 | 各票种落点 |
|---|---|---|
| `applicant_unit` | 作业申请单位 | 8 类票同名 | 
| `work_unit` | 作业单位 | 8 类票同名 |
| `work_leader` | 作业负责人 | 8 类票同名 |
| `period` | 作业实施时间 | 8 类票同名 `work_period`（datetimerange） |
| `location` | 作业地点 | DHZY→`fire_location`；YXKJ→`space_location`；MBCD→`pipe_position`；PTZY→`dig_location`；DLZY→`road_position`；**GCZY / QZDZ / LSYD→无地点字段**（见下） |
| `content` | 作业任务描述 | 8 类票 `work_content`（作为基础文本，各票可改） |
| `risk_basis` | 风险辨识基础 | 8 类票 `risk_identification`（作为基础文本，各票可改） |
| `related` | 关联票号 | 8 类票 `related_tickets`（**只读，由系统回填**） |

**三个票种没有地点字段**（`GCZY` 高处 / `QZDZ` 吊装 / `LSYD` 临时用电，见 `work_ticket_seed_data.py`）：不为它们新增票面字段（会偏离 GB 30871 附录 A 法定样式），改为把作业地点作为**上下文**注入：写进 `work_content` 的生成提示（规格 1 的 AI 通道输入）与包工作台的醒目提示，由填写人自行决定是否写入作业内容。这是刻意的取舍——合规优先于美观。

每个槽位写入票面时的 `values_meta.source = "batch"`，`source_ref = {batch_id, slot}`，可在票详情页追溯"这一项来自作业包"。

### 2.3 批量开票流程

1. **建包**：填标题（如"3# 罐区阀门更换"）+ 地点锚点（楼层→区域→对象，复用规格 1）+ 时段 + 共享槽位
2. **选票**：勾选本次需要办理的票种与级别（8 类可选，级别按票种联动）
3. **批量生成草稿**：一次事务内为每张票调 `open_ticket`，随后**回填 `related_tickets`**（每张票写入包内其他票号，逗号分隔），全部标记 `batch_id`
4. **逐票补齐**：各票只填"票种专有字段"（`fire_method` / `work_height` / `lift_weight` / `blind_plate_no` / `power_capacity` 等）
5. **逐票提交**（或"批量提交"）：每张票仍走 `validate_before_submit` 全部门禁；批量提交逐票返回结果，失败票单独列出且不影响其他票

第 3 步的票号回填必须在一个事务内完成（先 `flush` 拿到每张票的 `code`，再统一 UPDATE `values`），否则会出现"A 票的关联票号里有 B，B 里没有 A"的不一致。

### 2.4 包级气体检测共享

现状：`work_ticket_gas_tests.instance_id` 非空，检测记录只能属于单张票。同一次检修里动火与受限空间往往在同一时段做同一轮检测，现在要录两遍。

设计：检测记录支持**双归属**——归属某张票（`instance_id`）或归属作业包（`batch_id`），两者恰有其一。

```sql
ALTER TABLE work_ticket_gas_tests ALTER COLUMN instance_id DROP NOT NULL;
ALTER TABLE work_ticket_gas_tests ADD COLUMN batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE CASCADE;
ALTER TABLE work_ticket_gas_tests ADD CONSTRAINT ck_wtgt_owner CHECK ((instance_id IS NULL) <> (batch_id IS NULL));
```

取数与展示规则：

- 票详情、提交校验、打印快照读取"**本票检测 + 所属包级检测**"的合并结果
- 打印票面时，包级记录在前并标注来源（"包级检测"/"本票检测"），票面样式不变
- **30 分钟时效规则不做任何豁免**：包级记录同样受 `GAS_TEST_MAX_AGE` 约束，超时提示"请重新检测"。这正是现场实际流程——作业前统一检测一轮，随即提交相关票

GB 30871 边界（规格内明确，避免误用）：受限空间检测项目（氧含量、可燃气体、有毒气体）与动火点检测（可燃气体）**点位与项目不同**。包级记录定位为"共同基础记录"，各票仍可补充本票专属检测；系统不因存在包级记录而禁止票级补充。

### 2.5 措施与包内票的互相印证

不新建数据结构，复用规格 1 的 `measures_meta`：

- 动火票措施第 15 条（"其他相关特殊作业已办理相应安全作业票，作业现场四周已设立警戒区"）在确认时，若同包存在其他票，确认区展示：`本包已包含：受限空间票 YXKJ-…-0003（已提交）、吊装票 QZDZ-…-0004（草稿）`，作为确认依据（**仅展示，不自动确认**）
- 交叉作业类措施的 `reason_text` 支持从包级共享信息带出（如"交叉作业协调人：张三"），由用户确认后写入
- 包工作台提供"N 条措施涉及本包其他作业"的汇总视图，便于安全员集中核对

### 2.6 AI 在批量场景的用法

复用规格 1 的 `work_ticket_prefill` 能力，输入增加包上下文：

- **包级一次生成**：以包的任务描述 + 地点锚点 + 全部票种为输入，一次生成"风险辨识基础"（3~6 条）
- **各票差异化补充**：每张票在包级基础上补充本票特有危害（如受限空间补充"缺氧/中毒"，吊装补充"起重伤害"），逐票走人工确认
- 这样 N 张票只需 1 次 AI 调用 + N 次轻量补充，而不是 N 次完整调用（省 token，也避免 N 段雷同文本）

## 3. 数据模型与迁移

迁移文件：`backend/db_migration_20260920_work_ticket_batch.sql`（幂等）

```sql
CREATE TABLE IF NOT EXISTS work_ticket_batches (
    id                UUID PRIMARY KEY,
    enterprise_id     UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'draft',   -- draft|active|closed|cancelled
    floor_id          UUID NULL REFERENCES enterprise_floors(id) ON DELETE SET NULL,
    zone_id           UUID NULL REFERENCES risk_zones(id) ON DELETE SET NULL,
    risk_object_id    UUID NULL REFERENCES risk_objects(id) ON DELETE SET NULL,
    location_text     VARCHAR(500) NULL,
    work_period_start TIMESTAMPTZ NULL,
    work_period_end   TIMESTAMPTZ NULL,
    shared_values     JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_base      TEXT NULL,
    risk_basis        TEXT NULL,
    created_by        UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wtb_enterprise_status ON work_ticket_batches(enterprise_id, status);

ALTER TABLE work_ticket_instances ADD COLUMN IF NOT EXISTS batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_wti_batch ON work_ticket_instances(batch_id);

ALTER TABLE work_ticket_gas_tests ALTER COLUMN instance_id DROP NOT NULL;
ALTER TABLE work_ticket_gas_tests ADD COLUMN IF NOT EXISTS batch_id UUID NULL REFERENCES work_ticket_batches(id) ON DELETE CASCADE;
-- PG 不支持 ADD CONSTRAINT IF NOT EXISTS，用 DO 块保证可重复执行
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_wtgt_owner') THEN
        ALTER TABLE work_ticket_gas_tests ADD CONSTRAINT ck_wtgt_owner
            CHECK ((instance_id IS NULL) <> (batch_id IS NULL));
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_wtgt_batch ON work_ticket_gas_tests(batch_id);
```

ORM 同步：新增 `WorkTicketBatch` 模型；`WorkTicketInstance.batch_id`；`WorkTicketGasTest.batch_id` + `instance_id` 改 Optional。

前置依赖：规格 1 的 **§0 措施数据缺陷（P0）**必须已修复——否则动火/受限空间的措施清单是 106 条（含其他票种措施），§2.5 的"措施与包内票互相印证"会在错误的措施集合上工作。

部署注意：按部署手册 **§8.0.1**（新迁移脚本必须 `docker cp` + 三重核验）与 **§8.0.2**（容器间 `docker cp` 不支持）。CHECK 约束在既有 28 行数据上成立（现有记录 `instance_id` 均非空），需在迁移后核验约束已生效。

## 4. API 设计

沿用统一信封与既有权限函数。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/work-ticket/batches` | 建包（标题/地点锚点/时段/共享槽位） |
| GET | `/work-ticket/batches` | 列表（`enterprise_id` 必填，支持 status 筛选） |
| GET | `/work-ticket/batches/{id}` | 详情：包信息 + 票列表（含各票待补字段数、状态）+ 包级检测 |
| PATCH | `/work-ticket/batches/{id}` | 改共享槽位（`active` 时仅回写到未提交票） |
| POST | `/work-ticket/batches/{id}/tickets` | 批量生成草稿，body `[{ticket_type, level, template_id}]`，事务内回填 `related_tickets` |
| DELETE | `/work-ticket/batches/{id}/tickets/{ticket_id}` | 从包中移除草稿票（仅 `draft` 票） |
| POST | `/work-ticket/batches/{id}/gas-tests` | 新增包级检测记录 |
| POST | `/work-ticket/batches/{id}/submit-all` | 批量提交，逐票返回 `{ticket_id, ok, errors[]}` |
| POST | `/work-ticket/batches/{id}/transition` | 关闭 / 作废（作废时校验包内无已提交票） |

读接口权限：`ensure_enterprise_visible`（企业主与绑定成员按既有规则收窄）；写接口：`ensure_enterprise_owned`。

## 5. 前端交互

新增两个页面与一个入口：

| 页面 | 路径 | 内容 |
|---|---|---|
| 新建作业包 | `/enterprises/:id/work-ticket/batches/new` | 标题 + 地点锚点选择 + 时段 + 共享槽位表单 + 票种多选（含级别） |
| 作业包工作台 | `/enterprises/:id/work-ticket/batches/:batchId` | 顶部共享信息（可折叠编辑）；中部票卡片列表（状态、待补项、检测数、进入填写/提交）；底部包级检测录入 + 批量提交 |

列表页 `WorkTicketListPage` 增加"作业包"筛选与入口；票详情页显示"所属作业包"链接与同包票号。

**票卡片的"待补项"计数**：进入工作台即调用规格 1 的预填接口，算出每张票还剩几个必填字段未确认（预填已确认的不计），让用户一眼看到"还差多少"。

**批量提交的失败呈现**：逐票结果列在底部抽屉，失败票给出具体问题清单（复用 `validate_before_submit` 文案），点击直接跳到该票的对应步骤。

## 6. 错误处理与降级

| 场景 | 行为 |
|---|---|
| 批量生成中某票模板缺失/未启用 | 事务整体回滚，返回具体票种，不产生半成品包 |
| 包内票号回填失败 | 事务回滚（不允许"部分关联"状态） |
| 改共享槽位时部分票已提交 | 仅回写未提交票，返回受影响票数；已提交票提示"如需修改请作废重开" |
| 包级检测超过 30 分钟 | 提交时按既有规则阻断并提示重测 |
| 包内某票被作废 | 该票从关联票号列表中移除（其余票的 `related_tickets` 同步更新） |
| 包被作废但有已提交票 | 拒绝并提示先处理对应票 |
| 未维护风险数据的企业 | 地点锚点退化为自由文本（同规格 1 降级路径） |

## 7. 测试与验证

**后端单测**（`backend/tests/test_work_ticket_batch.py`）

1. 槽位映射：8 类票逐类断言 `field_key` 落点正确（含 3 个无地点字段票种的跳过逻辑）
2. 票号回填：3 票包生成后，每票 `related_tickets` 恰好含另外 2 票，且顺序稳定
3. 事务性：注入一张票模板缺失 → 整体回滚，库中 0 新增
4. 检测合并：票详情/校验/打印快照三处均能读到"本票 + 包级"记录
5. 30 分钟规则：包级记录超时同样阻断（回归锁）
6. 包状态机：draft→active→closed；有已提交票时作废被拒
7. 改共享槽位：仅未提交票被更新，计数正确
8. 批量提交：1 票失败不影响其余票，失败原因逐票正确

**前端**

1. 工作台单测：票卡片待补项计数、批量提交结果抽屉
2. `tsc -b` / `vitest` / `eslint` 全绿

**端到端验证**（`output/playwright/e2e-20260920/scripts/`）

1. 探针：建 3 票包（动火 + 受限空间 + 吊装）→ 断言共享字段一次写入 3 票、`related_tickets` 互含、包级检测被两票读到
2. 浏览器实测：完整走一遍建包 → 补齐 → 批量提交，断言 0 console error
3. 反向验证：包内 1 票故意漏字段 → 批量提交后该票失败、其余成功，抽屉文案正确
4. 合规回归：包级检测超 30 分钟后提交被阻断

## 8. 工作量与风险

粗估 **4~6 人日**：后端（模型 + 迁移 + 包服务 + 8 个端点 + 打印合并）约 3 人日；前端（两个页面 + 工作台交互）约 2 人日；测试与探针 1 人日。

| 风险 | 缓解 |
|---|---|
| 批量生成出错留下半成品包 | 全流程单事务 + 回滚测试（验收项） |
| 包级检测被误当作"一测到底" | 不豁免 30 分钟；票面标注来源；规格内写明点位差异边界 |
| 用户把批量提交理解为"批量批准" | 文案明确"提交仅进入各自审批流程"；不做任何批准入口 |
| 改共享信息导致票据内容不一致 | 仅未提交票可回写，已提交票只提示；操作写审计日志 |
| 三个票种无地点字段导致信息丢失 | 地点作为 AI/文本上下文注入 + 工作台提示；不为美观改法定票面 |

## 9. 验收清单

- [ ] 迁移已应用，既有 28 张票全部可正常读取、提交、打印（`batch_id` 为 NULL）
- [ ] 建包可完成，共享槽位一次填写
- [ ] 批量生成 3 票后，各票共享字段一致、`related_tickets` 互相包含、`batch_id` 正确
- [ ] 任一票生成失败时整包回滚，库中不留半成品
- [ ] 包级气体检测录一次，动火与受限空间票均能读到并出现在打印票面（标注来源）
- [ ] 包级检测超 30 分钟时提交被阻断
- [ ] 措施确认区能展示同包其他票及其状态，且不自动确认
- [ ] 批量提交逐票校验，失败票不影响其他票，失败原因可跳转处理
- [ ] 包状态机与作废约束按规格生效
- [ ] 改共享信息只影响未提交票，受影响票数有明确反馈
- [ ] 后端 `pytest` 全绿 + `ruff` 全绿；前端 `tsc -b` / `vitest` / `eslint` 全绿
- [ ] 探针与浏览器实测通过，交互动作计数与规格 1 基线一并留档
- [ ] GB 30871 附录 A 票面样式零改动（打印快照对比验证）

## 10. 与规格 1 的边界

本规格**不重复实现**规格 1 已交付的能力：确定性预填与来源留痕、措施三态与判定规则、人员与证照选择器、作业地点锚点、AI 预填通道。规格 2 仅新增：作业包容器、共享槽位映射、票间关联、包级检测归属、批量生成与批量提交。

若规格 1 尚未落地，规格 2 无法独立实施（`related_tickets` 回填与共享槽位都依赖 `values_meta` 的写入约定）。
