# Codex Custom Subagents task handoff v1

Task: task_q_t3_fix4

## 任务：法规索引纳入 article 节点（修标准号引用误报）

你是一个实现子智能体。代码质量复审发现标准号引用（如 GB/T 29639-2020）仍误报「疑似引用不存在的法规」。

根因：法规库 `graph.json` 中 GB/T 29639-2020 等标准只有 `article`（条文）类型节点（full_name 形如「GB/T 29639-2020 生产经营单位生产安全事故应急预案编制导则」），当前 `_REG_NODE_TYPES = ("law", "policy", "standard")` 排除 article，导致标准号匹配不到。

请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

当前 HEAD 应为 `1c3ee8a`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality_compliance.py -v
```

### 修复方案

`_REG_NODE_TYPES` 增加 `"article"`（保留 law/policy/standard），排除 `topic`：

```python
_REG_NODE_TYPES = ("law", "policy", "standard", "article")
```

同时 `_load_regulation_index` 中，多个节点同名 full_name 时优先保留 `effective` 状态（避免被后出现的非 effective 覆盖）：

```python
        index = {}
        for n in data.get("nodes", []):
            full = n.get("full_name", "")
            if not full or n.get("node_type") not in _REG_NODE_TYPES:
                continue
            status = n.get("status", "effective")
            if full not in index or status == "effective":
                index[full] = status
        _reg_index_cache = index
```

### 步骤：追加测试

在 `backend\tests\test_plan_quality_compliance.py` 追加：

```python
def test_l2_standard_number_ref_not_false_positive():
    from app.services.plan_quality_service import _REG_NODE_TYPES, _load_regulation_index
    assert "article" in _REG_NODE_TYPES
    index = _load_regulation_index()
    assert any("29639" in fn for fn in (index or {}))
```

（先跑一次确认真实库断言成立，若实际 full_name 不含「29639」则调整断言为检查 `_load_regulation_index` 非空且含 law 节点。）

### 完成标准

1. 索引含 law/policy/standard/article，排除 topic
2. GB/T 29639-2020 等标准号引用不再误报
3. 测试通过
4. 全量回归：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py` 全部通过

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality_compliance.py
git commit -m "fix(plan): include article nodes in regulation index so standard numbers match (quality)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 修复方式与真实库断言结果
3. pytest 结果
4. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
