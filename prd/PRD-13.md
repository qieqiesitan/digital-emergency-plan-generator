# PRD-13：法规知识图谱与智能合规引擎

> 版本：v1.0 | 日期：2026-07-07 | 状态：待评审

---

## 1. 产品概述

### 1.1 问题陈述

当前系统在生成风险评估报告、应急资源调查报告、综合应急预案、专项应急预案、现场处置方案时，所有编制依据完全依赖大模型内置知识。大模型训练数据存在截止日期，导致引用已废止法规、遗漏新发布法规、条文引用不准确等问题，报告合规性无法保证。

### 1.2 解决方案

GraphRAG（知识图谱 + 向量检索 + Prompt 注入）：构建安全生产法规知识库，AI 基于实时检索到的法规原文撰写编制依据。

### 1.3 三大核心原则

| 原则 | 说明 |
|---|---|
| 傻瓜化维护 | 粘贴全文 → AI 自动解析 → 点确认入库 |
| 松耦合 | 独立 Python package，与业务代码仅一行调用 |
| 静默降级 | 法规模块异常 → 自动回退原有逻辑 |

---

## 2. 系统架构

### 2.1 整体架构

`
前端 (React + TypeScript)
├── 法规库管理页面 (列表/搜索/粘贴解析/废止)
└── 关系图谱可视化 (Mermaid)

后端 (FastAPI) - 3个新增/修改点
├── routers/regulations.py          [新增] 法规管理路由
├── routers/generation.py           [修改] +1行注入调用
└── app/regulations/               [新增] 独立模块
    ├── graph.py                   图谱管理器 (NetworkX)
    ├── vector_store.py            ChromaDB 向量存储
    ├── retriever.py               混合检索编排
    ├── injector.py                Prompt 注入器
    ├── sync.py                    AI解析+入库+索引
    └── data/
        ├── graph.json             法规知识图谱
        ├── index.yaml             报告类型→法规映射
        └── texts/*.md             法规条文全文 (30+)
`

### 2.2 数据流（生成预案时）

`
用户点击「生成综合应急预案」
  → generation.py: _build_section_prompt()
  → 对「编制依据」章节: inject_regulations()
    → graph.query() → 8条必引法规
    → [可选] vector_store.search() → 语义补充
    → 格式化为法规参考块 → 拼接到 prompt
  → _stream_llm_chunks(prompt_with_regulations)
  → AI 基于注入的条文原文撰写编制依据
`
---

## 3. 后端模块详细设计

### 3.1 目录结构

`
backend/app/regulations/          # 新增独立模块
├── __init__.py                   # 模块入口，延迟初始化 + 全局单例
├── graph.py                      # 法规图谱管理器
├── vector_store.py               # ChromaDB 向量存储
├── retriever.py                  # 混合检索编排
├── injector.py                   # Prompt 注入器
├── sync.py                       # AI解析 + 入库 + 重建索引
└── data/                         # 数据持久化
    ├── graph.json                # 知识图谱 (NetworkX格式)
    ├── index.yaml                # 报告类型→法规映射
    ├── texts/                    # 法规条文全文 Markdown
    │   ├── 安全生产法_2021.md
    │   ├── GBT29639_2020.md
    │   └── ... (30+条)
    └── chroma_db/                # ChromaDB 持久化(自动生成)
`

### 3.2 graph.py —— 法规知识图谱管理器

**技术选型**：NetworkX（纯Python，零外部服务依赖，与graphify同款引擎）。

**图谱Schema**：

节点属性：id, label, full_name, node_type(law|standard|policy|topic), code, version, effective_date, issuing_body, status(effective|abolished|revised), abolished_by

边属性：source, target, relation(替代|上位法|引用|适用)

**核心API**：

`
RegulationGraph
├── load() → 从 graph.json 加载到内存 (NetworkX DiGraph)
├── query_by_plan_type(plan_type) → 按预案类型查询适用法规
├── query_by_topic(topic) → 按主题标签查询法规
├── trace_chain(node_id, relation) → 追溯关系链(如上位法链)
├── get_abolished() → 获取已废止法规清单
├── add_node(node) / add_edge(src, tgt, rel) → 新增
├── abolish(node_id, replaced_by) → 标记废止 + 添加替代边
└── save() → 持久化到 graph.json
`

#### graph.json 示例

`json
{
  "nodes": [
    {
      "id": "law_safety_production_2021",
      "label": "安全生产法",
      "full_name": "中华人民共和国安全生产法",
      "node_type": "law",
      "code": "主席令第88号",
      "version": "2021修正",
      "effective_date": "2021-09-01",
      "issuing_body": "全国人大常委会",
      "status": "effective"
    },
    {
      "id": "std_gbt29639_2020",
      "label": "GB/T 29639-2020",
      "full_name": "生产经营单位生产安全事故应急预案编制导则",
      "node_type": "standard",
      "code": "GB/T 29639-2020",
      "version": "2020版",
      "effective_date": "2020-09-29",
      "issuing_body": "国家市场监督管理总局",
      "status": "effective"
    },
    {
      "id": "std_aqt9002_2006",
      "label": "AQ/T 9002-2006",
      "full_name": "生产经营单位生产安全事故应急预案编制导则",
      "node_type": "standard",
      "code": "AQ/T 9002-2006",
      "version": "2006版",
      "effective_date": "2006-10-01",
      "issuing_body": "国家安全生产监督管理总局",
      "status": "abolished",
      "abolished_by": "std_gbt29639_2020"
    },
    {
      "id": "topic_emergency_plan",
      "label": "应急预案编制",
      "node_type": "topic"
    }
  ],
  "edges": [
    {"source": "std_gbt29639_2020", "target": "std_aqt9002_2006", "relation": "替代"},
    {"source": "std_gbt29639_2020", "target": "law_safety_production_2021", "relation": "下位法"},
    {"source": "std_gbt29639_2020", "target": "topic_emergency_plan", "relation": "适用"}
  ]
}
`

### 3.3 index.yaml —— 报告类型→法规映射

`yaml
comprehensive:  # 综合应急预案
  core:
    - law_safety_production_2021
    - law_emergency_response_2007
    - policy_plan_management_2019
    - policy_emergency_regulation_2019
    - std_gbt29639_2020
  optional:
    - law_fire_protection_2021

special:  # 专项应急预案
  core:
    - law_safety_production_2021
    - law_emergency_response_2007
    - policy_plan_management_2019
    - std_gbt29639_2020
    - std_aqt9007_2019
  optional:
    - gb30871_2022

onsite:  # 现场处置方案
  core:
    - law_safety_production_2021
    - policy_plan_management_2019
    - std_gbt29639_2020

risk_assessment:  # 风险评估报告
  core:
    - law_safety_production_2021
    - std_gbt13861_2022
    - gb18218_2018
    - gb6441_1986
    - std_aqt8001_2007
  optional:
    - gb50140_2005

resource_investigation:  # 应急资源调查报告
  core:
    - law_safety_production_2021
    - policy_plan_management_2019
    - policy_emergency_regulation_2019
    - gb30077_2023
`

### 3.4 vector_store.py —— ChromaDB 向量存储

**技术选型**：ChromaDB（pip install chromadb，嵌入式运行，无需独立服务）。

**Embedding策略**：复用用户配置的AI API（OpenAI/DeepSeek/Qwen的embedding接口），一次性批量向量化后缓存到本地文件，日常检索不再调用API。

**分块策略**：按「条」分块。安全生产法规天然以「条」为最小语义单元。

每条条文向量包含：id(法规id + 条号), text(条文原文), metadata(regulation_id, regulation_label, article, topics)

**核心API**：
`
RegulationVectorStore
├── ensure_collection() → 确保 ChromaDB collection 存在
├── add_regulation(regulation_id, articles) → 添加一条法规的全部条文向量
├── search(query, top_k, filter_ids) → 语义检索
├── delete_regulation(regulation_id) → 删除某法规所有向量
├── rebuild_all(embedding_fn) → 全量重建索引
└── collection_count() → 当前向量总数
`

### 3.5 retriever.py —— 混合检索编排

该类实现两级检索逻辑：
**第1级 —— 图谱精确匹配**：
`
graph.query_by_plan_type(plan_type)
  → 从 index.yaml 获取该类型 core + optional 法规列表
  → 过滤 status=abolished 的法规
  → 对废止法规添加替代标注
  → 从 texts/*.md 读取对应法规的条文原文
`

**第2级 —— 向量语义补充**（法规量>=50时启用）：
`
vector_store.search(enterprise_data中的风险描述, top_k=5)
  → 排除第1级已返回的条文
  → 补充相关度最高的条文
`

**返回格式**：
`json
{
  "effective": [
    {"regulation_id": "...", "label": "...", "articles": [{"number": "...", "text": "..."}]}
  ],
  "abolished": [{"label": "...", "replaced_by": "..."}]
}
`

**Token预算控制**：max_articles=30，超出时按优先级截断（core法规优先于optional）。

### 3.6 injector.py —— Prompt 注入器

**注入触发条件**：section_key 包含特定模式（sec_1_2, sec_1, 编制依据, 1.2, 1.1）时触发注入。非目标章节原样返回，零开销。

**核心函数**：inject_regulations(plan_type, section_key, section_title, prompt, enterprise_data) → str

逻辑流程：
1. 判断章节类型，非编制依据章节直接返回原prompt
2. 调用 retriever.retrieve() 获取法规数据
3. 任何异常 → 静默降级，返回原prompt
4. 将检索结果格式化后拼接到prompt末尾

**注入内容示例**：
`
【系统确认的现行有效法律法规参考——请严格依据以下条文撰写】

以下为当前系统确认有效的法律法规条文原文，请据此撰写编制依据，
在正文中准确引用法规名称和具体条款号。

### 安全生产法 (2021修正)
版本：2021修正 | 施行日期：2021-09-01 | 状态：现行有效

**第二条** 在中华人民共和国领域内从事生产经营活动的单位的安全生产，适用本法...
**第二十一条** 生产经营单位的主要负责人对本单位安全生产工作负有下列职责：（一）建立健全并落实本单位全员安全生产责任制...
**第八十一条** 生产经营单位应当制定本单位生产安全事故应急救援预案...

### GB/T 29639-2020 应急预案编制导则
版本：2020版 | 施行日期：2020-09-29 | 状态：现行有效

**4.1** 应急预案编制程序包括成立应急预案编制工作组、资料收集、风险评估...
**4.5** 综合应急预案主要内容应当规定应急组织机构及职责...

---
### 以下法规已废止，请勿引用：
- AQ/T 9002-2006，已被 GB/T 29639-2020 替代
`

### 3.7 sync.py —— 法规数据同步引擎

负责法规数据的自动化处理，提供以下能力：

**AI解析**：用户粘贴法规全文 → 后端调AI API → 返回结构化JSON（编号、名称、日期、替代关系、上位法、主题标签、条文清单）。前端展示预览 → 用户确认 → 入库。

**入库流程**：
`
RegulationSyncer.ingest(parsed_data)
  1. 写入 texts/{code}_{version}.md (条文全文)
  2. 更新 graph.json (节点 + 替代边 + 上位法边 + 主题边)
  3. 调用 vector_store.add_regulation() (向量化所有条文)
  4. 返回 regulation_id
`

**废止流程**：
`
RegulationSyncer.abolish(regulation_id, replaced_by)
  1. graph.json 中 status → "abolished"
  2. graph.json 中添加 abolished_by 字段
  3. graph.json 中添加替代边
`

**一键重建索引**：遍历 texts/*.md → 分块 → embedding API → 写入 ChromaDB。

**图谱校验**：检查孤岛节点、断链、引用不存在的法规id。

---

## 4. 后端 API 设计

### 4.1 路由注册

新增 ackend/app/routers/regulations.py，prefix="/regulations"

在 main.py 中新增两行：
`python
from app.routers import regulations
app.include_router(regulations.router, prefix="/api/v1")
`

### 4.2 接口清单（10个）

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | /api/v1/regulations | 法规列表(分页+搜索+筛选) | 认证用户 |
| GET | /api/v1/regulations/{id} | 法规详情(含条文全文) | 认证用户 |
| POST | /api/v1/regulations/parse | AI解析法规全文 | 认证用户 |
| POST | /api/v1/regulations | 确认入库 | 管理员 |
| PUT | /api/v1/regulations/{id} | 编辑法规 | 管理员 |
| DELETE | /api/v1/regulations/{id} | 删除法规 | 管理员 |
| POST | /api/v1/regulations/{id}/abolish | 标记废止 | 管理员 |
| GET | /api/v1/regulations/graph | 图谱数据(Mermaid渲染用) | 认证用户 |
| POST | /api/v1/regulations/rebuild-index | 一键重建向量索引 | 管理员 |
| GET | /api/v1/regulations/stats | 统计(总数/废止数/已索引) | 认证用户 |

### 4.3 关键接口详情

**POST /api/v1/regulations/parse** —— AI解析

请求：{"raw_text": "GB/T 29639-2020 生产经营单位..."}

响应：{"code":0,"data":{"code":"GB/T 29639-2020","full_name":"","issuing_body":"","effective_date":"","replaces":[],"based_on":[],"topics":[],"articles":[],"article_count":42}}

**POST /api/v1/regulations/{id}/abolish** —— 标记废止

请求：{"replaced_by": "std_gbt29639_2020"}

**GET /api/v1/regulations/graph** —— 图谱数据

响应：{"code":0,"data":{"nodes":[...],"edges":[...]}}

**POST /api/v1/regulations/rebuild-index** —— 一键重建索引

响应：{"code":0,"data":{"total_articles":486,"status":"done","duration_seconds":12.5}}

---

## 5. 数据库设计

### 5.1 核心决策：法规数据不存 PostgreSQL

| 数据类型 | 存储位置 | 理由 |
|---|---|---|
| 图谱(节点+边) | data/graph.json | NetworkX原生格式，Git可Diff |
| 映射表 | data/index.yaml | YAML人工可读写 |
| 法规全文 | data/texts/*.md | Markdown，Git可追溯 |
| 向量索引 | data/chroma_db/ | ChromaDB自动管理 |
| 入库记录 | graph.json内created_at/updated_at | 轻量，无需单独建表 |

### 5.2 为什么不用 PostgreSQL

1. 法规数据量小（30-200条），文件系统完全够用
2. 变更频率低，每月几条修订，文件粒度刚好
3. 松耦合，不依赖PG schema变更
4. Git友好，每条法规变更可追溯
5. 可移植，graph.json + texts/ 可打包分享给其他系统

---

## 6. 前端设计

### 6.1 页面入口

系统设置 → 法规库管理（与角色管理/用户管理/提示词管理同级）

### 6.2 页面一：法规库管理（列表页）

路由：/settings/regulations

页面布局参考现有 RoleManagePage.tsx 的 CRUD 模式。包含：搜索框（关键词搜索）、状态筛选（有效/废止/全部）、类型筛选（法律/标准/政策/全部）、新增按钮、分页列表、底部统计栏（总数/有效/废止/已索引条文数）。

### 6.3 页面二：新增法规（粘贴解析流程）

**Step 1 —— 粘贴全文**：大文本框 + [自动解析结构→] 按钮。

**Step 2 —— AI解析结果预览**：展示解析出的编号、全称、发布机关、施行日期、替代关系、上位法依据、适用主题标签、条文清单（可折叠展开）。所有字段可编辑。

**Step 3**：[确认入库] 按钮 → 调用 POST /regulations → 成功Toast → 跳回列表页。

### 6.4 标记废止弹窗

搜索选择替代法规 → 确认废止 → 图谱自动添加替代边。

### 6.5 页面三：关系图谱（可视化 Tab）

法规库管理页面第二个Tab。复用现有 mermaid_renderer.py 渲染SVG图谱。

节点颜色：绿色 = 现行有效，红色 = 已废止。点击节点 → 侧边抽屉展示法规详情。

### 6.6 前端文件清单

`
frontend/src/
├── pages/Settings/RegulationManagePage.tsx      [新增] 主页面
├── components/regulation/
│   ├── RegulationList.tsx                        [新增] 列表组件
│   ├── RegulationForm.tsx                        [新增] 粘贴解析流程
│   ├── RegulationDetail.tsx                      [新增] 详情/编辑
│   ├── RegulationGraph.tsx                       [新增] 图谱Tab
│   └── AbolishDialog.tsx                         [新增] 废止弹窗
├── services/regulationService.ts                [新增] API调用层
└── types/regulation.ts                          [新增] 类型定义
`

### 6.7 TypeScript 类型定义 (regulation.ts)

核心接口：RegulationNode, RegulationEdge, RegulationArticle, RegulationParseRequest, RegulationParseResult, RegulationCreateRequest, RegulationListParams, RegulationListResponse, RegulationStats, RegulationGraphData

详细字段见实施时的具体代码。
---

## 7. 现有系统集成变更

### 7.1 变更清单

| 文件 | 变更内容 | 类型 |
|---|---|---|
| backend/app/regulations/* | 新增7个文件 + data目录 | 新增 ~500行 |
| backend/app/routers/regulations.py | 新增10个API端点 | 新增 ~300行 |
| backend/app/routers/generation.py | _build_section_prompt末尾+1行调用 | 修改 +3行 |
| backend/app/main.py | +2行 import + include_router | 修改 +2行 |
| backend/requirements.txt | +3行 chromadb, networkx, pyyaml | 修改 +3行 |
| frontend/新增7个文件 | 页面 + 5组件 + service + types | 新增 ~680行 |
| frontend/src/routes/index.tsx | +1行路由 | 修改 +1行 |

**总计**：新增约1480行代码，修改约9行现有代码。几乎零侵入。

### 7.2 generation.py 精确变更

文件顶部 import 区新增一行：
`python
from app.regulations.injector import inject_regulations
`

_build_section_prompt 函数中，mermaid_inst 处理之后、return 之前加入：
`python
prompt = inject_regulations(
    plan_type=plan_type,
    section_key=section_key,
    section_title=section_title,
    prompt=prompt,
    enterprise_data=enterprise_data,
)
`

---

## 8. 冷启动数据准备

### 8.1 30条核心法规清单

| # | 类型 | 法规 | 版本 |
|---|---|---|---|
| 1 | 法律 | 中华人民共和国安全生产法 | 2021修正 |
| 2 | 法律 | 中华人民共和国突发事件应对法 | 2007 |
| 3 | 法律 | 中华人民共和国消防法 | 2021修正 |
| 4 | 法律 | 中华人民共和国环境保护法 | 2014修订 |
| 5 | 法律 | 中华人民共和国职业病防治法 | 2018修正 |
| 6 | 法律 | 中华人民共和国劳动法 | 2018修正 |
| 7 | 法律 | 中华人民共和国特种设备安全法 | 2014 |
| 8 | 行政法规 | 生产安全事故应急条例 | 2019 |
| 9 | 行政法规 | 危险化学品安全管理条例 | 2013修订 |
| 10 | 行政法规 | 生产安全事故报告和调查处理条例 | 2007 |
| 11 | 部门规章 | 生产安全事故应急预案管理办法 | 2019修订 |
| 12 | 部门规章 | 生产经营单位安全培训规定 | 2015修订 |
| 13 | 部门规章 | 特种作业人员安全技术培训考核管理规定 | 2015修订 |
| 14 | 部门规章 | 安全生产事故隐患排查治理暂行规定 | 2008 |
| 15 | 国标 | GB/T 29639-2020 应急预案编制导则 | 2020 |
| 16 | 国标 | GB/T 13861-2022 危险有害因素分类与代码 | 2022 |
| 17 | 国标 | GB 18218-2018 危化品重大危险源辨识 | 2018 |
| 18 | 国标 | GB 6441-1986 企业职工伤亡事故分类 | 1986 |
| 19 | 国标 | GB 30871-2022 危化品特殊作业安全规范 | 2022 |
| 20 | 国标 | GB 50016-2014 建筑设计防火规范 | 2018修订 |
| 21 | 国标 | GB 50140-2005 建筑灭火器配置设计规范 | 2005 |
| 22 | 国标 | GB 30077-2023 危化品单位应急物资配备要求 | 2023 |
| 23 | 国标 | GB/T 38565-2020 应急物资分类及编码 | 2020 |
| 24 | 行标 | AQ/T 9007-2019 应急演练评估规范 | 2019 |
| 25 | 行标 | AQ/T 8001-2007 安全评价通则 | 2007 |
| 26 | 行标 | AQ 3013-2008 危化品从业单位安全标准化 | 2008 |
| 27 | 行标 | AQ/T 3033-2022 化工企业安全管理规范 | 2022 |
| 28 | 政策 | 国务院关于进一步加强安全生产工作的决定 | 2004 |
| 29 | 政策 | 关于全面加强危化品安全生产工作的意见 | 2020 |
| 30 | 政策 | 「十四五」国家安全生产规划 | 2022 |

### 8.2 条文原文整理步骤

1. 从国家法律法规数据库/国家标准全文公开系统获取条文原文
2. 每条法规整理为一个 Markdown 文件，命名格式：{编号}_{版本}.md
3. 格式规范：文件头含发布机关、施行日期、替代关系、适用主题，正文以「## 条号 条标题」分节

### 8.3 冷启动命令

`ash
python -m app.regulations.sync --bootstrap
`

读取 data/texts/ 下所有 .md 文件 → AI解析 → 写入 graph.json → 向量化 → ChromaDB。耗时约10分钟。
---

## 9. 实施步骤

### 总工期：3-4天

| 阶段 | 内容 | 产出 |
|---|---|---|
| Day 1 | 后端核心模块 | ~500行Python |
| Day 2 | API + 集成 + sync | ~400行Python |
| Day 3 | 前端全量 | ~680行TSX |
| Day 4 | 数据 + 联调验证 | 30条法规 + 测试报告 |

### Day 1 —— 后端核心（~500行）

1. requirements.txt 新增 chromadb, networkx, pyyaml
2. regulations/__init__.py 模块入口 + 延迟初始化 + 全局单例 get_retriever()
3. regulations/data/index.yaml 报告类型→法规映射
4. regulations/data/graph.json 空骨架（NetworkX兼容格式）
5. regulations/graph.py 实现 RegulationGraph 类（全部API）
6. regulations/vector_store.py 实现 RegulationVectorStore（ChromaDB封装）
7. regulations/retriever.py 实现 RegulationRetriever（两级检索）
8. regulations/injector.py 实现 inject_regulations() + _format_regulation_block()
9. 单元验证：python -c 测试各模块可用性

### Day 2 —— API + 集成 + sync（~400行）

1. regulations/sync.py AI解析 + 入库 + 废止 + 重建索引 + 图谱校验
2. routers/regulations.py 10个API端点
3. main.py 注册 regulations router
4. routers/generation.py _build_section_prompt 接入 inject_regulations()
5. Swagger UI 手动测试所有接口

### Day 3 —— 前端（~680行TSX）

1. types/regulation.ts 类型定义
2. services/regulationService.ts API调用层
3. RegulationList.tsx 列表+搜索+筛选+分页
4. RegulationForm.tsx 粘贴→解析→预览→确认三步流程
5. RegulationDetail.tsx 详情展示 + 编辑
6. RegulationGraph.tsx Mermaid图谱渲染
7. AbolishDialog.tsx 废止弹窗
8. RegulationManagePage.tsx 主页面（列表Tab + 图谱Tab）
9. routes/index.tsx 新增 /settings/regulations 路由

### Day 4 —— 数据 + 端到端联调

1. 整理30条法规的条文原文Markdown
2. 运行 python -m app.regulations.sync --bootstrap 冷启动
3. 人工审核 graph.json 关系边
4. 从前端粘贴一条新法规，验证端到端流程
5. 生成一份综合应急预案，对比注入前后编制依据质量
6. 修复发现的问题

---

## 10. 降级与异常处理

| 场景 | 行为 |
|---|---|
| graph.json 被误删 | 注入静默跳过，预案照常生成 |
| ChromaDB 损坏 | 向量检索跳过，只用图谱结果 |
| AI API 不可用（embedding） | rebuild-index 报错提示，列表页显示索引状态 |
| 图谱中引用不存在的法规id | validate_graph() 检测并提示，不阻断功能 |
| 条文超过 token 限制 | retriever 按优先级截断（core优先） |
| 法规模块任何异常 | 捕获后返回原始 prompt，预案正常生成 |

---

## 11. 附录

### A. 依赖清单

`
# backend/requirements.txt 新增
chromadb>=0.5.0       # 嵌入式向量数据库
networkx>=3.3         # 图计算引擎
pyyaml>=6.0           # YAML解析
`

### B. 环境变量（可选，均有默认值）

`ash
REGULATIONS_DATA_DIR=./app/regulations/data    # 数据目录
REGULATIONS_MAX_ARTICLES=30                     # 注入最大条文数
REGULATIONS_VECTOR_ENABLED=true                 # 向量检索开关
`

### C. 完整文件清单

**新增文件 (18个)**：

- backend/app/regulations/__init__.py
- backend/app/regulations/graph.py
- backend/app/regulations/vector_store.py
- backend/app/regulations/retriever.py
- backend/app/regulations/injector.py
- backend/app/regulations/sync.py
- backend/app/regulations/data/graph.json
- backend/app/regulations/data/index.yaml
- backend/app/regulations/data/texts/*.md (30个法规文件)
- backend/app/routers/regulations.py
- frontend/src/pages/Settings/RegulationManagePage.tsx
- frontend/src/components/regulation/RegulationList.tsx
- frontend/src/components/regulation/RegulationForm.tsx
- frontend/src/components/regulation/RegulationDetail.tsx
- frontend/src/components/regulation/RegulationGraph.tsx
- frontend/src/components/regulation/AbolishDialog.tsx
- frontend/src/services/regulationService.ts
- frontend/src/types/regulation.ts

**修改文件 (4个)**：

- backend/requirements.txt (+3行)
- backend/app/main.py (+2行)
- backend/app/routers/generation.py (+3行)
- frontend/src/routes/index.tsx (+1行)

---

> 文档结束。下一步：评审确认后进入 Day 1 实施。

---

## 12. 补充：文件上传解析（PDF / Word）

> 新增于 2026-07-07，基于用户反馈补充

### 12.1 概述

在粘贴全文的基础上，新增文件上传方式：直接上传 PDF 或 Word 文档，系统自动提取文本后交 AI 解析。

### 12.2 技术方案

上传 PDF/Word → 后端识别文件类型 → .pdf: PyMuPDF提取 → .docx: python-docx提取 → 纯文本传给DeepSeek → AI解析 → 预览确认 → 入库

### 12.3 依赖补充

PyMuPDF>=1.24.0（PDF文字提取，中文友好）。python-docx 已有，无需额外安装。

### 12.4 sync.py 新增函数

新增 extract_text_from_pdf(file_bytes), extract_text_from_docx(file_bytes), extract_text(file_bytes, filename) 三个函数。根据文件扩展名自动选择提取方式。

### 12.5 API 变更

POST /api/v1/regulations/parse 原有 raw_text 字段基础上，新增可选 file 上传字段（UploadFile）。后端逻辑：如果传了 file → 提取文本 → 如果没传 file 也没传 raw_text → 报错 400 → raw_text 统一走 AI 解析。

### 12.6 前端变更

RegulationForm.tsx Step 1 调整为两种输入方式：方式一粘贴全文（原有文本框）、方式二上传文件（支持 PDF/Word，拖拽或点击选择，限制 10MB）。文件选择后自动读取文件名和大小显示在界面上。

### 12.7 与 DeepSeek 的兼容性

用户使用 DeepSeek，方案完全兼容：结构化解析 prompt 不指定模型品牌，只要求 JSON 输出；Embedding 使用 DeepSeek 兼容接口。切换其他 AI 后自动适配。

### 12.8 更新后依赖清单

requirements.txt 新增：chromadb>=0.5.0, networkx>=3.3, pyyaml>=6.0, PyMuPDF>=1.24.0。python-docx 已有。

---

## 13. 补充：历史痕迹与源文档存储

> 新增于 2026-07-07，基于用户反馈补充

### 13.1 概述

为每一条法规保留完整生命周期记录：谁上传的原始文件、何时入库、何时修改了什么字段、何时被废止。所有原始文件（PDF/Word）永久保存，随时可预览或重新下载。

### 13.2 数据结构

在现有文件存储体系上新增两个数据文件，无需 PostgreSQL：

| 存储 | 路径 | 格式 | 说明 |
|---|---|---|---|
| 变更日志 | data/history.jsonl | JSONL（每行一个事件，追加写入） | 全局时间线 |
| 源文件 | data/uploads/{reg_id}/ | 原始文件 | 上传的PDF/Word原样保存 |

#### history.jsonl 事件格式

```json
{"event_id":"evt_001","timestamp":"2026-07-07T10:30:00Z","regulation_id":"std_gbt29639_2020","action":"created","operator":"admin","detail":{"via":"upload","filename":"GBT29639-2020.pdf","file_size":2410000}}
{"event_id":"evt_002","timestamp":"2026-07-07T11:00:00Z","regulation_id":"std_gbt29639_2020","action":"updated","operator":"admin","detail":{"changed_fields":["articles.4.1.text"],"reason":"条文更正"}}
{"event_id":"evt_003","timestamp":"2026-07-08T09:00:00Z","regulation_id":"std_aqt9002_2006","action":"abolished","operator":"admin","detail":{"replaced_by":"std_gbt29639_2020","reason":"新标准已发布"}}
```

事件类型：`created`（新增入库）、`updated`（字段修改）、`abolished`（标记废止）、`reindexed`（重新索引）、`deleted`（删除，软标记）

#### data/uploads/ 目录结构

```
data/uploads/
  └── std_gbt29639_2020/
      ├── original.pdf          # 首次上传的源文件
      └── 2026-07-07_rev.pdf    # 后续更新的源文件（带日期前缀）
```

每条法规一个子目录，保留所有版本的源文件。

### 13.3 sync.py 变更

入库流程增加三步：
1. 保存源文件到 data/uploads/{reg_id}/ 目录
2. 写入一条 history.jsonl 事件
3. 在 graph.json 对应节点更新 updated_at

修改流程：
1. 对比旧数据，记录 changed_fields
2. 写入 history.jsonl（action=updated）

废止流程：写入 history.jsonl（action=abolished）

新增工具函数：
```python
def save_source_file(regulation_id: str, file_bytes: bytes, filename: str) -> str:
    # 保存到 data/uploads/{reg_id}/{filename}
    # 返回保存路径

def log_event(regulation_id: str, action: str, operator: str, detail: dict):
    # 追加一行到 data/history.jsonl

def get_history(regulation_id: str = None, limit: int = 50) -> list[dict]:
    # 读取 history.jsonl，支持按法规筛选 + 分页
```

### 13.4 新增 API

**GET /api/v1/regulations/{id}/history** —— 单条法规变更历史

按时间倒序返回该法规的所有变更事件，含操作人、时间、变更详情、变更前后对比（如有）。前端以时间线组件展示。

**GET /api/v1/regulations/{id}/source** —— 获取源文件

返回原始上传文件（PDF或Word）。前端可在线预览（浏览器原生支持PDF，Word下载查看）。如果有多版本源文件，加 ?version=latest 参数。

**GET /api/v1/regulations/source/{id}/versions** —— 源文件版本列表

返回该法规所有上传过的源文件版本。

**GET /api/v1/regulations/history** —— 全局变更时间线

按时间倒序返回所有法规的变更事件，支持分页。前端在法规库管理页的第三个Tab「变更记录」展示。

### 13.5 前端变更

**法规详情页**（RegulationDetail.tsx）新增两个区域：

- 「变更历史」时间线：纵向展示该法规从创建到废止的全过程事件
- 「源文件」区：列出所有上传过的原始文件，点击预览/下载

**法规库管理页**（RegulationManagePage.tsx）新增第三个Tab「变更记录」：

全局变更时间线，展示最近所有法规的变更事件。可筛选按法规、按操作类型、按时间范围。

### 13.6 页面布局示意

法规库管理页三个Tab：
```
[法规列表]  [关系图谱]  [变更记录]

变更记录 Tab:
┌──────────────────────────────────────────────┐
│ 筛选：法规[全部▼] 操作[全部▼] 时间[最近30天▼]  │
│                                               │
│ ● 2026-07-08 09:00  admin                    │
│   AQ/T 9002-2006 标记为废止                   │
│   替代法规：GB/T 29639-2020                   │
│                                               │
│ ● 2026-07-07 11:00  admin                    │
│   GB/T 29639-2020 条文编辑                    │
│   修改字段：条文4.1                            │
│   原因：条文更正                               │
│                                               │
│ ● 2026-07-07 10:30  admin                    │
│   GB/T 29639-2020 新增入库                     │
│   源文件：GBT29639-2020.pdf (2.3MB) [预览]     │
│   入库条文：42条                                │
│                                               │
│ ── 第1页 / 共3页 ──                            │
└──────────────────────────────────────────────┘
```

### 13.7 文件清单补充

新增文件：
- data/history.jsonl（变更日志，自动生成）
- data/uploads/（源文件目录，自动生成）
