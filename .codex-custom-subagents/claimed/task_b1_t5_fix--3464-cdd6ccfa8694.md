# Codex Custom Subagents task handoff v1

Task: task_b1_t5_fix

## 任务：修复 autofill 渲染的存储型 XSS 风险

你是一个实现子智能体。代码质量审查发现 `backend\app\routers\sections.py::_render_org_structure_html` 将组织架构用户数据直接拼接进 HTML 未转义，内容最终被前端渲染，存在存储型 XSS。请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement`

当前 HEAD 应为 `70ace69`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement\backend
.\.venv\Scripts\python.exe -m pytest tests\test_plan_autofill.py -v
```

### 步骤 1：追加失败的测试（XSS 转义）

在 `backend\tests\test_plan_autofill.py` 末尾追加：

```python
def test_render_org_structure_html_escapes_user_data():
    org = [{
        "group_name": "<script>alert(1)</script>",
        "members": [
            {"name": "<img src=x onerror=alert(2)>", "position": "总指挥",
             "phone": "13800000000", "responsibilities": "负责<应急>工作"},
        ],
    }]
    html = _render_org_structure_html(org)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img" not in html
    assert "&lt;img" in html
```

### 步骤 2：运行测试验证失败

运行 pytest 命令。
预期：新增测试 FAIL（`"<script>" not in html` 断言失败）。

### 步骤 3：实现转义

修改 `backend\app\routers\sections.py`：

1. 顶部追加 `import html as _html`（若文件已有 import html 则复用）。
2. 重写 `_render_org_structure_html`，所有用户数据字段（group_name/members 的 name/position/phone/responsibilities）用 `_html.escape(str(...), quote=True)` 转义后再拼接。保持表格结构（序号/表头/表标签）本身不转义。

参考实现：

```python
def _render_org_structure_html(org_structure: list) -> str:
    """组织架构 → HTML 表格（每组一张表）。用户数据一律转义，防存储型 XSS。"""
    parts = []
    for g in org_structure or []:
        members = [m for m in g.get("members", []) if m.get("name")]
        if not members:
            continue
        rows = "".join(
            f"<tr><td>{i+1}</td><td>{_html.escape(str(m.get('name','')), quote=True)}</td>"
            f"<td>{_html.escape(str(m.get('position','')), quote=True)}</td>"
            f"<td>{_html.escape(str(m.get('phone','')), quote=True)}</td>"
            f"<td>{_html.escape(str(m.get('responsibilities','')), quote=True)}</td></tr>"
            for i, m in enumerate(members)
        )
        group_name = _html.escape(str(g.get('group_name','')), quote=True)
        parts.append(
            f"<h4>{group_name}</h4>"
            f"<table><thead><tr><th>序号</th><th>姓名</th><th>职务</th>"
            f"<th>联系电话</th><th>职责</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return "\n".join(parts)
```

### 步骤 4：运行测试验证通过

运行 pytest 命令。
预期：PASS（3 passed）。

### 步骤 5：Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-generation-enhancement
git add backend/app/routers/sections.py backend/tests/test_plan_autofill.py
git commit -m "fix(plan): escape org data in autofill HTML to prevent stored XSS (batch1)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. pytest 最终输出（几 passed）
3. commit SHA（`git rev-parse --short HEAD`）
4. 如有疑虑，说明具体内容

不要提交其他文件；不要推送；不要动 TASKS.md。
