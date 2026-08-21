# 事故类型全链路对齐 GB 6441-2025 — 设计规格

> **日期**：2026-08-21 | **状态**：设计中 | **依赖**：GB 6441-2025（已实施）、风险分级管控模块（已上线）、风险告知卡（已上线）、预案生成（已上线）

---

## 1. 概述

将系统中**所有**使用「事故类型」/「风险类别」的地方统一对齐到强制性国标 **GB 6441-2025《生产安全事故分类与编码》（2026-07-01 实施，27 类）**：前后端各收敛为一个共享常量模块，消除 7+ 处散落清单；存量数据（风险事件、预案、风险源类别、告知卡快照）按新旧映射表迁移；AI 提示词、Excel 模板、法规库同步更新；顺带修复风险源模板/AI 生成端点的 `PRESET_RISK_CATEGORIES` 未导入 NameError。

核心原则：**单一事实源、旧值映射、自由值保留**。

---

## 2. 背景与问题

当前事故类型清单散落 7 处且互相不一致：

| # | 位置 | 数量 | 问题 |
|---|------|------|------|
| 1 | `frontend/src/utils/riskMethodEngine.ts:32`（RiskEventForm 下拉） | 15 | 缺冒顶片帮/透水/放炮/火药爆炸/瓦斯爆炸 |
| 2 | `frontend/src/utils/constants.ts:1`（RiskSourceForm 下拉） | 12 | 命名非标准（爆炸/中毒窒息） |
| 3 | `frontend/src/pages/Plan/PlanCreatePage.tsx:116`（预案创建下拉） | 10 | 内联硬编码 |
| 4 | `frontend/src/mobile/screens/PlanCreateScreen.tsx` | 自由文本 | 无法保证口径 |
| 5 | `backend/app/services/risk_notice_card_data.py:18` | 20 | 旧标完整但需升级 + 补标志/措施组 |
| 6 | `backend/app/services/risk_assessment_service.py:60/61` | 15 | 缺 5 类 + 「淹溾」错字 |
| 7 | `backend/seed_prompts_full.py:367` / `risk_ai_service.py` | 引用旧标 | GB 6441-1986 已废止 |

另有 3 处隐藏问题：
- `backend/app/routers/risk_sources_ext.py` 4 次使用 `PRESET_RISK_CATEGORIES` 但**从未导入**（实测模块无此名）→ 模板下载/AI 生成/导入预览端点运行时报 NameError（现存 bug）
- AI 建议链路（风险源迁移 `suggested_accident_type`、风险事件建议）无口径约束，旧值可能持续流入
- 真实库存在非标准自由值（事件名）与泛化值（爆炸/中毒窒息/火灾爆炸），迁移需分层处理

---

## 3. 需求决策（用户已逐项确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 标准口径 | 统一按 **GB 6441-2025 新国标 27 类**（不保留旧 20 类双轨） |
| 2 | 存量数据 | 做**新旧映射表**并迁移（风险事件/预案/风险源类别/告知卡快照） |
| 3 | 结构收敛 | 前后端各收敛为一个**共享常量模块**（不做 API 动态下发，YAGNI） |
| 4 | 风险类别 | RiskSourceForm「风险类别」与事故类型**同一套 27 类** |
| 5 | 自由值策略 | 旧国标值 + 旧预设类别按映射迁移；**自由事件名/复合表述保留原样** |

---

## 4. 标准依据：GB 6441-2025 基本事故类型（27 类）

已从官方标准文本核对（序号 1-27，末类「其他」，第 17 类「可燃液体蒸气爆炸」）：

| 序号 | 名称 | 序号 | 名称 |
|------|------|------|------|
| 1 | 物体打击 | 15 | 管道爆炸 |
| 2 | 厂（场）内车辆致害 | 16 | 可燃气体爆炸 |
| 3 | 道路（轨道）车辆致害 | 17 | 可燃液体蒸气爆炸 |
| 4 | 机械致害 | 18 | 粉尘爆炸 |
| 5 | 起重致害 | 19 | 民用爆炸物品爆炸 |
| 6 | 触电 | 20 | 烟花爆竹爆炸 |
| 7 | 淹溺 | 21 | 其他可燃固体爆炸 |
| 8 | 灼烫 | 22 | 高温熔融物爆炸 |
| 9 | 火灾 | 23 | 中毒 |
| 10 | 高处坠落 | 24 | 窒息 |
| 11 | 跌落 | 25 | 滑坡 |
| 12 | 坍塌 | 26 | 泄漏 |
| 13 | 水害 | 27 | 其他 |
| 14 | 容器爆炸 | | |

与旧版关键差异：新增 12 类（跌落/水害/管道爆炸/可燃气体爆炸/可燃液体蒸气爆炸/粉尘爆炸/民用爆炸物品爆炸/烟花爆竹爆炸/其他可燃固体爆炸/高温熔融物爆炸/滑坡/泄漏）；删除 7 类（冒顶片帮/透水/放炮/火药爆炸/瓦斯爆炸/锅炉爆炸/其他爆炸）；拆分 2 类（车辆伤害、中毒和窒息）；更名 3 类（机械伤害→机械致害、起重伤害→起重致害、其他伤害→其他）。

---

## 5. 新旧映射表（20 类旧标 + 旧预设类别 → 27 类）

### 5.1 旧国标 20 类 → 新国标

| 旧值（GB/T 6441-1986） | 新值（GB 6441-2025） | 映射性质 |
|----------------------|----------------------|----------|
| 物体打击 | 物体打击 | 保留 |
| 车辆伤害 | 厂（场）内车辆致害 | 拆分默认（企业风控场景默认厂内） |
| 机械伤害 | 机械致害 | 更名 |
| 起重伤害 | 起重致害 | 更名 |
| 触电 | 触电 | 保留 |
| 淹溺 | 淹溺 | 保留 |
| 灼烫 | 灼烫 | 保留 |
| 火灾 | 火灾 | 保留 |
| 高处坠落 | 高处坠落 | 保留 |
| 坍塌 | 坍塌 | 保留 |
| 冒顶片帮 | 坍塌 | 删除并入 |
| 透水 | 水害 | 删除替代 |
| 放炮 | 民用爆炸物品爆炸 | 删除替代 |
| 火药爆炸 | 民用爆炸物品爆炸 | 删除替代 |
| 瓦斯爆炸 | 可燃气体爆炸 | 删除替代（瓦斯=甲烷） |
| 锅炉爆炸 | 容器爆炸 | 删除替代（锅炉属承压容器） |
| 容器爆炸 | 容器爆炸 | 保留 |
| 其他爆炸 | 其他 | 删除兜底 |
| 中毒和窒息 | 中毒 | 拆分默认（有限空间事故以中毒为主因） |
| 其他伤害 | 其他 | 更名 |

### 5.2 旧系统预设类别 → 新国标

| 旧值（PRESET 12 类） | 新值 | 说明 |
|---------------------|------|------|
| 爆炸 | 其他 | 泛化值，无法细分到具体爆炸类，归兜底 |
| 中毒窒息 | 中毒 | 与「中毒和窒息」同默认 |

### 5.3 保留原样（不迁移）

自由事件名与复合表述（非旧国标条目，硬映射会丢语义）：`火灾爆炸`、`设备损坏/数据丢失`、`制冷故障导致设备过热`、`人员滑倒/摔伤`、`踩踏/人员伤害`、`食物中毒`、`档案霉变/损毁` 等。展示、统计、告知卡兜底逻辑照常工作（告知卡 `EXTRA_SIGN_GROUPS` 保留 `火灾爆炸→火灾` 标志别名）。

---

## 6. 共享模块设计

### 6.1 后端 `backend/app/services/accident_types.py`（新增）

```python
ACCIDENT_TYPES_2025: list[str]          # 27 类，按国标表 1 顺序
LEGACY_TO_NEW_MAP: dict[str, str]       # 旧 20 类 + 旧预设（5.1/5.2）

def normalize_accident_type(value: str) -> str:
    """旧值→新值；27 类原样；未知值原样返回（自由值保留）。"""

def split_accident_values(value: str) -> list[str]:
    """按 、 / , 分隔多值（预案/风险源类别为逗号或顿号连接）。"""
```

### 6.2 前端 `frontend/src/utils/accidentTypes.ts`（新增）

```ts
export const ACCIDENT_TYPES_2025 = [...] as const;              // 27 类
export const LEGACY_TO_NEW_ACCIDENT_TYPE_MAP: Record<string, string>;
export function normalizeAccidentType(value: string): string;   // 同后端语义
```

配套单测：清单完整性（恰 27 类且与国标逐一对应）、映射正确性、normalize 三态（新值/旧值/未知值）。

---

## 7. 消费点改造清单

### 7.1 前端

| 文件 | 改动 |
|------|------|
| `utils/riskMethodEngine.ts:32` | 删除本地 `ACCIDENT_TYPES`，改为从 `accidentTypes` 导入 |
| `utils/constants.ts:1` | 删除 `PRESET_RISK_CATEGORIES`，RiskSourceForm 改从 `accidentTypes` 导入共享 27 类 |
| `pages/Plan/PlanCreatePage.tsx:116` | 内联 10 类 → 共享 27 类 |
| `mobile/screens/PlanCreateScreen.tsx` | 自由文本输入 → 27 类 chips 多选；风险源推荐值保留并优先展示 |
| `components/enterprise/RiskEventForm.tsx:414` | 占位文案「选择 GB6441 事故类型」→「选择 GB 6441-2025 事故类型」 |

### 7.2 后端

| 文件 | 改动 |
|------|------|
| `services/accident_types.py` | 新增共享模块 |
| `services/risk_notice_card_data.py` | `GB6441_ACCIDENT_TYPES` 从共享模块派生；`SIGN_GROUPS`/`EMERGENCY_TEMPLATES` 按 27 类重建（旧 20 组经保留/更名/承接合并后沿用 16 组，新增 11 组（道路（轨道）车辆致害、跌落、管道爆炸、可燃液体蒸气爆炸、粉尘爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、窒息、滑坡、泄漏），删除 7 组旧键；`EXTRA_SIGN_GROUPS` 保留火灾爆炸别名） |
| `services/risk_assessment_service.py:60/61` | prompt 改为 27 类全文，修复「淹溾」错字；`:28/:77` 标准引用更新 |
| `seed_prompts_full.py:367/:432/:440` | 系统提示词与辨识维度 prompt 更新为 27 类；**重新 seed 同步数据库** |
| `services/risk_ai_service.py:166/:202/:221` | 「GB 6441-1986」→「GB 6441-2025」+ 27 类约束 |
| `routers/risk_sources_ext.py:183/:309/:521/:683` | `PRESET_RISK_CATEGORIES` → 共享 27 类（**修复 NameError**） |
| `services/risk_source_migration_service.py:82` | 建议事故类型入库前 `normalize_accident_type`；AI 提示词按 27 类约束 |
| 法规库 `regulations/data/texts/` | 新增 `gb6441_2025.md` 标准全文；`gb6441_1986.md` 标注「已被 GB 6441-2025 代替」 |
| `routers/chat.py:38` | `create_plan` 工具参数 `accident_type` 描述补充「按 GB 6441-2025 27 类」（可选） |

### 7.3 纯透传消费点（无需改代码，迁移后自动一致）

`eventPayload.ts`、`riskHierarchyEvents.ts`、`smartGuideImport.ts`、`RiskOverviewStats.tsx`（Top5 分组）、`RiskOverviewMatrix.tsx`、`risk_notice_card_*.py`（标志/措施/文档导出）、`risk_control_list_service.py`、`external.py`、`generation.py`、`plans.py`、`plan_quality_service.py`。

---

## 8. 存量数据迁移

新增幂等迁移 SQL `backend/db_migration_accident_types_2025.sql`，覆盖 4 处：

| 表 | 字段 | 处理 |
|----|------|------|
| `risk_events` | `accident_type`（单值） | UPDATE CASE 映射，未知值不动 |
| `plan_projects` | `accident_type`（可含 、/, 多值） | `regexp_split_to_table` 拆项映射后 `string_agg` 回拼（保留原分隔符语义：顿号） |
| `risk_sources` | `categories`（逗号分隔多值） | 同上，按逗号拆分映射回拼 |
| `risk_notice_cards` | `content->'accident_types'`（JSONB 数组） | JSONB 逐元素映射（不触碰 `signs` 快照） |

设计要点：
- 幂等：重复执行结果一致（映射函数化，旧值映射后不再命中）
- 迁移前后各跑一次校验查询，确认旧标准值零残留、未知值数量与迁移前一致
- 迁移文件保留在 `backend/` 随发布包分发（与既有 `db_migration_*.sql` 惯例一致）

---

## 9. 测试策略（TDD）

### 9.1 新增

| 层 | 测试 | 断言 |
|----|------|------|
| 前端 | `utils/accidentTypes.test.ts` | 27 类完整且顺序与国标一致；映射 22 项（20 旧标 + 2 预设）全覆盖；normalize 三态 |
| 后端 | `tests/test_accident_types.py` | 清单/映射/normalize/split 行为；告知卡 27 类均有标志组与应急模板 |

### 9.2 更新（旧类型断言失效）

- `backend/tests/test_risk_notice_card_data.py`（灼烫/中毒和窒息/锅炉爆炸）
- `backend/tests/test_risk_notice_card_service.py`（灼烫/其他伤害/中毒和窒息/锅炉爆炸/车辆伤害）
- 其他引用旧类型的测试在实施中 `rg` 全量排查

### 9.3 迁移验证

- SQL 在副本库/测试库执行：前后对比查询、幂等重跑、自由值零改动

---

## 10. 风险与注意事项

1. **语义默认值**：「中毒和窒息→中毒」「车辆伤害→厂（场）内车辆致害」「爆炸→其他」为默认映射，迁移后可在表单人工改回（个别需人工复核的值在迁移报告列出）
2. **seed 生效**：`seed_prompts_full.py` 改后必须重新执行 seed 脚本同步数据库模板，否则线上提示词仍是旧口径
3. **告知卡快照**：迁移只改 `accident_types` 字段，不动已保存的 `signs`（AI/人工优化结果），避免覆盖用户人工成果
4. **自由值**：不强制迁移，但新录入经下拉约束后不会再产生新的非标准值；AI 建议链路 normalize 兜底
5. **法规库索引**：新增 `gb6441_2025.md` 需按法规库既有机制入索引（bm25/chroma），旧文标注废止

---

## 11. 验证方式（完成标准）

- [ ] 后端全量 pytest 通过；前端 tsc / vitest 通过
- [ ] `rg` 全库零残留旧标准类型清单（冒顶片帮/透水/放炮/火药爆炸/瓦斯爆炸/锅炉爆炸/其他爆炸/中毒和窒息/其他伤害/机械伤害/起重伤害/车辆伤害 等仅出现在映射表与迁移 SQL 中）
- [ ] 迁移 SQL 幂等重跑通过，旧值零残留，自由值未动
- [ ] Docker 重启冒烟：模板下载 200、告知卡新类型标志正常、预案创建下拉含 27 类
- [ ] codegraph sync + graphify update
