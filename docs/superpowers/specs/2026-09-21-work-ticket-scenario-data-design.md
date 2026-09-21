# 作业票措施条件数据化 设计

> 解决：用户反馈「不管选什么类型，作业情景不会跟着变」
> 路线：路线一（映射搬到数据文件 + 文本锚定 + 生成器产出），并补全 8 个票种
> 状态：待用户审查

## 1. 背景与目标

### 1.1 现状（已实测）

| 票种 | 措施条数 | 有判定 | 无法判定 |
|---|---|---|---|
| 动火 DHZY | 16 | 3 | 13 |
| 受限空间 YXKJ | 15 | 0 | 15 |
| 盲板 MBCD / 临电 LSYD / 动土 PTZY / 断路 DLZY | 11 / 14 / 11 / 4 | 0 | 全部 |
| 高处 GCZY ×4 级 / 吊装 QZDZ ×3 级 | 15 / 20 | 0 | 全部 |

两个缺陷：
1. **前端** `WorkTicketNewPage.tsx` 的 `SCENARIO_FIELDS` 是硬编码的 7 项动火语境复选框，不随票种变化
2. **后端** `work_ticket_measure_rules.MEASURE_CONDITIONS` 只映射了动火 16 条，其余 7 个票种一条都没有
   → 非动火票上勾选情景完全无效（已用探针证实：传 `{"in_tank_area": false}` 后分布一字未变）

### 1.2 目标

1. **8 个票种都有条件映射**，情景区按票种展示，勾选立即影响措施建议
2. **映射数据化**：改标准文本或改映射后，**重跑一次生成器即同步**，不需改代码、不发版
3. **映射按措施文本锚定**（不是按序号）：标准修订导致序号漂移时不会错判

### 1.3 非目标（明确不做）

- 不做"系统自动发现标准变了并提示"的法规变更检测（用户已确认只要前者）
- 不做条件映射的 AI 自动生成（语义判断无文本依据，必须人工标注）
- 不做管理界面在线编辑映射（映射与标准文本同源，走"改文件 + 重跑"）
- 不改 `validate_before_submit` 的法定门禁语义

## 2. 数据文件：唯一事实源

新建 `backend/app/regulations/data/work_ticket_conditions.yaml`，与标准文本并列存放：

> ⚠️ 下面示例里的措施正文用 `…` 截断只为节省篇幅；**真实 YAML 必须写措施的完整正文**，
> 否则文本锚定会失配（生成器会报错中止，不会静默放过）。

```yaml
# 措施条件映射：改这里 → 重跑 backend/seed_work_ticket_conditions.py → 同步入库
# 锚定键 = 票种 + 措施正文（规范化后精确匹配），不用序号——标准修订插入条文时不会错位
version: 1

conditions:
  # 通用条件（多票种复用）
  has_other_tickets:
    label: 本次作业还办理了其他特殊作业票
    auto: tickets_in_batch        # 由作业包/关联票自动推断
  night_work:
    label: 作业时段涉及夜间（20:00~06:00）
    auto: period_at_night
  explosion_hazard_area:
    label: 作业点在火灾爆炸危险场所
    auto: null                    # 自动推断不出来 → 由用户勾选
  # …（完整清单见 §5）

tickets:
  DHZY:
    level_field: fire_level
    scenario:                     # 该票种要向用户展示的情景区（人工勾选的条件）
      - internal_work
      - connected_pipeline
      - surroundings_ignition
      - in_tank_area
      - height_work
      - has_flammable_lining
      - surrounding_hazardous_ops
    measures:
      - text: 动火设备内部构件清洗干净，蒸汽吹扫或水洗、置换合格，达到动火条件
        conditions: [internal_work]
      - text: 与动火设备相连接的所有管线已断开，加盲板（ ）块，未采取水封或仅关闭阀门的方式代替盲板
        conditions: [connected_pipeline]
      # …（16 条）
  YXKJ:
    scenario: [hazardous_residue, connected_pipeline, rotating_equipment, flammable_atmosphere, dust_inside, corrosive_medium]
    measures:
      - text: 盛装过有毒、可燃物料的受限空间，所有与受限空间有联系的阀门、管线已加盲板隔离…
        conditions: [hazardous_residue, connected_pipeline]
      # …（15 条）
```

**为什么锚定键用正文而不是序号**：标准修订若在某条后插入一条，序号整体后移，按序号锚定会把"不涉及"判到错误的措施上——那是静默错判，比不判定更危险。正文锚定在顺序变化时仍然正确。

## 3. 生成器：文本锚定与失配规则

新建 `backend/seed_work_ticket_conditions.py`（与既有 `seed_work_ticket_templates.py` 同风格，纯函数 `build_sql()` 可单测）：

1. 读标准文本 → `parse_measures()` 得到每个票种的措施清单（复用既有解析器）
2. 读 YAML → 校验每个票种声明的条件键都已定义、每条措施都有 `text` 与 `conditions`
3. **按正文匹配**：YAML 的每条 `text` 必须能在该票种的措施里找到（规范化后精确匹配）
4. 产出 SQL：`work_ticket_measure_conditions` 表 + `work_ticket_scenarios` 表

两条硬规则（安全底线）：

- **失配即报错并中止生成**：YAML 里有映射但标准文本里找不到对应措施 → `RuntimeError` 列出失配条目。
  这样标准文本改动后重跑会立刻暴露，而不是悄悄少一条映射。
- **未映射即 unknown**：标准文本里有措施但 YAML 未映射 → 生成"未映射清单"写入报表/日志，
  该措施在运行时落 `unknown`（人工逐条处理），**绝不猜**。

生成器同时产出 `backend/work_ticket_conditions_report.json`（未映射清单 + 覆盖统计），便于每次重跑后核对。

## 4. 数据库与接口

```sql
CREATE TABLE IF NOT EXISTS work_ticket_measure_conditions (
    id            UUID PRIMARY KEY,
    ticket_type   VARCHAR(20) NOT NULL,
    measure_ref   VARCHAR(64) NOT NULL,   -- 措施正文的规范化 hash（稳定锚点）
    sort_order    INTEGER NOT NULL,       -- 仅用于展示排序，不参与匹配
    condition_key VARCHAR(60) NOT NULL,
    UNIQUE (ticket_type, measure_ref, condition_key)
);

CREATE TABLE IF NOT EXISTS work_ticket_scenarios (
    id            UUID PRIMARY KEY,
    ticket_type   VARCHAR(20) NOT NULL,
    condition_key VARCHAR(60) NOT NULL,
    label         VARCHAR(200) NOT NULL,
    auto_rule     VARCHAR(60) NULL,       -- 非空表示可自动推断，前端不必展示为勾选项
    sort_order    INTEGER NOT NULL,
    UNIQUE (ticket_type, condition_key)
);
```

运行时加载：`work_ticket_measure_rules` 改为从这两张表构建 `MEASURE_CONDITIONS` 与条件标签
（进程内缓存，参考 `llm_client._load_capability` 的 30 秒 TTL 缓存写法），**代码里不再硬编码任何映射**。

**规范化规则（锚定与查找共用同一个函数）**：去除全部空白字符、全角标点转半角、去掉末尾标点。
只做这三项——不做模糊匹配、不做同义词替换，因为模糊匹配会把"改了字的另一条措施"错认成同一条，
那正是要避免的静默错判。

接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| — | `/work-ticket/templates` | 每个模板增加 `scenario_fields: [{key, label}]`（只含人工勾选项），前端随票种切换直接用它渲染，不额外发请求 |
| GET | `/work-ticket/scenarios?ticket_type=YXKJ` | 兜底单查接口（供作业包等场景单独取） |
| — | `/work-ticket/prefill` | 响应中的 `measures_suggestions` 改用新映射（无需改契约） |

## 5. 八个票种的条件与情景项（本规格核心）

每条映射的依据都是"该措施条文自身提到的现场条件"，下面是逐票种清单。

### 5.1 通用条件（跨票种）

| 条件键 | 名称 | 推断方式 |
|---|---|---|
| `has_other_tickets` | 本次作业还办理了其他特殊作业票 | 自动：作业包内票数 > 1 或已填关联票号 |
| `night_work` | 作业时段涉及夜间（20:00~06:00） | 自动：由 `work_period` 推断 |
| `explosion_hazard_area` | 作业点在火灾爆炸危险场所 | 人工勾选（可由作业对象所属区域名辅助预置） |

### 5.2 动火 DHZY（16 条，沿用现有并数据化）

情景项 7 个：`internal_work`、`connected_pipeline`、`surroundings_ignition`、`in_tank_area`、`height_work`、`has_flammable_lining`、`surrounding_hazardous_ops`
自动项：`gas_welding`（动火方式含气焊/气割）、`electric_welding`（含电焊）、`has_other_tickets`

### 5.3 受限空间 YXKJ（15 条）

情景项：`hazardous_residue`（盛装过有毒/可燃物料）、`connected_pipeline`、`rotating_equipment`（内部有转动设备）、`flammable_atmosphere`（内部易燃易爆）、`dust_inside`（内部存在大量扬尘）、`corrosive_medium`（内部有腐蚀性介质）

### 5.4 盲板抽堵 MBCD（11 条）

情景项：`toxic_medium`、`explosion_hazard_area`、`corrosive_medium`、`high_temp_medium`、`low_temp_medium`、`multi_point_same_pipe`（同一管道多处抽堵）

### 5.5 高处 GCZY（15 条）

情景项：`toxic_gas_area`、`scaffold_used`、`layered_work`、`ladder_used`、`light_shed`（有轻型棚）、`load_bearing_plate`、`night_or_poor_light`、`outdoor`
自动项：`above_30m`（由 `work_height ≥ 30` 推断）、`has_other_tickets`

### 5.6 吊装 QZDZ（20 条）

情景项：`hazardous_equipment_nearby`、`building_as_anchor`、`near_power_line`、`pipe_as_anchor`、`underground_facilities`、`overhead_facilities`、`explosion_hazard_area`、`outdoor`
自动项：`level_1_or_2`（由吊装级别推断）、`has_other_tickets`

### 5.7 临时用电 LSYD（14 条）

情景项：`explosion_hazard_area`、`line_elevated`（线路架高敷设）、`cross_road`（跨越道路）、`line_along_surface`、`underground_cable`、`outdoor`

### 5.8 动土 PTZY（11 条）

情景项（人工勾选）：`underground_cable`、`underground_pipeline`、`on_road`、`hazardous_area`（易燃易爆/有毒气体场所）
自动项：`deep_excavation`（由 `dig_depth > 1.2` 推断）、`night_work`（由作业时段推断）、`has_other_tickets`

### 5.9 断路 DLZY（4 条）

**无人工勾选的情景项**：该票种 4 条措施里 3 条为固定措施，唯一的条件依赖是"夜间作业设置警示灯"，
而 `night_work` 由作业时段自动推断 → 第 0 步对该票种显示"本票种无需额外情景，系统按作业时段自动判定夜间照明要求"。

### 5.10 完整映射清单（逐条依据，供审阅）

「固定」= 该条措施与现场条件无关（任何时候都要确认），不建立条件映射，运行时落 `unknown` 由人工处理。
每行括号里是措施条文开头，便于对照标准原文。

| 票种 | # | 措施（条文开头） | 条件 |
|---|---|---|---|
| DHZY | 1 | 动火设备内部构件清洗干净… | `internal_work` |
| DHZY | 2 | 与动火设备相连接的所有管线已断开… | `connected_pipeline` |
| DHZY | 3 | 动火点周围及附近的孔洞、窨井、地沟… | `surroundings_ignition` |
| DHZY | 4 | 油气罐区动火点同一防火堤内… | `in_tank_area` |
| DHZY | 5 | 高处作业已采取防火花飞溅措施… | `height_work` |
| DHZY | 6 | 在有可燃物构件和使用可燃物做防腐内衬的设备内部动火作业… | `has_flammable_lining` |
| DHZY | 7 | 乙炔气瓶直立放置… | `gas_welding` |
| DHZY | 8 | 现场配备灭火器（ ）台… | 固定 |
| DHZY | 9 | 电焊机所处位置已考虑防火防爆要求… | `electric_welding` |
| DHZY | 10 | 动火点周围规定距离内没有易燃易爆化学品的装卸、排放、喷漆… | `surrounding_hazardous_ops` |
| DHZY | 11 | 动火点30m内垂直空间未排放可燃气体… | `surrounding_hazardous_ops` |
| DHZY | 12 | 已开展作业危害分析…交叉作业已明确协调人 | `has_other_tickets` |
| DHZY | 13 | 用于连续检测的移动式可燃气体检测仪已配备到位 | `gas_welding`∨`electric_welding` |
| DHZY | 14 | 配备的摄录设备已到位… | 固定 |
| DHZY | 15 | 其他相关特殊作业已办理相应安全作业票… | `has_other_tickets` |
| DHZY | 16 | 其他安全措施：编制人： | 占位行 |
| YXKJ | 1 | 盛装过有毒、可燃物料的受限空间…阀门、管线已加盲板隔离 | `hazardous_residue`∨`connected_pipeline` |
| YXKJ | 2 | 盛装过有毒、可燃物料的受限空间，设备已经过置换、吹扫或蒸煮 | `hazardous_residue` |
| YXKJ | 3 | 设备通风孔已打开进行自然通风… | 固定 |
| YXKJ | 4 | 转动设备已切断电源…加锁并悬挂"禁止合闸" | `rotating_equipment` |
| YXKJ | 5 | 受限空间内部已具备进人作业条件…易燃易爆物料容器内作业 | `flammable_atmosphere` |
| YXKJ | 6 | 受限空间进出口通道畅通… | 固定 |
| YXKJ | 7 | 盛装过可燃有毒液体、气体的受限空间，已分析…气体和氧气含量 | `hazardous_residue` |
| YXKJ | 8 | 存在大量扬尘的设备已停止扬尘 | `dust_inside` |
| YXKJ | 9 | 用于连续检测的移动式可燃、有毒气体、氧气检测仪已配备到位 | 固定 |
| YXKJ | 10 | 作业人员已佩戴必要的个体防护装备… | 固定 |
| YXKJ | 11 | 已配备作业应急设施…盛有腐蚀性介质的容器作业现场已配备应急用冲洗水 | `corrosive_medium` |
| YXKJ | 12 | 受限空间内作业已配备通信设备 | 固定 |
| YXKJ | 13 | 受限空间出入口四周已设立警戒区 | 固定 |
| YXKJ | 14 | 其他相关特殊作业已办理相应安全作业票 | `has_other_tickets` |
| YXKJ | 15 | 其他安全措施：编制人： | 占位行 |
| MBCD | 1 | 在管道、设备上作业时，降低系统压力… | 固定 |
| MBCD | 2 | 在有毒介质的管道、设备上作业时…个体防护装备 | `toxic_medium` |
| MBCD | 3 | 火灾爆炸危险场所，作业人员穿防静电工作服…防爆工具 | `explosion_hazard_area` |
| MBCD | 4 | 火灾爆炸危险场所的气体管道，距作业地点30m内无其他动火作业 | `explosion_hazard_area` |
| MBCD | 5 | 在强腐蚀性介质的管道、设备上作业时…防止酸碱化学灼伤 | `corrosive_medium` |
| MBCD | 6 | 介质温度较高、可能造成烫伤的情况下…防烫措施 | `high_temp_medium` |
| MBCD | 7 | 介质温度较低、可能造成人员冻伤情况下…防冻伤措施 | `low_temp_medium` |
| MBCD | 8 | 同一管道上未同时进行两处及两处以上的盲板抽堵作业 | `multi_point_same_pipe` |
| MBCD | 9 | 其他相关特殊作业已办理相应安全作业票 | `has_other_tickets` |
| MBCD | 10 | 作业现场四周已设警戒区 | 固定 |
| MBCD | 11 | 其他安全措施：编制人： | 占位行 |
| GCZY | 1 | 作业人员身体条件符合要求 | 固定 |
| GCZY | 2 | 作业人员着装符合作业要求 | 固定 |
| GCZY | 3 | 作业人员佩戴…有可能散发有毒气体的场所携带正压式空气呼吸器 | `toxic_gas_area` |
| GCZY | 4 | 作业人员携带有工具袋及安全绳 | 固定 |
| GCZY | 5 | 现场搭设的脚手架、防护网、围栏符合安全规定 | `scaffold_used` |
| GCZY | 6 | 垂直分层作业中间有隔离设施 | `layered_work` |
| GCZY | 7 | 梯子、绳子符合安全规定 | `ladder_used` |
| GCZY | 8 | 轻型棚的承重梁、柱能承重作业过程最大负荷的要求 | `light_shed` |
| GCZY | 9 | 作业人员在不承重物处作业所搭设的承重板稳定牢固 | `load_bearing_plate` |
| GCZY | 10 | 采光、夜间作业照明符合作业要求 | `night_or_poor_light` |
| GCZY | 11 | 30m以上高处作业时…配备通信、联络工具 | `above_30m`（自动：`work_height ≥ 30`） |
| GCZY | 12 | 作业现场四周已设警戒区 | 固定 |
| GCZY | 13 | 露天作业，风力满足作业安全要求 | `outdoor` |
| GCZY | 14 | 其他相关特殊作业已办理相应安全作业票 | `has_other_tickets` |
| GCZY | 15 | 其他安全措施：编制人： | 占位行 |
| QZDZ | 1 | 一、二级吊装作业已编制吊装作业方案… | `level_1_or_2`（自动：由级别推断） |
| QZDZ | 2 | 吊装场所如有含危险物料的设备、管道时… | `hazardous_equipment_nearby` |
| QZDZ | 3 | 作业人员已按规定佩戴个体防护装备 | 固定 |
| QZDZ | 4 | 已对起重吊装设备、钢丝绳…进行检查 | 固定 |
| QZDZ | 5 | 已明确各自分工、坚守岗位，并统一规定联络信号 | 固定 |
| QZDZ | 6 | 将建筑物、构筑物作为锚点…审查核算并批准 | `building_as_anchor` |
| QZDZ | 7 | 吊装绳索、揽风绳…不应与带电线路接触 | `near_power_line` |
| QZDZ | 8 | 不应利用管道、管架、电杆、机电设备等作吊装锚点 | `pipe_as_anchor` |
| QZDZ | 9 | 吊物捆扎坚固…棱角吊物已采取衬垫措施 | 固定 |
| QZDZ | 10 | 起重机安全装置灵活好用 | 固定 |
| QZDZ | 11 | 吊装作业人员持有有效的法定资格证书 | 固定 |
| QZDZ | 12 | 地下通信电（光）缆…承重吊装机械的负重量已确认 | `underground_facilities` |
| QZDZ | 13 | 起吊物的质量(t)经确认，在吊装机械的承重范围内 | 固定 |
| QZDZ | 14 | 在吊装高度的管线、电缆桥架已做好防护措施 | `overhead_facilities` |
| QZDZ | 15 | 作业现场围栏、警戒线、警告牌、夜间警示灯已按要求设置 | 固定（夜间警示灯见 LSYD/PTZY/DLZY 的 `night_work`） |
| QZDZ | 16 | 作业高度和转臂范围内无架空线路 | `near_power_line` |
| QZDZ | 17 | 在爆炸危险场所内的作业，机动车排气管已装阻火器 | `explosion_hazard_area` |
| QZDZ | 18 | 露天作业，环境风力满足作业安全要求 | `outdoor` |
| QZDZ | 19 | 其他相关特殊作业已办理相应安全作业票 | `has_other_tickets` |
| QZDZ | 20 | 其他安全措施：编制人： | 占位行 |
| LSYD | 1 | 作业人员持有电工作业操作证 | 固定 |
| LSYD | 2 | 在防爆场所使用的临时电源、元器件和线路达到相应的防爆等级要求 | `explosion_hazard_area` |
| LSYD | 3 | 上级开关已断电、加锁，并挂安全警示标牌 | 固定 |
| LSYD | 4 | 临时用电的单相和混用线路要求按照TN-S三相五线制方式接线 | 固定 |
| LSYD | 5 | 临时用电线路如架高敷设…不低于2.5m,跨越道路高度不低于5m | `line_elevated` |
| LSYD | 6 | 临时用电线路如沿墙面或地面敷设…穿越道路…防机械损伤 | `line_along_surface`∨`cross_road` |
| LSYD | 7 | 临时用电线路架空进线不应采用裸线 | `line_elevated` |
| LSYD | 8 | 暗管埋设及地下电缆线路敷设时…电缆埋深要求大于0.7m | `underground_cable` |
| LSYD | 9 | 现场临时用配电盘、箱配备有防雨措施，并可靠接地 | `outdoor` |
| LSYD | 10 | 临时用电设施已装配漏电保护器…（一机一闸一保护） | 固定 |
| LSYD | 11 | 用电设备、线路容量、负荷符合要求 | 固定 |
| LSYD | 12 | 其他相关特殊作业已办理相应安全作业票 | `has_other_tickets` |
| LSYD | 13 | 作业场所已进行气体检测且符合作业安全要求 | `explosion_hazard_area` |
| LSYD | 14 | 其他安全措施：编制人： | 占位行 |
| PTZY | 1 | 地下电力电缆、通信电（光）缆…已确认，保护措施已落实 | `underground_cable` |
| PTZY | 2 | 地下供排水、消防管线、工艺管线已确认… | `underground_pipeline` |
| PTZY | 3 | 已按作业方案图划线和立桩 | 固定 |
| PTZY | 4 | 作业现场围栏、警戒线、警告牌、夜间警示灯已按要求设置 | 固定 |
| PTZY | 5 | 已进行放坡处理和固壁支撑 | `deep_excavation`（自动：`dig_depth > 1.2` 时建议涉及） |
| PTZY | 6 | 道路施工作业已报：交通、消防、安全监督部门、应急中心 | `on_road` |
| PTZY | 7 | 现场夜间有充足照明… | `night_work`（自动） |
| PTZY | 8 | 作业人员配备有必要的个人防护装备 | 固定 |
| PTZY | 9 | 易燃易爆、有毒气体存在的场所动土深度超过1.2m… | `deep_excavation`∨`hazardous_area` |
| PTZY | 10 | 其他相关特殊作业已办理相应安全作业票 | `has_other_tickets` |
| PTZY | 11 | 其他安全措施：编制人： | 占位行 |
| DLZY | 1 | 作业前，制定交通组织方案… | 固定 |
| DLZY | 2 | 作业前，在断路的路口和相关道路上设置交通警示标志… | 固定 |
| DLZY | 3 | 夜间作业设置警示灯 | `night_work`（自动） |
| DLZY | 4 | 其他安全措施：编制人： | 占位行 |

统计：8 票种共 106 条措施，其中 **66 条建立条件映射**（其中 6 条依赖自动推断的条件：
GCZY-11 `above_30m`、QZDZ-1 `level_1_or_2`、PTZY-5/9 `deep_excavation`、PTZY-7 与 DLZY-3 `night_work`），
**40 条为固定措施或占位行**（运行时不判定，落 `unknown` 由人工逐条确认）。

## 6. 前端改造

1. 第 0 步「作业情景」改为**按票种渲染**：从 `/templates` 响应（或 `/scenarios`）取该票种的 `scenario` 列表；无人工勾选项的票种（如断路只有夜间，可由时段自动推断）显示"本票种无需额外情景"
2. 勾选仍遵循既有的三态语义：勾选=true；未勾选且未声明核实时保持 `None`（不推断为"不涉及"）
3. 自动推断的条件在界面上以只读方式回显（如"系统识别：作业时段涉及夜间"），让用户知道判定依据
4. 票种切换时清空上一票种的情景勾选（避免把动火的情景带到受限空间票）

## 7. 测试与验收

**后端单测**
1. 生成器：YAML 覆盖 8 个票种、每票种映射条数 = 措施条数 - 固定措施数；失配时抛错（构造一条错文本验证）
2. 未映射措施落 `unknown`（构造一条新增措施验证）
3. 锚定稳定性：把某票种的措施顺序打乱后重新生成，映射仍指向同一正文（回归锁）
4. 运行时加载：从表构建的 `MEASURE_CONDITIONS` 与 YAML 一致
5. 每票种至少有一条 `not_applicable` 可被触发（逐票种构造情景验证）

**前端**
1. 切票种时情景区随票种变化（单测）
2. 8 票种各自渲染出正确的情景项数量

**端到端探针**
1. 对 8 个票种逐个传"明确不涉及"的情景，断言 `not_applicable` 数量 > 0（当前只有动火满足）
2. 浏览器实测：切换票种时情景区文本变化、勾选后措施列表出现"建议不涉及"

## 8. 工作量与风险

粗估 **3~5 天**：YAML + 生成器 + 失配规则 1 天；两张表 + 迁移 + 运行时加载 0.5 天；8 票种逐条标注与核对 1.5~2 天；前端按票种渲染 0.5 天；测试与探针 0.5~1 天。

| 风险 | 缓解 |
|---|---|
| 文本锚定过严（标准文本用字微调导致失配） | 失配即报错，重跑时立刻可见；规范化只做空白与全半角处理，不做模糊匹配（模糊匹配会误判） |
| 条件划分过粗导致"不涉及"被误判 | 保守原则：一个条件的真值不确定时保持 `None`；只有用户明确勾选或明确声明核实时才产生 False |
| 标准文本被我方修改后忘记重跑 | 生成器产出报告文件；验收清单里要求"改文本必重跑并核对报告" |
| 8 票种标注的业务判断可能有争议 | 每条映射在 YAML 里带 `basis`（依据的措施正文片段），便于逐条复核 |
