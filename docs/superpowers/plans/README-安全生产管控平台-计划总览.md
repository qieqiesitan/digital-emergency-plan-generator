# 安全生产管控平台 · 实现计划总览

> 本文件是全部实现计划的索引与执行纪律。**先读这份，再读具体计划。**
> 配套设计文档：`docs/superpowers/specs/2026-09-17-safety-control-platform-design.md`

---

## 一、计划清单

| # | 计划文件 | 覆盖阶段 | 依赖 | 状态 |
|---|---|---|---|---|
| 1 | `2026-09-17-major-hazard-r-value.md` | P0-1~P0-4 + P0-7 后端 | — | ✅ **已实现并合入 master**（9 任务 / 52 测试 / 0 回归 / 真库端到端通过） |
| 2 | `2026-09-17-llm-gateway-hardening.md` | P0-5 前半（修 B1/B2 + 调用留痕 + 按能力选模型） | — | 📝 **已写待执行**（4 任务） |
| 3 | `2026-09-17-major-hazard-frontend.md` | P0-6 前端 | 计划 1 | ⏳ 待写 |
| 4 | `2026-09-17-major-hazard-report.md` | P0-7 报告导出 | 计划 1、3 | ⏳ 待写 |
| 5 | `2026-09-17-datahub-ingest.md` | P1 数据接入适配层 | 计划 2 | ⏳ 待写 |
| 6 | `2026-09-17-ai-extraction-pipeline.md` | P0-5 后半（资料 → 台账） | 计划 2、5 | ⏳ 待写 |
| 7 | `2026-09-17-cross-module-linkage.md` | P1 关联打通（风险/隐患 ↔ 重大危险源/预案） | 计划 1 | ⏳ 待写 |
| 8 | `2026-09-17-work-ticket-core.md` | P2-0 + P2-a（GB 30871 清洗 + 审批引擎 + 动火/受限空间） | 计划 2、3 | ⏳ 待写 |
| 9 | `2026-09-17-work-ticket-8types.md` | P2-b（其余 6 类 + 归档打印） | 计划 8 | ⏳ 待写 |
| 10 | `2026-09-17-platform-polish.md` | P3（AI 能力注册表 + 跨企业总览） | 计划 2 | ⏳ 待写 |

---

## 二、依赖关系

```
计划 1 (✅ 完成) ──┬─→ 计划 3 前端 ──→ 计划 4 报告导出
                  └─→ 计划 7 关联打通

计划 2 网关 ──┬─→ 计划 5 DataHub ──→ 计划 6 AI 抽取链路
              └─→ 计划 8 作业票核心 ──→ 计划 9 其余 6 类

计划 2 ──→ 计划 10 平台化
```

**可并行的组**：{3, 2} 可同时开工；{5, 7} 可同时开工。
**必须串行的链**：2 → 6（抽取链路依赖网关的留痕与异常语义）；8 → 9（骨架没验证前铺 6 类等于 6 次返工）。

---

## 三、建议执行顺序

1. **计划 2** —— 修的是正在跑的缺陷，越早越好；且它是后续所有 AI 相关计划的地基
2. **计划 3** —— 让计划 1 的后端变成用户能看见、能操作的界面
3. **计划 7** —— 打通已有模块，成本低、价值直观
4. **计划 5** —— 数据接入能力，为计划 6 铺路
5. **计划 6** —— AI 抽取链路（本平台的差异化卖点）
6. **计划 4** —— 报告导出（让结论可交付）
7. **计划 8** —— 作业票核心（最大的一块，45~65 人日）
8. **计划 9** —— 其余 6 类作业票
9. **计划 10** —— 平台化收尾

---

## 四、全局执行纪律（每个计划都适用）

### 4.1 隔离工作区

每个计划开工前用 `superpowers:using-git-worktrees` 建独立 worktree，分支名 `codex/<计划名>`。
**不在 master 上直接实现。**

### 4.2 测试基线

宿主机跑后端的正确姿势：

```bash
# 主仓库后端 venv 可直接复用；在 worktree 的 backend/ 目录下执行即导入 worktree 的代码
"C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe" -m pytest backend/tests -q --ignore=backend/tests/test_autofill_research.py
```

**已知既有失败（4 个，master 上就存在，不是回归）**：

```
test_batch_context.py::test_stream_llm_chunks_yields_each_chunk
test_migration_runner.py::test_baseline_migrations_match_pre_upgrade_scripts
test_prompts_permission.py::test_list_prompts_allowed_for_regular_user
test_security_batch_c.py::test_logout_revokes_access_and_refresh_api
```

另 `test_autofill_research.py` 因缺 `scrapling` 依赖在本机无法收集，已 ignore。

**基线口径：`1549 passed / 4 failed`**（截至 2026-09-17）。新计划完成后失败数不得高于 4，通过数应等于 `1549 + 新增用例数`。

### 4.3 数据库相关验证

需要真库的验证（迁移幂等、端到端接口）**在 worktree 内无法做**——容器挂载的是主仓库。做法：先完成全部纯代码任务并全绿，合并回 master 后再一次性补真库验证。真库验证姿势见计划 1 的验收章节。

### 4.4 数据库容器

PostgreSQL 容器名为 **`emergency-plan-db`**（镜像 `postgres:16`），库名 `emergency_plan`，用户 `postgres`。后端容器 `emergency-plan-backend`。

### 4.5 迁移脚本

- 放 `backend/` 根，命名 `db_migration_YYYYMMDD_<描述>.sql`
- 由 `app/services/migration_runner.py` 启动时按文件名排序自动执行，执行记录写 `schema_migrations`
- **新脚本不要加进 `BASELINE_MIGRATIONS`**（那是给升级前版本已捆绑脚本用的）
- 必须幂等：`CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` / 种子数据用确定性 UUID5 + `ON CONFLICT (id) DO NOTHING`

### 4.6 提交规范

- 每个任务一次 commit，message 末尾带 `（任务 N/M）`
- **只 add 该任务涉及的文件**，严禁 `git add -A`
- **TASKS.md 永不 commit**（项目惯例）

### 4.7 独立脚本的坑

在容器内或独立脚本里使用 `major_hazard` 相关模型时，必须先
`from app.models.user import User  # noqa: F401`，否则 FK 指向 `users` 解析失败报
`NoReferencedTableError`。

---

## 五、计划 1 已交付的资产（后续计划直接复用，不要重建）

**数据层**

| 表 | 说明 |
|---|---|
| `critical_quantities` | GB 18218 表1/表2 临界量，**109 行**（表1 85 + 表2 24） |
| `hazard_beta_factors` | 表3/表4 校正系数 β，**38 行**（表3 14 + 表4 24） |
| `exposure_alpha_factors` | 表5 暴露人员系数 α，5 行 |
| `major_hazard_levels` | 表6 分级阈值，4 行 |
| `major_hazard_units` / `major_hazard_unit_chemicals` | 单元与单元内品种存量 |
| `major_hazard_calculations` | **不可变计算快照**（只追加） |
| `major_hazard_records` | 档案与备案（包保责任人、附件、完整性） |
| `evidence_refs` | 依据层多态表（`owner_type` + `owner_id` + `article_anchor`） |

**服务层**

| 模块 | 用途 |
|---|---|
| `app/services/major_hazard_calc.py` | **纯函数 R 值法引擎**（式(1) 辨识、式(2) 分级），不碰数据库 |
| `app/services/major_hazard_service.py` | 编排：读常量 → 调引擎 → 写不可变快照；`resolve_beta` 实现表3优先/表4回落；`replay_snapshot` 复算核对 |
| `app/services/evidence_service.py` | 挂/查法规依据（幂等） |
| `app/services/chemical_storage_parser.py` | 存量文本 "50吨/3000kg" → (数值, 单位)，解析不出返回 `(None, None)` 不猜测 |

**接口层**（`app/routers/major_hazard.py`，14 个端点，前缀 `/api/v1/major-hazard`）

```
GET  /definitions/critical-quantities        临界量检索（供选物质）
GET  /units                                  单元列表
POST /units                                  建单元
PUT  /units/{id}                             改单元
DELETE /units/{id}                           删单元
GET  /units/{id}/chemicals                   单元品种
PUT  /units/{id}/chemicals                   整体替换品种
POST /units/{id}/compute                     计算并写快照
GET  /units/{id}/calculations                快照列表
GET  /units/{id}/evidence                    查依据
POST /units/{id}/evidence                    挂依据
GET  /units/{id}/record                      查档案
PUT  /units/{id}/record                      建/改档案
```

**注意**：`Decimal` 类型字段经 FastAPI 序列化后是**字符串**（保精度），前端需自行转数值。这是有意行为。

**标准数据源**：`docs/标准数据-GB18218-2018/`（6 个 JSON + 复核 Markdown + 校验报告），生成器 `scripts/gen_major_hazard_seed_sql.py` 可复现（连跑两次逐字节一致）。

**作业票相关标准资产（计划 8 会用）**

| 资产 | 位置 | 内容 |
|---|---|---|
| GB 30871-2022 真原文 | `backend/app/regulations/data/texts/reg_gb_30871_2022.md` | 63KB / 1136 行；第4章通用要求 18 条、第5章动火 32 条、第6章受限空间 10 条、第7章盲板抽堵 12 条、第8章高处 16 条、第9章吊装 16 条、第10章临时用电 8 条、第11章动土 11 条、第12章断路 5 条 |
| **附录A** | 同上 | 表 A.1~A.8 = 8 类作业票的**法定票面样式**，含逐条安全措施清单（带"是否涉及/确认人"列） |
| **附录B 表B.1** | 同上 | 法定"办理部门 / 审核会签 / 审批部门"矩阵（特级动火→主管领导；一级→安全管理部门；二级→基层单位；临时用电→配送电单位；动土→多单位会签 等） |
| **附录B 表B.2** | 同上 | 三联持有与保存规则；B.3 规定作业票至少保存一年、影像至少留存一个月 |

> ⚠️ **计划 8 的前置任务**：该文本有**系统性 OCR 讹字**——"式"出现 **0 次**而"怯"出现 **30 次**（样式→样怯、方式→方怯）；"Ⅱ"出现 0 次而"聂"出现 4 次。**不修就 seed 措施库，用户会在动火票上看到"动火方怯"。** 判据：修复后"式"计数 > 0 且"怯" = 0、"聂" = 0。

---

## 六、明确不做（写进所有计划的非目标）

教育培训 / 考试、应急演练、监测报警与 IoT、SIL 等级评估、AI 视频分析、人员定位、通用 BPMN 工作流引擎、通用 ETL 框架、CA 电子签名、复制对标系统界面与文案。

---

## 七、跨计划的统一设计约束（来自视觉走查确认，见 spec §13.1）

1. 作业票导航：**单入口「特殊作业」+ 页面内类型筛选**，不做 8 个独立菜单
2. 作业票流程模板：**法定环节锁定，可加不可删**
3. 重大危险源计算页：**实时预览 + 手动固化**（改动即刻显示 s/R，点"固化"才写快照）
4. `q_design_max` 来源：**从台账 `max_storage` 带出初值 + 强制人工确认**，界面标注口径差异
5. DataHub 确认粒度：**整批默认全选 + 勾掉错的**，低置信度默认不勾；**拒绝"高置信度自动入库"**

另有三条贯穿全程的硬门槛（spec §1.4）：

- R 值计算必须可复算（快照留全量输入）
- AI 抽取的数据必须带来源与置信度，**未经人工确认不得入库**
- 状态变更全留痕
