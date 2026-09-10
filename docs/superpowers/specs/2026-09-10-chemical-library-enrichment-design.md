# 化学品库字段富集设计（UN 号 / 理化性质 / GHS 危害分类）

日期：2026-09-10
状态：已获用户分节批准（口径：甲 / 甲 / 乙 + 交付方案 1）

## 1. 背景与目标

`chemical_library` 已预录入《危险化学品目录（2022 调整版）》2997 条，但除了品名、
别名、CAS、剧毒备注外，其余字段（UN 号、物理状态、闪点、爆炸极限、引燃温度、
密度、沸点、健康危害、火灾爆炸危险等）全部为空——《目录》本身不含这些信息。

本设计的目标：在**不引入 AI 生成数据**、**只填可溯源数值**的前提下，用离线批处理
为库条目补齐结构化字段，产出随版本部署的幂等数据，让企业侧「从库选择预填」拿到
更完整的台账数据。

### 已确认决策

| 决策点 | 结论 |
|---|---|
| 准确度口径 | 甲：只采权威/公开数据库可溯源的值，查不到留空；不使用 AI 生成 |
| 字段范围 | 甲：只做结构化字段 + GHS 危害类别文本；急救/泄漏/储运/防护本期不做 |
| 数值口径 | 乙：只采「实验值」或无标注的实测值；纯「计算值」留空；不新增数据来源列 |
| 交付方式 | 方案 1：离线批处理 → 幂等迁移 SQL → 随版本部署自动落库 |

## 2. 数据源

### 2.1 ChemBlink（中文，主源：理化性质 + GHS 危害分类）

- 产品页：`https://www.chemblink.com/zh/products/{CAS}C.htm`
- 可取值：密度、沸点、闪点、熔点、折射率；安全数据中的 GHS 危险品标志、
  危害标签（H 码）、防护标签（P 码）、危害分类表（中文类别名 + 类别号 + H 码）；
  部分条目页面正文含 `UN xxxx`。
- 数值标注：页面会区分「实验值」「计算值」（计算值来自 ACD/Labs 软件）。
- 其 `/zh/MSDS/{CAS}MSDSC.htm` 页面只是第三方 SDS 的 PDF 链接清单（Alfa-Aesar、
  TCI 等，英文、时效旧），不含正文，本期不使用。
- robots.txt 允许抓取（仅 Disallow `/cgi-bin/`、`/XMLFiles/`）。

### 2.2 PubChem（美国 NIH，补充源：UN 号 / 物理状态 / 爆炸极限 / 引燃温度）

- 名称解析：`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{CAS}/cids/JSON`
- 属性：`https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{CID}/JSON`
- 可取值：`Names and Identifiers > UN Number`；`Physical Description`；
  `Flash Point`、`Boiling Point`、`Density`、`Autoignition Temperature`；
  `Flammable Limits`、`Lower Explosive Limit (LEL)`、`Upper Explosive Limit (UEL)`；
  `GHS Classification`（英文，仅作 ChemBlink 缺失时的兜底）。

### 2.3 实测可行性（2026-09-10 抽样，30 条随机带 CAS 条目）

| 指标 | ChemBlink | PubChem |
|---|---|---|
| 页面/CID 可得 | 30/30 | 28/30 |
| 密度 | 70% | 需再统计 |
| 沸点 | 70% | 需再统计 |
| 闪点 | 60%（其中约 1/6 只有计算值） | 33% |
| GHS 危害分类 | 83%（中文） | 87%（英文） |
| UN 号 | 部分（小样本 4/10） | 63% |
| 物理状态 | 无 | 83% |
| 爆炸极限 | 无 | 27%（LEL/UEL） |
| 引燃温度 | 无 | 20% |

严格口径（不用纯计算值）下的预计覆盖率：闪点约 50%、沸点约 67%、密度约 67%。

## 3. 字段映射

| 库字段 | 来源 | 规则 |
|---|---|---|
| `un_no` | PubChem → ChemBlink | 两源不一致则留空并进待核清单 |
| `physical_state` | PubChem Physical Description | 英文关键词映射为「气态/液态/固态」，无法判定留空 |
| `flash_point` | ChemBlink → PubChem | 取实验值/无标注实测值；仅计算值留空 |
| `boiling_point` | ChemBlink → PubChem | 同上 |
| `density` | ChemBlink → PubChem | 同上，保留原始单位文本 |
| `explosion_limit` | PubChem LEL/UEL | 合成「下限~上限」格式 |
| `ignition_temp` | PubChem Autoignition Temperature | 无则留空 |
| `health_hazard` | ChemBlink GHS 危害分类 | 归类：急性毒性、皮肤腐蚀/刺激、严重眼损伤/刺激、呼吸道/皮肤致敏、致突变、致癌、生殖毒性、特定目标器官毒性、吸入危害 |
| `fire_hazard` | ChemBlink GHS 危害分类 | 归类：爆炸物、易燃气体/气溶胶/液体/固体、自反应物质、有机过氧化物、自燃、自热、遇水放出易燃气体、氧化性物质、加压气体 |
| `leak_response` / `storage_transport` / `first_aid` / `protective_measures` | — | 本期不填（范围外） |
| `name` / `alias` / `cas_no` / `remark` | — | 不改动 |

危害类别文本形如「急性毒性 类别4；眼刺激 类别2」。ChemBlink 缺失而 PubChem 有
英文 GHS 时，仅在能用 GB 30000 系列标准中文术语映射时填入，否则留空。

## 4. 冲突与缺失规则

1. **同源多值**：优先「实验值」，其次无标注实测值；只有「计算值」→ 留空。
2. **跨源冲突（UN 号）**：两源不一致 → 留空 + 待核清单。
3. **跨源冲突（数值）**：优先标注实验值的一方；两方均为实验值且相对差 >10% →
   留空 + 待核清单；单位不同先换算，无法换算时保留 ChemBlink 原值。
4. **只填空字段**：任何已有非空值（含管理员手工填写）都不覆盖。
5. **无 CAS 条目**：166 条跳过（留空），在报告中列出。
6. **同 CAS 多规格条目**：共享同一组数值（如 高氯酸三档浓度、苯酚/苯酚溶液），
   在报告中单独列出以便人工复核。

## 5. 数据流

1. 导出：从数据库取 2831 条有 CAS 的 `(id, name, cas_no)`。
2. 抓取：PubChem（CAS→CID→属性）+ ChemBlink（产品页）；原始响应落本地缓存，
   限速 0.3 秒/请求，失败重试 3 次（指数退避），支持断点续跑。
3. 解析：抽取字段、判定实验值/计算值、保留单位、抽取 GHS 类别。
4. 合并：套第 4 节规则，生成富集数据 + 抓取报告（覆盖率、来源分布、待核清单、
   失败清单、多规格清单）。
5. 生成：产出幂等迁移 SQL。
6. 验证：在开发环境应用并统计覆盖率，随后抽样复核。

## 6. 落库与幂等

- 迁移文件：`backend/db_migration_20260910_chemical_library_enrich.sql`
  （沿用既有机制：`docker cp` 至容器 + 后端重启自动应用；公司升级时自动生效）。
- 语句形式：按 `id` 更新，逐字段使用 `COALESCE(NULLIF(字段,''), '新值')`，
  保证只填空、重复执行结果不变、失败不会写坏既有数据。
- 数据文件：`backend/data/chemical_library_enrichment_20260910.json`（合并结果快照）。
- 报告：`docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md`。
- 体积预估：SQL 1–2 MB，JSON 约 1 MB。
- 回滚：这些字段原本为空，将指定字段置空即可恢复；SQL 幂等无副作用。

## 7. 影响面与 UI

- 前端不改代码：管理页已有 UN 号/物理状态/闪点列，编辑抽屉已含全部 15 个字段，
  管理员可直接修正；企业侧「从库选择预填」链路自动受益。
- 不新增数据库列，不改 API，不改企业台账表结构。

## 8. 错误处理

| 场景 | 处理 |
|---|---|
| 站点超时 / 5xx / 404 | 重试 3 次（指数退避），仍失败记入失败清单，相关字段留空 |
| 页面无该字段 | 留空，不推断、不猜测 |
| 解析异常（结构变化） | 该条记入失败清单，保留原始响应供排查 |
| 双源冲突 | 按第 4 节规则处理，冲突项进待核清单 |
| 限速 / 封禁迹象 | 自动降速并重试，必要时中断并保留断点 |

## 9. 测试与验收

- 解析器单测：离线样页夹具（ChemBlink 产品页、PubChem 属性 JSON），覆盖
  实验值/计算值判定、单位保留、GHS 类别分流、UN 冲突留空、物理状态映射。
- 迁移幂等测试：同一 SQL 连续执行两次，行数与已有值均不变。
- 覆盖率验收：与第 2.3 节区间对比（UN 50–65%、物理状态 75–85%、闪点 45–60%、
  沸点/密度 60–70%、爆炸极限 20–30%、引燃温度 15–25%、GHS 75–85%）。
- 抽样复核：随机 30 条，报告中附源页面链接供人工核对。
- 回归：后端定向测试 + 前端 `tsc`/`vitest` + 部署健康检查（8082 / backend health）。

## 10. 范围外

- 急救措施、泄漏应急处置、储存与运输、防护措施等成段文本（需官方 SDS 源）。
- 无 CAS 的 166 条属性补全。
- 与《危险化学品分类信息表》等官方表的对齐替换（找到可下载源后可再做一轮）。
- 定时自动更新（本期为一次性快照）。
- 任何 AI 生成数据。

## 11. 预计改动文件

| 文件 | 说明 |
|---|---|
| `backend/tools/enrich_chemical_library.py` | 抓取 + 解析 + 合并 + 生成 SQL（CLI，支持 `--limit` / `--refresh` / `--out`） |
| `backend/tests/test_chemical_library_enrichment.py` | 解析器单测 + 迁移幂等测试 |
| `backend/tests/fixtures/chemical_enrichment/*` | 离线样页夹具 |
| `backend/db_migration_20260910_chemical_library_enrich.sql` | 幂等填充 SQL |
| `backend/data/chemical_library_enrichment_20260910.json` | 富集数据快照 |
| `docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md` | 覆盖率与待核清单报告 |

`TASKS.md` 永不提交。

## 12. 风险与限制

- ChemBlink 为商业聚合库并声明「不承诺完备与准确」，因此只采实验值/实测值、
  冲突留空，并做 30 条抽样复核。
- 站点结构或限流变化会导致部分条目失败；缓存与断点续跑可降低重跑成本。
- 数据为 2026-09-10 快照，后续更新需重跑批处理。
- 多规格条目共享同 CAS 数值，可能与该规格实际物料存在偏差，报告会单列。
