# Codex Custom Subagents task handoff v1

Task: regulation_index_fix_2025

## 任务：补齐法规库 gb6441_2025 检索索引（graph 节点 + BM25 重建）

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；后端命令在 `backend` 子目录执行（系统 python 即可，不需要 chromadb）。

### 背景

终审发现：`backend/app/regulations/data/texts/gb6441_2025.md` 与 `index.yaml` 已加入，但 `graph.json` 缺 `gb6441_2025` 节点、`bm25_index.json` 无其条文，导致法规检索（query_by_plan_type('risk_assessment')）跳过该法规，AI 引用链路拿不到 GB 6441-2025。需补节点 + 重建 BM25。

### 第 1 步：向 graph.json 添加 gb6441_2025 节点

用 Python 脚本操作（必须用 `app.regulations.graph.RegulationGraph` 的 API 或等价的 json 读写，**保持文件 UTF-8 中文原样、不破坏其余 7562 个节点**）：

参考节点（gb6441_1986）字段：

```python
{
  "label": "GB",
  "full_name": "GB 6441-2025 生产安全事故分类与编码",
  "node_type": "standard",
  "code": "GB",
  "version": "",
  "effective_date": "2026-07-01",
  "issuing_body": "国家市场监督管理总局（国家标准化管理委员会）",
  "status": "effective",
  "topics": ["事故分类", "风险评估"],
  "article_count": 1,
  "source": "bootstrapped",
  "created_at": "2026-08-21T00:00:00Z",
  "updated_at": "2026-08-21T00:00:00Z",
  "ai_topics": ["事故分类", "风险评估"],
  "id": "gb6441_2025"
}
```

优先使用 `RegulationGraph` 的节点新增 API（先 `from app.regulations.graph import RegulationGraph`，`graph = RegulationGraph()`，找 `add_standard`/`add_node`/`upsert` 之类方法；若无合适 API 再直接操作 graph.json 的 nodes 列表 append 并 `save()`）。操作后必须调用持久化（`graph.save()` 或等价的写回 graph.json）。

验证：`python -c "from app.regulations import get_graph; g=get_graph(); print(g.get_node('gb6441_2025'))"` 应返回含 full_name 的节点。

### 第 2 步：重建 BM25 索引

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -c "
from app.regulations.bm25_index import BM25ArticleIndex
idx = BM25ArticleIndex()
print(idx.rebuild_all())
"
```

预期：`{'total_articles': N, 'status': 'done'}`（N 应比之前多，包含 gb6441_2025 的条文数）。

验证：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -c "
import json
data = json.load(open('app/regulations/data/bm25_index.json', encoding='utf-8'))
docs = data.get('docs', {})
hit = [k for k in docs if k.startswith('art_gb6441_2025_')]
print('gb6441_2025 docs:', len(hit), hit[:3])
"
```

预期：命中 > 0。

### 第 3 步：端到端检索验证

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -c "
from app.regulations import get_regulation_retriever
r = get_regulation_retriever()
res = r.query_by_plan_type('risk_assessment')
names = [x.get('full_name','') for x in res]
print('has gb6441_2025:', any('GB 6441-2025' in n or 'gb6441_2025' in str(x.get('id','')) for n,x in zip(names,res)))
"
```

预期：has gb6441_2025 = True（若 API 名不同，用 `dir()` 找等价方法并说明）。

### 第 4 步：提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/regulations/data/graph.json backend/app/regulations/data/bm25_index.json
git commit -m "fix(accident-types): register gb6441-2025 in regulation graph and rebuild BM25 index"
```

### 红线

- 只改 `graph.json` 与 `bm25_index.json` 两个文件（bm25 重建会重写整个文件属预期）
- 不得改动其他法规节点/条文；不得改动 index.yaml、texts/*.md
- graph.json 必须保持 UTF-8 中文正常（用 ensure_ascii=False 写回）
- 不要更新 TASKS.md
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- graph 节点添加方式与验证输出、BM25 重建输出、检索端到端验证输出
- commit SHA（git log -1 --format=%h）
