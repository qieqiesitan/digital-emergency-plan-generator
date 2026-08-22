# Codex Custom Subagents task handoff v1

Task: final_review_accident_types_v2

## 任务：最终整体复审 — 法规库索引修复闭环确认（commit 6288031）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

上一轮终审（final_review_accident_types）唯一必须修复项为「法规库检索索引链路未完成」，已由 commit `6288031` 修复。本任务复核该修复是否闭环，并确认整体分支可合并。这是只读审查：不要修改任何源码。

### 复核项（逐条）

1. `git show --stat 6288031` 确认只含 `backend/app/regulations/data/graph.json` 与 `bm25_index.json`
2. graph 节点：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -c "from app.regulations import get_graph; print(get_graph().get_node('gb6441_2025'))"` 应返回含 full_name「GB 6441-2025 生产安全事故分类与编码」的节点
3. BM25：`python -c "import json; data=json.load(open('app/regulations/data/bm25_index.json',encoding='utf-8')); docs=data.get('docs',{}); print(sum(1 for k in docs if k.startswith('art_gb6441_2025_')), 'docs')"` 应 > 0
4. 端到端检索：`python -c "from app.regulations import get_retriever; r=get_retriever(); res=r.graph.query_by_plan_type('risk_assessment'); print(any('gb6441_2025' in str(x.get('id','')) for x in res))"`（或等价 API）应 True
5. 工作树干净（`git status --short` 空）；`git log --oneline -3` 确认 HEAD=6288031
6. 门禁复跑（可选，若时间允许）：backend pytest 全量 + frontend tsc/vitest；至少复跑 `python -m pytest tests/test_accident_types.py tests/test_risk_notice_card_service.py -q`

### 汇报格式

- 结论：✅ 可合并 | ❌ 需修复（逐条列出）
- 6 项逐条核验结果
- task_id、claim_id、path（claim_task.py 输出）
