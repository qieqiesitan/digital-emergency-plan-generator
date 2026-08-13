# Codex Custom Subagents task handoff v1

Task: task_q_t2_fix

## 任务：修复 C1-C3 规格审查问题

你是一个实现子智能体。规格审查发现 `backend\app\services\plan_quality_service.py` 的 C1-C3 实现存在以下问题，请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

当前 HEAD 应为 `6d21c65`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v
```

### 需修复的问题

**1（严重）：总指挥正则误匹配副总指挥**

`(r"总指挥（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "总指挥")` 会把「副总指挥：王五」中的「总指挥：王五」也匹配为总指挥。修复：先匹配更长职务再匹配短职务，或使用负向后顾：

```python
    ROLE_PATTERNS = [
        (r"(?<!副)总指挥（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "总指挥"),
        (r"副总指挥（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "副总指挥"),
        (r"安全负责人（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "安全负责人"),
        (r"(?<!副)组长（?:：|为|是)?\s*([\u4e00-\u9fa5]{2,4})", "组长"),
    ]
```

**2（重要）：org_structure 比对用 position 而非 role 致失效**

组织架构成员字段是 `position`（职务），当前 `role in (m.get("position") or "")` 中 role="总指挥"，而成员 position 可能是「总指挥」或「组长」——这是对的；但审查指出应同时检查 `role` 字段。修复：比对时同时匹配 position 与 role：

```python
        org_names = {
            m.get("name") for g in (getattr(enterprise, "org_structure", None) or [])
            for m in g.get("members", [])
            if role in (m.get("position") or "") or role in (m.get("role") or "")
        }
```

**3（重要）：C3 时限单位混用缺失**

规格要求：同一数字模式（如「30分钟」与「0.5小时」并存）→ warning。修复：在 C3 中追加：

```python
    # 时限混用：30分钟 与 0.5小时 并存
    has_min = bool(re.search(r"\d+\s*分钟", full_text))
    has_hr = bool(re.search(r"\d+(?:\.\d+)?\s*小时", full_text))
    if has_min and has_hr:
        warnings.append({
            "section_key": "",
            "section_title": "",
            "warning": "时限表述不统一（分钟与小时混用）",
        })
```

**4（一般）：warning 文案缺章节/姓名信息**

跨章节不一致 warning 增加涉及的章节与姓名：

```python
        if len(names) > 1:
            detail = "、".join(f"「{t}」{n}" for t, n in entries)
            warnings.append({
                "section_key": "",
                "section_title": "",
                "warning": f"跨章节{role}姓名不一致：{detail}",
            })
```

### 步骤：追加测试

在 `backend\tests\test_plan_quality.py` 追加：

```python
def test_c1_deputy_commander_not_matched_as_commander():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    # 只有副总指挥，不应误报总指挥不一致
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>副总指挥：王五</p>"),
    ])
    assert not any("总指挥" in w["warning"] for w in result["warnings"])


def test_c3_time_unit_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>30分钟内上报，0.5小时后处置完毕。</p>"),
    ])
    assert any("时限" in w["warning"] for w in result["warnings"])
```

### 完成标准

1. 4 个问题全部修复
2. 新增测试通过
3. 全量回归：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py` 全部通过

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality.py
git commit -m "fix(plan): refine C1-C3 consistency checks (quality)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 4 个问题修复方式
3. pytest 结果
4. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
