# Codex Custom Subagents task handoff v1

Task: task_02_fix_merge

## 目标

修复任务 2 实现中的一个合并顺序 bug：`get_dict_map` 的合并依赖查询行序，字符串升序下系统行后到会覆盖企业行，与「企业 > 系统」语义相反。改为顺序无关 + 企业优先，并追加反序测试。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`b0a1020`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 文件

- 修改：`backend/app/services/data_dict_service.py`
- 修改：`backend/tests/test_data_dict.py`

## 步骤

- [ ] **步骤 1：追加反序失败测试**（`backend/tests/test_data_dict.py` 末尾追加）

```python
@pytest.mark.asyncio
async def test_enterprise_wins_regardless_of_row_order():
    db = MagicMock()
    db.execute = AsyncMock()
    rows = [
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.3}, scope="enterprise", enterprise_id="ent-1"),
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", is_system=True),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert merged["engineering"]["value"]["factor"] == 0.3
```

（企业行在前、系统行在后——若实现仍依赖行序，此测试会失败。）

- [ ] **步骤 2：运行测试确认失败**

在 `backend` 目录 `python -m pytest tests/test_data_dict.py -v`
预期：新用例 FAIL（现有实现让系统行覆盖企业行），其余 4 用例 PASS

- [ ] **步骤 3：修复合并逻辑**（`backend/app/services/data_dict_service.py`）

把合并循环改为：

```python
    merged: dict[str, dict] = {}
    for r in rows:
        if r.code not in merged or r.enterprise_id is not None:
            merged[r.code] = {"label": r.label, "value": r.value, "description": r.description}
    _cache[key] = (now, merged)
    return merged
```

语义：企业条目（enterprise_id 非空）总是覆盖同 code 系统条目；系统条目只在无企业条目时生效。不再依赖查询行序（查询保留原 `order_by` 亦可）。

- [ ] **步骤 4：运行测试验证通过**

在 `backend` 目录 `python -m pytest tests/test_data_dict.py -v`，预期 5 passed；再跑 `python -m pytest tests/ -q` 确认无回归。

- [ ] **步骤 5：Commit**

在 `.worktrees\dual-prevention` 内：

```bash
git add backend/app/services/data_dict_service.py backend/tests/test_data_dict.py
git commit -m "fix(data-dict): order-independent enterprise-over-system dict merge"
```

不要提交 TASKS.md；消息精确匹配；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_02_fix_merge --claim-id <claim_id> --exit-code 0 --summary "字典合并顺序修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果。

## 规则

- 用 `apply_patch` 编辑文件；只改列出的 2 个文件；
- 阻塞或有疑问时停下汇报。
