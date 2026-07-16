# PRD-14：法规库智能引用增强

> **版本**：1.0 | **创建日期**：2026-07-16 | **依赖**：PRD-04, PRD-13 | **状态**：待评审

---

## 1. 问题定义

### 1.1 当前状态

系统已有的法规库基础设施：

| 组件 | 位置 | 能力 |
|------|------|------|
| 法规全文库 | backend/app/regulations/data/texts/ | 48 部法规的 Markdown 原文 |
| 知识图谱 | graph.py (NetworkX) | 法规节点 + 关系，按预案类型索引 |
| 向量存储 | vector_store.py (ChromaDB) | 条文级向量索引（未部署，chromadb 未安装） |
| 混合检索 | retriever.py | 图谱精确匹配 + 向量语义补充 |
| 法规注入 | injector.py / context_builder.py | 预案生成时按章节注入条文到 LLM prompt |

法规库在预案生成场景中工作良好。但在 AI 助手聊天场景中存在以下缺口：

1. search_regulations 工具实现有 bug：调用 vs.similarity_search() 但实际方法名是 vs.search()，每次都 fallback 到图谱关键字匹配，只返回元数据不返回条文原文
2. list_regulations 仅返回法规列表，没有条文内容
3. CHAT_SYSTEM_PROMPT 中没有关于引用法规的指令
4. ChromaDB 未安装，向量存储尚未构建，语义检索能力为零

### 1.2 目标

用户在聊天助手中询问安全生产、应急管理、消防、职业健康等法规问题时，AI 能够：
- 自动检索法规库中相关条文原文
- 基于实际法规内容回答问题
- 在回答末尾列出引用，格式为：《法规全称》（文号）第 X 条

---

## 2. 整体架构

```
用户提问
    │
    ▼
chat.py  agent_loop
system prompt 识别法规类问题 → 触发 search_regulation_articles 工具
    │
    ▼
chat_dispatch.py  _search_regulation_articles()
调向量库语义检索 + 图谱补全元数据
    │
  ┌─┴─┐
  ▼   ▼
向量库  图谱
ChromaDB 语义检索 top-8 条文 → graph.get_node() 补全法规全称/文号/状态
  │   │
  └─┬─┘
    ▼
结构化结果 (JSON)
[{article_text, article_number, regulation_full_name, regulation_code, status, similarity_score}]
    │
    ▼
LLM (DeepSeek/Qwen/GPT)
基于条文回答 + 末尾引用格式
    │
    ▼
前端渲染
Markdown → HTML（现有链路）或 plain text with pre-wrap
```

---

## 3. 分阶段实施计划

### 第一阶段（约 2.5h）—— 核心检索 + 引用

目标：聊天助手具备法规引用能力，端到端可验证。

#### 3.1.1 安装 chromadb 并构建向量存储

当前 Python 环境中未安装 chromadb，向量存储尚未构建。需先就绪。

```
pip install chromadb
```

然后运行一次全量索引构建。RegulationVectorStore 已有 rebuild_all() 方法，第一阶段使用 ChromaDB 内置默认嵌入模型（all-MiniLM-L6-v2）。

新增脚本：backend/scripts/build_regulation_index.py

```python
"""一次性构建法规向量索引。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.regulations.vector_store import RegulationVectorStore

if __name__ == "__main__":
    vs = RegulationVectorStore()
    result = vs.rebuild_all(embedding_fn=None)
    print(f"索引构建完成: {result}")
```

核验：索引构建后 chroma_db/ 目录出现，vs.collection_count() > 0。

#### 3.1.2 修复 search_regulations 的 bug

文件：backend/app/services/chat_dispatch.py，约第 406 行

当前代码：
```python
results = vs.similarity_search(query, k=5)
```

修复为：
```python
results = vs.search(query, top_k=5)
```

同时调整返回值字段名从 doc.page_content/doc.metadata 改为 item["text"]/item["metadata"]。

#### 3.1.3 新增 search_regulation_articles 工具

chat.py — 工具定义（追加到 CHAT_TOOLS 数组末尾）：

```python
{"type": "function", "function": {
    "name": "search_regulation_articles",
    "description": "语义检索法规条文原文。当用户询问安全生产、应急管理、消防、职业健康、特种设备、危化品等法律法规问题时，必须调用此工具查找相关法律条文的具体内容和出处。返回条文原文、所属法规全称、文号、条款号",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户问题的关键词或完整句子"},
            "top_k": {"type": "integer", "description": "返回条数，默认 8，范围 3-15"}
        },
        "required": ["query"]
    }
}},
```

chat_dispatch.py — Handler 实现（新增函数）：

```python
async def _search_regulation_articles(db, user, args):
    """法规条文语义检索——供聊天助手回答法规问题时使用。

    流程：向量库语义检索 top-K 条文 → 图谱补全法规元数据 → 过滤废止法规
    """
    query = args.get("query", "")
    if not query:
        return {"error": "请提供 query"}

    top_k = _parse_int(args.get("top_k", 8)) or 8
    top_k = max(3, min(top_k, 15))

    from app.regulations import get_vector_store, get_graph
    vs = get_vector_store()
    graph = get_graph()

    articles = []
    seen = set()

    # 第一层：向量语义检索
    if vs and vs.collection_count() > 0:
        try:
            results = vs.search(query, top_k=top_k)
        except Exception:
            results = []
    else:
        results = []

    # 第二层：图谱补全元数据
    for item in results:
        meta = item.get("metadata", {})
        reg_id = meta.get("regulation_id", "")
        if reg_id in seen:
            continue
        seen.add(reg_id)

        node = graph.get_node(reg_id)
        if not node or node.get("status") == "abolished":
            continue

        articles.append({
            "article_text": item.get("text", ""),
            "article_number": meta.get("article", ""),
            "regulation_id": reg_id,
            "regulation_full_name": node.get("full_name", node.get("title", "")),
            "regulation_code": node.get("code", ""),
            "regulation_status": node.get("status", "effective"),
            "similarity_score": round(1 - item.get("distance", 0), 4),
        })

    # 第三层：无结果时降级到图谱关键词检索
    if not articles:
        keyword_result = graph.list_nodes(keyword=query, page_size=5)
        return {
            "articles": [],
            "fallback_message": "法规库中暂未找到与您问题直接相关的条文。以下是与关键词匹配的法规列表供参考：",
            "fallback_regulations": [
                {"id": n.get("id"), "full_name": n.get("full_name", ""),
                 "code": n.get("code", ""), "status": n.get("status")}
                for n in keyword_result.get("items", [])
            ],
        }

    return {"articles": articles, "count": len(articles)}
```

注册到 _FUNCTIONS：
```python
"search_regulation_articles": _search_regulation_articles,
```

#### 3.1.4 更新 CHAT_SYSTEM_PROMPT

在现有 prompt 末尾追加：

```
【法规引用规则——必须严格遵守】
当用户询问安全生产、应急管理、消防、职业健康、特种设备、危险化学品、
事故调查、隐患排查、安全培训、应急预案编制等法律法规相关问题时，
必须执行以下步骤：

1. 立即调用 search_regulation_articles 工具检索相关法规条文。
   query 参数应为用户问题的完整句子或关键词，不要自行提炼。

2. 回答必须基于工具返回的实际条文内容，不得编造法规名称或条款号。
   如果工具返回了条文，应在回答中体现条文要求。
   如果工具返回为空（articles=[]），明确告知用户：
   "法规库中暂未找到与您问题直接相关的条文，以下建议基于一般性原则——"
   然后可以基于常识给出指导，但不要编造具体法规名称和条款号。

3. 回答末尾必须以「📋 引用法规」为标题，列出所引用的法规。
   每一条引用格式为：
   - 《法规全称》（文号）第X条
   示例：
   - 《中华人民共和国安全生产法》（2021修正）第二十一条
   - 《生产安全事故应急预案管理办法》（应急管理部令第2号）第八条

4. 引用列表只包含实际在回答中用到的法规，不凑数。

5. 如果用户问的问题与法律法规无关（如系统操作、数据统计），
   不需要调用此工具，也不需要添加引用列表。
```

#### 3.1.5 前端改动

第一阶段前端零改动。引用信息作为 Markdown 格式文本嵌入到 LLM 回复末尾，现有前端已支持展示。

#### 3.1.6 第一阶段工作量

| 任务 | 文件 | 预估 |
|------|------|------|
| 安装 chromadb + 构建索引 | requirements.txt + 新建脚本 | 20min |
| 修复 search_regulations bug | chat_dispatch.py | 5min |
| 新增 search_regulation_articles | chat.py + chat_dispatch.py | 45min |
| 更新 system prompt | chat.py | 15min |
| 本地测试验证 | - | 30min |
| **小计** | | **~2h** |

---

### 第二阶段（约 3h）—— 中文向量模型升级

目标：用中文优化嵌入模型替换 ChromaDB 默认的 all-MiniLM-L6-v2，显著提升语义检索准确率。

#### 3.2.1 问题分析

ChromaDB 默认嵌入模型 all-MiniLM-L6-v2（384 维）针对英文优化。对中文法规文本：
- 分词效果差，中文词语被当作单个字符处理
- 专业术语不敏感

#### 3.2.2 方案选型

| 方案 | 模型 | 维度 | 中文效果 | 模型体积 |
|------|------|------|---------|---------|
| A | shibing624/text2vec-base-chinese | 768 | ★★★★★ | ~400MB |
| B | BAAI/bge-small-zh-v1.5 | 512 | ★★★★★ | ~100MB |
| C | intfloat/multilingual-e5-small | 384 | ★★★★ | ~120MB |

推荐方案 B：BGE-small-zh 在中文检索评测中表现最优，体积小，通过 sentence-transformers 直接加载。

#### 3.2.3 实施步骤

Step 1：安装依赖
```
pip install sentence-transformers
```

Step 2：新增 backend/app/regulations/embeddings.py

```python
"""中文法规文本嵌入模型封装。"""
from sentence_transformers import SentenceTransformer

_model = None

def get_embedding_fn():
    """延迟加载 BGE-small-zh 模型（~100MB）。"""
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    """将中文文本列表转为 512 维向量列表。"""
    model = get_embedding_fn()
    return model.encode(texts, normalize_embeddings=True).tolist()
```

Step 3：修改 vector_store.py，调用 add_regulation 时传入 embedding_fn=embed_texts

Step 4：删除旧 chroma_db/ 目录，重建索引
```
python backend/scripts/build_regulation_index.py
```

Step 5：修改 search_regulation_articles 中查询文本加 BGE 前缀
```python
query = f"为这个句子生成表示以用于检索相关文章：{original_query}"
results = vs.search(query, top_k=top_k)
```

#### 3.2.4 核验方法

设计 5 组测试用例：

| 查询 | 期望命中 |
|------|---------|
| "企业应急预案应该多久演练一次" | 《生产安全事故应急预案管理办法》演练周期条款 |
| "特种设备操作人员需要什么证件" | 《特种设备安全法》作业人员资格条款 |
| "危险化学品储存有哪些要求" | 《危险化学品安全管理条例》储存条款 |
| "安全事故报告时限是多少" | 《生产安全事故报告和调查处理条例》报告时限条款 |
| "消防安全检查多久做一次" | 《消防法》检查条款 |

要求：5 组中至少 4 组的第一条结果与期望命中一致。

#### 3.2.5 第二阶段工作量

| 任务 | 预估 |
|------|------|
| 安装 sentence-transformers + 下载模型 | 15min |
| 新增 embeddings.py | 15min |
| 修改 vector_store + 重建索引 | 45min |
| 测试 5 组用例 + 调优 | 1.5h |
| **小计** | **~3h** |

---

### 第三阶段（约 4h）—— 前端引用增强

目标：引用不再是纯文本，而是精美格式化的卡片，点击可查看条文原文。

#### 3.3.1 后端改造

调整 LLM 输出格式：system prompt 要求 LLM 在回答末尾将引用格式化为结构化标记：

```
<!--CITATIONS-->
- 《中华人民共和国安全生产法》（2021修正）第二十一条 | law_safety_production_2021
- 《生产安全事故应急预案管理办法》（应急管理部令第2号）第八条 | policy_plan_management_2019
```

chat.py 的 agent_loop 检测 <!--CITATIONS--> 标记，解析为结构化 JSON，追加为 SSE 事件：

```json
{"type": "citations", "items": [
  {"name": "中华人民共和国安全生产法", "code": "2021修正",
   "article": "第二十一条", "regulation_id": "law_safety_production_2021"},
  {"name": "生产安全事故应急预案管理办法", "code": "应急管理部令第2号",
   "article": "第八条", "regulation_id": "policy_plan_management_2019"}
]}
```

ChatSSEEvent 的 type union 增加 "citations"。

#### 3.3.2 新增后端 API：GET /api/v1/regulations/{id}/articles

用途：前端点击引用卡片后，通过此 API 获取该法规的完整条文。

```python
@router.get("/{regulation_id}/articles")
async def get_regulation_articles(regulation_id: str):
    """获取指定法规的完整条文列表。"""
    from app.regulations import get_graph
    graph = get_graph()
    node = graph.get_node(regulation_id)
    if not node:
        raise HTTPException(404, "法规不存在")
    articles = _load_articles_from_file(regulation_id)
    return {"regulation": node, "articles": articles}
```

#### 3.3.3 前端改动

新增组件：frontend/src/components/chat/CitationCard.tsx

设计要点：
- 卡片式布局，浅灰背景 + 左侧色带（法律-蓝、行政法规-绿、部门规章-橙、标准-灰）
- 显示：法规全称、文号、条款号、条文首行摘要
- 点击展开：显示条文完整原文（通过 API 获取）
- hover 状态：微阴影 + framer-motion 动画

修改 chat/index.tsx：
- 监听 SSE 事件 type === "citations"
- 在消息底部渲染 CitationCard 列表
- 引用区域与正文用分割线隔开

#### 3.3.4 第三阶段工作量

| 任务 | 预估 |
|------|------|
| 后端 LLM 输出格式调整 | 1h |
| 新增 /regulations/{id}/articles API | 30min |
| 前端 CitationCard 组件 | 1.5h |
| 前端 chat 页面集成 | 1h |
| **小计** | **~4h** |

---

### 第四阶段（约 3h）—— 法规时效性智能提示

目标：AI 回答时自动识别并标注法规的时效状态，防止引用已废止的法规。

#### 3.4.1 当前基础

知识图谱中每条法规节点已有 status 字段（effective/abolished）。search_regulation_articles 已在返回结果前过滤 status == "abolished" 的法规。

但仍需增强：
- 检查"部分废止"（法规总体有效但某些条款被新法替代）
- 告知用户某法规的最新修订版本

#### 3.4.2 图谱补齐

在 graph.json 中补充字段：
```json
{
  "law_safety_production_2021": {
    "status": "effective",
    "effective_date": "2021-09-01",
    "latest_revision": "2021年修正",
    "replaces": ["law_safety_production_2014"]
  }
}
```

在 search_regulation_articles 返回结果中追加 superseded_info：
```python
chain = graph.trace_chain(reg_id, relation="替代")
if chain:
    article["replaces"] = chain[1:]
```

#### 3.4.3 System prompt 追加

```
如果检索到的法规有 replaces 字段，可在回答中提及"该法规替代了《旧法名称》"。
如果检索到多个版本同一个法规，优先引用最新版本。
```

#### 3.4.4 第四阶段工作量

| 任务 | 预估 |
|------|------|
| 图谱字段补齐（48 个节点） | 1h |
| search_regulation_articles 时效性增强 | 1h |
| system prompt 更新 + 测试 | 1h |
| **小计** | **~3h** |

---

## 4. 涉及文件清单

| 文件 | 阶段 | 改动类型 |
|------|------|---------|
| backend/requirements.txt | P1 | 追加 chromadb（P2 追加 sentence-transformers） |
| backend/scripts/build_regulation_index.py | P1 | 新增 |
| backend/app/services/chat_dispatch.py | P1-P4 | 修复 bug + 新增 handler + 多次增强 |
| backend/app/routers/chat.py | P1-P3 | 新增工具定义 + 更新 system prompt + SSE 事件 |
| backend/app/regulations/vector_store.py | P2 | 支持外部 embedding_fn |
| backend/app/regulations/embeddings.py | P2 | 新增 |
| backend/app/regulations/graph.py | P4 | 补充 trace_predecessors 方法 + 节点字段 |
| backend/app/regulations/data/graph.json | P4 | 节点字段补齐 |
| backend/app/routers/regulations.py | P3 | 新增 /articles 端点 |
| frontend/src/components/chat/CitationCard.tsx | P3 | 新增 |
| frontend/src/pages/Chat/index.tsx | P3 | 集成 CitationCard |
| frontend/src/services/chatService.ts | P3 | 类型扩展 |

---

## 5. 风险与边界

| 风险 | 影响 | 对策 |
|------|------|------|
| ChromaDB 默认嵌入中文效果差 | P1 语义检索准确率不如预期 | 可接受，P2 用 BGE 模型彻底解决 |
| sentence-transformers 依赖 PyTorch ~1.5GB | 部署包体积增大 | 用 CPU only 版本，模型文件仅 ~100MB |
| LLM 不一定按引用格式输出 | 引用不完整或格式错误 | system prompt 加强约束 + 必要时做格式校验后处理 |
| 法规库数据不完整 | 某些问题检索不到对应条文 | system prompt 已指示如实告知用户，不编造 |
| CHAT_TOOLS 数组膨胀 | 超过 LLM context 限制 | 当前 36 个，增加后 37 个，仍在安全范围 |

---

## 6. 验收标准

### P1 验收

1. 用户问"企业必须制定应急预案吗？"→ AI 调用了 search_regulation_articles → 回答引用了《安全生产法》第八十一条 → 末尾有引用列表
2. 用户问"如何创建企业？"→ AI 不调用 search_regulation_articles → 无引用列表
3. 用户问"消防通道宽度有什么要求？"→ AI 检索到 GB 50016 相关条文 → 引用格式正确
4. search_regulations 的 bug 被修复：调用后不报 AttributeError

### P2 验收

5 组测试用例中，至少 4 组的 top-1 结果与期望命中一致

### P3 验收

1. 引用在聊天界面中渲染为卡片式，有视觉区分
2. 点击引用卡片可展开查看条文原文
3. 不同法规类型有不同颜色标识

### P4 验收

1. 已废止的法规不会出现在检索结果中
2. AI 回答时会说明某法规替代了哪些旧法

---

## 7. 不做的范围

- 不上传法规 PDF/Word 自动解析（已有手动上传功能，不在本次范围）
- 不做法规全文搜索页面的搜索引擎级改造
- 不做多轮对话记忆的法规上下文持久化
- 不做法规变更自动推送/监控
