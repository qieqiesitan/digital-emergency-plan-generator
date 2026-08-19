# Codex Custom Subagents task handoff v1

Task: task_org_05_fix

## 目标

按组织任务 5 质量审查建议为 `_summarize_org_structure` 补直接单测，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`0642101`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 文件

- 修改：`backend/tests/test_enterprise_org.py`

## 修复

补 `_summarize_org_structure` 单测（从 `app.services.enterprise_org_service` 导入）：

```python
def test_summarize_org_structure_paths():
    nodes = [
        {"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []},
        {"id": "t1", "type": "team", "name": "甲班", "parent_id": "d1", "members": []},
        {"id": "t2", "type": "team", "name": "乙班", "parent_id": "d1", "members": []},
    ]
    summary = _summarize_org_structure(nodes)
    assert "生产部" in summary
    assert "生产部/甲班" in summary
    assert "生产部/乙班" in summary

def test_summarize_org_structure_cycle_safe():
    nodes = [
        {"id": "a", "type": "dept", "name": "A", "parent_id": "b", "members": []},
        {"id": "b", "type": "dept", "name": "B", "parent_id": "a", "members": []},
    ]
    summary = _summarize_org_structure(nodes)
    assert isinstance(summary, str)
    assert summary != ""

def test_summarize_org_structure_empty():
    assert _summarize_org_structure([]) == "（暂无）"
```

（按实际函数签名与返回文案微调；断言行为而非实现。）

## 验证

- `python -m pytest tests/test_enterprise_org.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；`git diff --check` 干净。

## Commit

```bash
git add backend/tests/test_enterprise_org.py
git commit -m "test(org): cover org structure summarizer"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_05_fix --claim-id <claim_id> --exit-code 0 --summary "组织任务5摘要单测完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果。

## 规则

- 用 `apply_patch` 编辑；只改列出的 1 个文件；阻塞时停下汇报。
