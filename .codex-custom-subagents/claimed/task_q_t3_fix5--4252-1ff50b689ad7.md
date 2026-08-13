# Codex Custom Subagents task handoff v1

Task: task_q_t3_fix5

## 任务：修复法规索引短键导致 L2 漏报

你是一个实现子智能体。代码质量复审发现 `backend\app\services\plan_quality_service.py` 的 L2 比对存在漏报：article 节点中部分 `full_name` 是短键（如单字符「1」「A」「D」或短中文），双向包含匹配 `full_norm in norm` 会让任意引用（如「安全生产法」含「全」）命中短键，导致引用全部被视为「存在」、不再报疑似不存在。

请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

当前 HEAD 应为 `3e375d9`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality_compliance.py -v
```

### 修复方案

在 `_load_regulation_index` 构建索引时，过滤过短的 full_name（归一化后长度 < 4 的丢弃，避免短键污染匹配）：

```python
        index = {}
        for n in data.get("nodes", []):
            full = n.get("full_name", "")
            if not full or n.get("node_type") not in _REG_NODE_TYPES:
                continue
            if len(_normalize(full)) < 4:
                continue
            status = n.get("status", "effective")
            if full not in index or status == "effective":
                index[full] = status
        _reg_index_cache = index
```

同时 L2 比对改为仅 `norm in full_norm`（引用应在法规全名内），去掉 `full_norm in norm` 反向方向，避免短键方向漏报：

```python
            if reg_index:
                for full, status in reg_index.items():
                    full_norm = _normalize(full)
                    if norm_ref in full_norm:
                        matched_status = status
                        break
```

注：反向方向（法规名是引用子串）本来就不该用——正文引用「安全生产法」而库名「中华人民共和国安全生产法」时，`norm in full_norm` 已覆盖（「安全生产法」在「中华人民共和国安全生产法」内）。去掉反向方向无损失。

### 步骤：追加测试

在 `backend\tests\test_plan_quality_compliance.py` 追加：

```python
def test_l2_short_key_nodes_do_not_mask_missing_refs():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    with patch("app.services.plan_quality_service._load_regulation_index") as mock_load:
        # 构造含短键的索引：单字符「1」「全」不应让任意引用命中
        mock_load.return_value = {"1": "effective", "全": "effective", "中华人民共和国安全生产法": "effective"}
        result = check_plan(plan, enterprise, [
            _section("sec_1", "事故风险分析", "<p>依据《不存在的法规X》要求。</p>"),
        ])
    assert any("不存在" in w["warning"] for w in result["warnings"])
```

并确认 `_load_regulation_index` 真实索引不含长度 < 4 的 key（跑一次断言）。

### 完成标准

1. 索引过滤短键（归一化长度 < 4）
2. L2 比对仅 `norm in full_norm`（去掉反向）
3. 测试通过
4. 全量回归：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py` 全部通过

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality_compliance.py
git commit -m "fix(plan): drop short regulation keys and use one-way match to stop L2 false negatives (quality)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 修复方式
3. pytest 结果
4. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
