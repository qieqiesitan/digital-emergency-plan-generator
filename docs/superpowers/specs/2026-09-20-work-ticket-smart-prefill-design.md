# 作业票智能预填设计（规格 1 / 共 2 份）

> 范围：A 层（确定性预填与继承）+ B 层（AI 预填）
> 依赖：无（本规格是规格 2「情景化批量开票」的前置）
> 状态：待用户审查

## 0. 前置修复：模板措施数据缺陷（P0，必须先做）

### 0.1 缺陷

真库实测（2026-09-20）：

| 模板 | 当前措施条数 | 正确条数（GB 30871 附录A 对应表） |
|---|---|---|
| DHZY 特级 / 一级 / 二级 | **106** | 16（表 A.1） |
| YXKJ 受限空间 | **106** | 15（表 A.2） |
| QZDZ 一/二/三级 | 20 | 20 ✓ |
| GCZY Ⅰ~Ⅳ级 | 15 | 15 ✓ |
| LSYD / MBCD / PTZY / DLZY | 14 / 11 / 11 / 4 | ✓ |

106 条 = 附录 A 表 A.1~A.8 **全部措施的总和**（16+15+11+15+20+14+11+4 = 106）。即动火票的措施清单里混进了盲板、高处、吊装、临电、动土、断路的措施。

### 0.2 根因

1. 首批种子（`db_migration_20260917_work_ticket_seed.sql`，含 4 个模板）由**早期解析逻辑**生成：当时未按附录表号切换目标表，把全部附录 A 措施都写给了每个模板（该文件内 4 个模板各有 106 条）。
2. 修正版生成器（`db_migration_20260917_work_ticket_seed_v2.sql`，每模板正确条数）使用**确定性 UUID5 主键** + `ON CONFLICT (id) DO NOTHING`：排序 1~16 的行 ID 与 v1 相同被跳过，而 v1 多出的第 17~106 行**没有任何机制删除**，于是原样留在库中。

结论：生成器已修好，**存量数据没修**——这是当前线上开票体验的直接原因。

### 0.3 影响面（真库）

- 动火 3 个级别 + 受限空间的模板措施为 106 条 → 开票第 4 步要在一个 106 项的列表里操作
- 28 张票中已有 2 张按 106 条确认过（1 张 approved、1 张 approving）；其余动火/受限空间票确认了 16 条
- 已打印快照是固化的历史事实，**不修改**

### 0.4 修复方案

新增迁移 `backend/db_migration_20260920_work_ticket_measure_fix.sql`：

```sql
-- 删除错误扩充的措施行（保留 sort_order 在正确区间内的行，其文本与修正版种子一致）
DELETE FROM work_ticket_template_measures m
USING work_ticket_templates t
WHERE m.template_id = t.id
  AND ((t.code = 'DHZY' AND m.sort_order > 16)
    OR (t.code = 'YXKJ' AND m.sort_order > 15));
```

执行前后必须核验：

1. 修复前：`SELECT t.code, t.level, count(*) ...` → 记录基线（DHZY×3 / YXKJ = 106）
2. 修复后：DHZY×3 = 16、YXKJ = 15、其余 11 个模板条数不变（11/14/15/20/4）
3. **文本一致性**：DHZY 保留的 1~16 行与 v2 种子中的 16 条逐条比对（条数与文本全等），确认留下的是正确的动火措施而非前 16 条恰好是动火措施以外的内容
4. 老票兼容：`values.confirmed_measures` 中大于新条数的编号**不做清理**（`validate_before_submit` 只校验缺失、忽略多余编号，天然兼容）；但需确认 2 张按 106 条确认的已提交票在票详情页展示正常

### 0.5 与法规文本的一致性佐证

`backend/app/regulations/data/texts/reg_gb_30871_2022.md` 第 819~834 行（表 A.1）含 16 条动火措施、第 868~888 行（表 A.2）含 15 条受限空间措施；v2 生成器输出的条数与之一致。这是"16 / 15 为正确条数"的直接依据。

### 0.6 为什么必须先做

本规格后续的两项工作（措施三态、措施继承）都建立在"措施库条数正确"之上。若先做三态判定，106 条里 90 条属于其他票种，判定规则会为它们输出大量"不涉及"，把缺陷伪装成业务规则，之后更难发现。

## 1. 背景与目标

### 1.1 背景（实测证据）

开票过程机械的根因不是字段多，而是**系统里已有的答案一个都没用上**。实测（2026-09-20，真库 + 源码）：

| 事实 | 证据 |
|---|---|
| 二级动火票票面 12 字段、必填 11，全部手打或手选，无默认值/下拉/联动 | `WorkTicketNewPage.tsx` 第 1 步渲染逻辑 |
| 安全措施逐条勾选：**动火 3 个级别与受限空间各 106 条**（含其他票种措施，见 §0 缺陷），其余票种 4~20 条 | 真库 `work_ticket_template_measures` 实测 |
| 全库 584 条模板措施 `is_mandatory` 全为 TRUE，无"是否涉及"判定数据 | `SELECT is_mandatory, count(*) FROM work_ticket_template_measures` → 584 / t |
| 开票页只调 `getEnterprise` 取 `credit_code` 拼票号，其余字段一律空白 | `WorkTicketNewPage.tsx:118` |
| `allow_ai_prefill` 列存在且 3 个字段标 TRUE，但接口不返回、前端类型无、全仓无消费点 | `work_ticket.py` 模型 / `routers/work_ticket.py` list_templates |
| 动火/受限空间另需 ≥1 条气体检测（6 字段） | `validate_before_submit` |
| 一次开票交互动作约 35~40 次（动火/受限空间还要在一个 106 项的措施列表里操作） | 上述合计，基线口径见 §6 |

同时确认**可复用的数据底座已经建成**：

- 风险五层：`risk_zones` 1275 / `risk_objects` 15 / `risk_units` 19 / `risk_events` 35 / `enterprise_floors` 157
- 成员台账 `enterprise_members` 33 条（name / phone / position / org_node_id）
- 危化品台账 `hazardous_chemicals` 31 条（MSDS 16 字段 + CAS/UN）
- 历史作业票 28 张（8 类齐备）、模板层 8 类票字段与 223 条措施种子
- AI 基础设施：`llm_client`（多厂商 + 重试 + 超时分类）、`ai_json`（统一 JSON 解析）、`ai_capability_service`（能力开关）、`hazard_ai_service` 等成熟范例

### 1.2 目标

1. 单张票的开票交互动作从约 35 次降到 **12 次以内**（不含气体检测数据本身；计数口径见 §6）
2. 每一个自动带出的值都**可追溯来源**，并在票面提交前经过人工确认
3. 安全措施支持"不适用"标记，**不静默删除**、可撤销、带理由、进审计
4. AI 预填失败/未配置时，开票流程**完全不受影响**（降级为可手填）

### 1.3 非目标（本规格明确不做）

- 不做批量开票、作业包、跨票共享（→ 规格 2）
- 不修改 `validate_before_submit` 的法定必填规则，不新增任何跳过/强制通道
- 不建特种作业人员资质的审批流或到期预警（只做证照记录与选择器）
- 不做移动端（移动端作业票页面当前整体缺失，属独立议题）
- 不重构模板层数据结构（字段定义与措施库仍由 seed 生成器维护）
- 不做"一键全部确认措施"——它制造"没看就勾"，本规格用判定排序替代

## 2. 核心机制

### 2.1 三个数据锚点

**锚点 A：作业对象（最强，新引入）**

开票第 0 步除类型/级别外，增加"作业地点"选择器：**楼层 → 区域（RiskZone）→ 可选对象（RiskObject/RiskUnit）**。选中后系统即获得：

| 获得物 | 来源 | 用途 |
|---|---|---|
| 地点文本（`RiskObject.location` / `name`） | risk_objects | 票面地点字段（fire_location / space_location / dig_location / road_position / pipe_position） |
| 关联风险事件（accident_type / trigger_conditions / chemical_id） | risk_events | 风险辨识结果的首要依据 |
| 关联危化品（MSDS 16 字段） | risk_events.chemical_id → hazardous_chemicals | 风险辨识、气体检测气体种类推荐、措施"是否涉及"判定 |
| 平面图坐标（location_x/y）| risk_objects | 票面附平面图位置、四色图联动 |

**降级**：企业未维护风险数据（对象/区域为空）时，地点退化为"自由文本 + 上次同类票地点建议"，不阻断开票。

**锚点 B：历史票继承**

取同企业 + 同 `template_id` + 状态非 `draft` 的最近一张票作为继承源。无历史时该来源整条跳过。

**锚点 C：成员台账**

`enterprise_members`（enabled=TRUE）作为人员字段候选；按 `position` 关键词（负责人/监护/电工/起重）排序置顶，其余按姓名排序。

### 2.2 字段来源映射（本规格的规格表）

来源优先级从左到右，前一个不可用时自动落下一个；最后一档永远是"留空手填"。

| field_key | 标签 | 来源与优先级 | 票面表现 |
|---|---|---|---|
| `applicant_unit` | 作业申请单位 | ①企业档案（`enterprises.name`）②上次同类票 ③手填 | 带来源徽标，可改 |
| `work_unit` | 作业单位 | ①上次同类票 ②企业档案 ③手填 | 带来源徽标，可改 |
| `apply_time` | 作业申请时间 | ①系统默认当前时间 ②手选 | 带"默认"徽标 |
| `work_period` | 作业实施时间 | ①作业包时段（规格 2）②上次同类票的时长（起点=申请时间）③默认 8 小时 ④手选 | 可改 |
| `fire_level` / `high_level` / `lift_level` | 作业级别 | **第 0 步选择联动**（消除当前重复输入） | 只读回显 + "改级别"跳回第 0 步 |
| `work_leader` | 作业负责人 | ①成员台账（position 含"负责人"）②上次同类票 ③手填 | 成员下拉 |
| `guardian` | 监护人 | ①成员台账（position 含"监护"）②上次同类票 ③手填 | 成员下拉 |
| `fire_person` | 动火人及证书编号 | ①成员台账 + 该成员证照（2.6）②手填 | 成员下拉 + 证书号自动拼接，可改 |
| `electrician` | 电工及证书编号 | 同 `fire_person` | 同上 |
| `lift_commander` | 吊装指挥 | ①成员台账 ②上次同类票 ③手填 | 成员下拉 |
| `logout_person` | 作业结束后注销人 | ①上次同类票 ②手填 | 可改 |
| `fire_location` / `space_location` / `dig_location` / `road_position` / `pipe_position` | 地点类 | ①作业对象锚点 A ②上次同类票 ③手填 | 选择器 + 可编辑文本 |
| `work_content` | 作业内容 | ①作业包任务描述（规格 2）②上次同类票 ③AI 生成 ④手填 | AI 时带"AI 生成"徽标 |
| `risk_identification` | 风险辨识结果 | ①AI 生成（锚点 A + 危化品 + 票种）②上次同类票 ③手填 | AI 时**必须显式确认** |
| `related_tickets` | 关联的其他特殊作业票编号 | ①同作业包自动填写（规格 2）②上次同类票 ③手填 | 非包内票可改；**包内票只读**（规格 2 由系统回填） |
| 票种专有字段（`blind_plate_no` / `lift_weight` / `work_height` / `power_capacity` / `fire_method` / `operate_type` / `dig_depth` 等） | — | **不预填**（现场事实，无法推断） | 保持手填 |

**硬原则：不确定就留空。** 预填只给可确定的值；宁可空白让用户填，也不给一个看似合理但可能是错的默认值（例：`work_height` 绝不猜）。

### 2.3 来源留痕模型

新增列 `work_ticket_instances.values_meta JSONB NOT NULL DEFAULT '{}'`：

```jsonc
{
  "risk_identification": {
    "source": "ai",                    // manual|history|member|risk_object|template_link|system_default|ai
    "source_ref": {                    // 可追溯依据，人工可读
      "risk_object_id": "…",
      "risk_event_ids": ["…"],
      "chemical_ids": ["…"],
      "model": "deepseek-chat"
    },
    "prefilled_at": "2026-09-20T10:00:00+08:00",
    "confirmed_at": "2026-09-20T10:02:11+08:00",
    "confirmed_by": "user-uuid",
    "edited": true                     // 用户确认前是否改过
  },
  "work_leader": {
    "source": "member",
    "source_ref": { "member_id": "…", "matched_position": "作业负责人" },
    "prefilled_at": "…",
    "confirmed_at": "…",
    "confirmed_by": "…",
    "edited": false
  }
}
```

确认规则（写入 `validate_before_submit`，**只增不放松**）：

- `source = "ai"` 的必填字段：**必须逐个显式确认**（点"采用"或手动编辑），否则提交被阻断，错误文案：`「风险辨识结果」为 AI 生成内容，尚未经人工确认`
- 其他来源（`history` / `member` / `risk_object` / `batch` / `template_link` / `system_default`）：在第 5 步"填写来源摘要"集中展示，提供**一个**"确认全部预填项"动作批量写入 `confirmed_at`——避免把省下的输入变成逐字段点击；用户也可逐个修改，改动后 `edited=true`
- 后端只强校验"AI 来源必须有 `confirmed_at`"这一条，其他来源的确认状态由前端负责写入、后端不设阻断（避免把交互问题变成后端门禁）
- `source` 缺失（老数据、直接调用 API）默认按 `manual` 处理，**老票不受影响**

### 2.4 措施"是否涉及"判定

现状：584 条措施全部 `is_mandatory=TRUE`；**动火与受限空间因 §0 缺陷各为 106 条**，其余票种 4~20 条，票面逐条勾选。GB 30871 附录A 表 A.1~A.8 的"是否涉及"列在标准原文中是**空格**（留给现场逐条判定），因此**没有现成法条可查**，必须由系统给出判定建议，最终由人确认。

**数据模型**：新增列 `work_ticket_instances.measures_meta JSONB NOT NULL DEFAULT '{}'`：

```jsonc
{
  "3":  { "state": "not_applicable", "reason_code": "no_flammable_in_area", "reason_text": "作业点周边无孔洞/窨井/地沟", "acted_by": "…", "acted_at": "…" },
  "12": { "state": "confirmed", "source": "history", "acted_by": "…", "acted_at": "…" }
}
```

每条措施三态：`pending`（未处理）/ `confirmed`（已确认涉及并落实）/ `not_applicable`（本票不涉及）。

- `not_applicable` **必须**带 `reason_code` + `reason_text`，且可一键撤销回 `pending`
- `confirmed_measures`（现有 `values.confirmed_measures` 数组）**保持不变**，与 `measures_meta` 双写，老代码与打印逻辑零改动
- 提交门禁：所有措施必须非 `pending`（现在是"必须全确认"，语义从"全勾选"变为"全部表过态"）

**门禁语义变更的合规依据**：GB 30871-2022 附录 A 表 A.1~A.8 的措施表本身就是四列——`序号 | 安全措施 | 是否涉及 | 确认人`，标准原文的"是否涉及"列是**空格**（见 `backend/app/regulations/data/texts/reg_gb_30871_2022.md:819`），即标准预期由填票人对每条措施表态"涉及 / 不涉及"，而不是无条件全部打勾。当前实现把"是否涉及"压成了"全部确认"，反而偏离票面设计。因此把门禁从"全部确认"改为"全部表态"是**向标准原文对齐**，不是放松：措施条数不变、不适用必须逐条给理由（固定原因码 + 说明）、全程审计、可撤销。

**判定建议引擎（确定性规则优先，AI 兜底）**

新增 `backend/app/services/work_ticket_measure_rules.py`，纯函数、可单测：

1. 从措施文本抽取条件信号（正则 + 关键词表）：罐区/油品、乙炔气瓶、高处、管线/法兰、可燃气体检测仪、摄录设备、动土、断路、受限空间、带电、交叉作业……
2. 与作业情景比对：票种、级别、作业对象（是否在罐区、是否涉危化品）、关联危化品的 MSDS 属性（闪点、爆炸极限）、同包内是否已有其他作业票
3. 输出每条一个建议：`suggest_applicable` / `suggest_not_applicable` / `unknown`
4. **建议只影响排序与分组**：
   - `suggest_not_applicable` → 默认收进"建议不涉及（N 条）"折叠区，展开后一键标记
   - `unknown` → 留在主列表
   - 任何建议都不自动写入 `measures_meta`，必须人工点击

规则表以数据形式放在 `work_ticket_measure_rules.py` 顶部的常量表里（key → 关键词/条件 → 判定），附 GB 30871 条款锚点，便于逐条核对与后续扩充。

### 2.5 AI 预填

**接线既有钩子**：`GET /work-ticket/templates` 响应增加 `allow_ai_prefill`（模板层已有数据，无需迁移）。前端据此决定字段旁是否出现"AI 生成"按钮。

**新能力**：在 `ai_capability_service` 注册 `work_ticket_prefill`（与现有能力同构，管理员可停用）。

**端点**：`POST /work-ticket/ai/prefill`（有 token 成本，仅用户点击时调用，不在进页面时自动触发）

请求：

```jsonc
{
  "enterprise_id": "…",
  "ticket_type": "DHZY",
  "level": "二级",
  "risk_object_id": "…",          // 可空（锚点 A 未选时）
  "work_content": "更换 3# 罐底阀门",  // 可空
  "last_ticket_id": "…"           // 可空：上次同类票，作为风格参照
}
```

响应：

```jsonc
{
  "available": true,
  "risk_identification": {
    "text": "1. 罐内残留易燃液体，动火前须清洗置换合格；2. …",
    "basis": ["作业对象：3# 储罐", "涉及介质：乙醇（闪点 13℃）", "历史同类票 2 张"]
  },
  "jsa": { "text": "…", "hazards": [{ "hazard": "…", "control": "…" }] },
  "measures_suggestions": [
    { "sort_order": 3, "suggest": "not_applicable", "reason": "作业点 15m 内无窨井/地沟（据所选作业对象周边）" }
  ],
  "note": "AI 生成内容仅供参考，须由作业负责人确认"
}
```

**提示词硬约束**（写在服务层，与 `hazard_ai_service` 同风格）：

1. 只输出中文，只输出 JSON，不输出解释性前后缀
2. **不得编造**企业不存在的设备、介质、管线；不确定的事实写"待现场核实"
3. 风险辨识结果 3~6 条，每条对应一个具体危害 + 控制措施
4. 禁止输出"符合作业条件""可以作业"之类的结论性批准语句——AI 不做批准
5. 输入中没有的信息不得推断（例：没给作业高度就不提高度风险）

**降级**：未配置 AI / 能力停用 / 超时 / 返回非 JSON → `{"available": false, "note": "…"}`，前端顶部轻提示"AI 预填不可用，请手动填写"，表单保持可填。与 `hazard_ai_service` 的 `_fallback()` 惯例一致。

**人工确认交互**：AI 结果进字段时显示 `AI 生成 · 依据：…`（Tag + tooltip），提供三个动作：**采用** / **重新生成** / 直接编辑。只有点"采用"或手动编辑后才写 `confirmed_at`。

### 2.6 人员与证照（数据底座补齐）

现状缺口：`enterprise_members` 12 列中**没有任何证照字段**，而票面必填 `fire_person`（动火人及证书编号）、`electrician`（电工及证书编号）——不补这一块，这两个字段每次仍要手打。

方案（最小形态，不做审批流）：

1. 新增列 `enterprise_members.certificates JSONB NOT NULL DEFAULT '[]'`
   ```jsonc
   [{ "type": "焊接与热切割作业", "no": "T6101…", "valid_to": "2027-05-30" }]
   ```
2. 成员管理页（`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`）增加证照编辑区：类型（下拉，含"焊接与热切割作业/低压电工作业/高处安装维护拆除作业/起重机械指挥/危险化学品安全作业"）+ 证书编号 + 有效期
3. 票面人员字段渲染改为"成员下拉 + 证书号"，选中成员后自动拼接为 `姓名 证书号` 写入 `values`（**落库格式与现在完全一致**，打印、docx、历史兼容零改动）
4. 证照过期时选择器置灰并提示，但**不阻断**（票面事实以现场核对为准）

### 2.7 前端向导改造

保持 6 步骨架（用户已熟悉），改造内容：

| 步骤 | 现在 | 改造后 |
|---|---|---|
| 0 类型与级别 | 类型 + 级别 | 增加"作业地点"选择器（楼层→区域→对象）；级别联动写回票面 |
| 1 票面内容 | 全空表单 | 进入时自动调确定性预填接口；每字段带来源徽标；顶部"预填 N 项，留空 M 项"摘要 |
| 2 气体检测 | 全空新增行 | 取样时间默认当前、检测人默认当前用户、地点默认作业地点、气体种类按作业对象关联危化品推荐（可改） |
| 3 安全措施 | N 条平铺 + "全部确认" | 三态；"建议不涉及"折叠区；**移除无条件的"全部确认"**，改为"确认全部建议涉及的（N 条）"——只覆盖 `suggest_applicable` 的条目并逐条记录确认人与时间，`unknown` 必须逐条处理 |
| 4 JSA | 提示"本计划未接入" | 接入 AI 生成。注意 `jsa` **不是模板字段**（前端独立 state，提交时并入 `values`），因此不依赖 `allow_ai_prefill`，按钮固定显示；结果写 `values.jsa` 与 `values_meta.jsa`（`source=ai`，需确认） |
| 5 人员与提交 | 只显示计数 | 增加"填写来源摘要"：自动带出 N 项 / AI 生成 M 项 / 手工填写 K 项；AI 项未确认时在此处列红并阻断 |

**草稿可保存（本规格必需）**

现状：`openTicket` 一次性创建，**没有任何更新草稿的端点**——用户填一半离开就只能丢弃。这本身就是"机械"的一部分。本规格补：

`PATCH /work-ticket/tickets/{id}`，仅 `status=draft` 可改，body 为 `{values, values_meta, measures_meta}`，进向导时若上次有未提交草稿则提示"继续上次填写"。

## 3. 数据模型与迁移

本规格涉及两个迁移文件：

1. `backend/db_migration_20260920_work_ticket_measure_fix.sql`——§0 的措施数据修复（**先执行**）
2. `backend/db_migration_20260920_work_ticket_prefill.sql`——本规格新增列（幂等，`ADD COLUMN IF NOT EXISTS`）

```sql
ALTER TABLE work_ticket_instances ADD COLUMN IF NOT EXISTS values_meta  JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE work_ticket_instances ADD COLUMN IF NOT EXISTS measures_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE enterprise_members  ADD COLUMN IF NOT EXISTS certificates JSONB NOT NULL DEFAULT '[]'::jsonb;
```

同步改动：`backend/app/models/work_ticket.py`（WorkTicketInstance 两列）、`backend/app/models/enterprise_org.py`（EnterpriseMember 一列）。

部署注意：按部署手册 **§8.0.1**——后端容器根目录未挂载，新迁移脚本必须 `docker cp` 进容器后执行并做三重核验（列存在 / 默认值正确 / 老行填充）。

## 4. API 设计

统一信封 `{"success","code","message","data"}`，沿用 `_ok()`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/work-ticket/templates` | **改动**：字段增加 `allow_ai_prefill`、`validation` 透出 |
| GET | `/work-ticket/prefill` | 确定性预填：入参 `enterprise_id` / `template_id` / `ticket_type` / `level` / `risk_object_id?`；返回 `{values, values_meta, sources_detail, members, locations, measures_suggestions, last_ticket}` |
| POST | `/work-ticket/ai/prefill` | AI 预填（用户点击触发），见 2.5 |
| PATCH | `/work-ticket/tickets/{id}` | 草稿保存（values + values_meta + measures_meta） |
| GET | `/work-ticket/locations` | 作业地点候选：楼层→区域→对象树（含 `location` 文本），供选择器使用 |
| GET | `/work-ticket/last-ticket` | 上次同类票摘要（供"参考上次"按钮） |

权限：全部经 `ensure_enterprise_owned`（企业主）或 `ensure_enterprise_visible`（成员只读），与既有端点一致。AI 端点额外走能力开关。

## 5. 错误处理与降级

| 场景 | 行为 |
|---|---|
| 企业无风险数据 | 地点选择器显示"未维护风险区域，请手动填写地点"，其余预填照常 |
| 无历史同类票 | 历史来源整条跳过，不提示错误 |
| 成员台账为空 | 人员字段退化为普通文本输入 |
| 预填接口 5xx/超时 | 表单保持空白可用 + 顶部黄条"未能自动带出，可手动填写"；不阻断 |
| AI 未配置/停用/超时/非 JSON | `available:false`，不弹错误 toast，仅在字段旁显示"AI 暂不可用" |
| 证照过期 | 选择器置灰 + 提示，不阻断 |
| 老票（无 values_meta） | 全部按 `manual` 处理，提交门禁不新增阻断 |

## 6. 测试与验证

**后端单测**（`backend/tests/test_work_ticket_prefill.py`、`test_work_ticket_measure_rules.py`）

1. 来源优先级：有历史票 vs 无历史票 vs 两者都无 → 取值与 `source` 正确
2. `values_meta` 归一化：脏数据/缺字段不炸
3. 提交门禁：AI 来源未确认 → 阻断且文案正确；老数据（无 meta）不阻断
4. 措施三态：`not_applicable` 缺理由 → 拒绝；撤销回 `pending` 正常
5. 规则引擎：对 223 条真实措施种子逐条跑，断言不抛异常且 `suggest` 分布合理（回归快照）
6. AI 降级：`ai_config=None` / 抛异常 / 返回非 JSON → `available:false` 且不抛
7. PATCH 草稿：非 draft 状态 409；跨企业 404

**前端**

1. 向导单测：预填徽标渲染、AI 未确认阻断提示、措施折叠区交互
2. `npx tsc -b` / `vitest` / `eslint` 全绿（项目既有门禁）

**端到端验证**（沿用项目探针惯例，`output/playwright/e2e-20260920/scripts/`）

1. 探针：真账号开一张二级动火票，记录**交互动作计数**，与改造前基线对比（目标 ≤12 次）
   - 口径：从进入向导到点"提交审批"之间浏览器端的用户输入事件数（点击 / 选择 / 一次连续文本输入各记 1），由探针脚本埋点统计
   - 基线：用同一脚本在修复前的构建上先测一次并留档，避免口径漂移
2. 浏览器实测：8 个票种各开一张，断言无 console error、预填徽标出现、来源 tooltip 文案正确
3. 反向验证：清空企业风险数据后再开票，确认降级提示出现且仍可提交
4. 提交门禁验证：AI 生成但不确认 → 前端红字 + 后端 422 双向阻断

## 7. 工作量与风险

粗估 **5~8 人日**：后端（模型 + 迁移 + 预填服务 + 规则引擎 + AI 服务 + 3 个端点）约 3 人日；前端（向导改造 + 徽标 + 三态措施 + 成员证照）约 3 人日；测试与探针 1~2 人日。

| 风险 | 缓解 |
|---|---|
| AI 生成的风险辨识内容不合规或空洞 | 强制人工确认 + 展示依据 + 提示词禁止编造与批准性表述 |
| 预填值过期（上次票的人员已变动） | 徽标显示来源与时间；人员选择器以成员台账为准而非直接采用历史文本 |
| "不适用"被滥用，措施被成批跳过 | 必须逐条理由 + 审计留痕 + 撤销入口；不做批量标记不适用 |
| 风险数据稀疏（当前仅 15 个对象）导致锚点 A 价值受限 | 区域级（1275 个）即可用；对象为空时退到区域 + 自由文本 |
| 老数据兼容 | 新列全部有默认值；无 meta 一律按 manual，不新增阻断 |

## 8. 验收清单

- [ ] 三列迁移已应用，老票 28 张全部可正常读取与打印
- [ ] §0 措施缺陷已修复并三重核验：DHZY 三个级别 = 16 条、YXKJ = 15 条、其余 11 个模板条数不变（11/14/15/20/4）
- [ ] 修复后 DHZY 保留的 16 条与 v2 种子逐条文本一致（确认留下的是动火措施本身）
- [ ] 开票页进入即有预填，每个预填字段可见来源徽标与依据
- [ ] 级别在第 0 步选定后，票面级别字段不再需要二次输入
- [ ] 人员字段可从成员台账选择，`values` 落库格式与现在一致（打印无差异）
- [ ] 成员证照可维护，动火人证书号自动拼接
- [ ] 措施三态可用，"建议不涉及"折叠区可展开并一键标记（需理由）
- [ ] 措施提交门禁从"全确认"变为"全部表过态"，且老票不受影响
- [ ] AI 预填可用时能生成风险辨识与 JSA；停用/超时/未配置时静默降级，开票不受阻
- [ ] AI 生成字段未确认时前后端双向阻断，文案明确
- [ ] PATCH 草稿保存可用，中断后可继续填写
- [ ] 无风险数据的企业开票流程完整可用（降级路径实测）
- [ ] 后端 `pytest` 全绿 + `ruff` 全绿；前端 `tsc -b` / `vitest` / `eslint` 全绿
- [ ] 探针与浏览器实测通过，交互动作计数达 ≤12 次目标
- [ ] 交互动作计数、降级路径、门禁双向验证均有证据留档

## 9. 与规格 2 的接口约定

本规格为规格 2 提供以下能力（规格 2 直接复用，不重复实现）：

1. 确定性预填服务（`prefill`）与来源留痕模型（`values_meta`）
2. 措施判定规则引擎（`measures_meta` 三态）
3. 人员与证照选择器
4. 作业地点锚点（楼层→区域→对象）
5. AI 预填通道（`work_ticket_prefill` 能力）
6. 模板措施数据缺陷修复（§0）——修复后的正确条数是措施三态与继承的前提
