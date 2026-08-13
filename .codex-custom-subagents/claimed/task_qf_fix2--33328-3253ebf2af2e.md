# Codex Custom Subagents task handoff v1

Task: task_qf_fix2

## 任务：修复 _role_matches 子串回归 + C3 前瞻变体缺口

你是一个实现子智能体。代码质量审查发现 `backend\app\services\plan_quality_service.py` 两个问题，请修复并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-fixes`

当前 HEAD 应为 `8355151`。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-fixes\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v
```

### 需修复的问题

#### 问题 1（严重）：_role_matches 子串回归——「总指挥」匹配「副总指挥」

当前 `if role in pos` 中 role="总指挥" 是 "副总指挥" 的子串，导致 position="副总指挥" 的成员被误判为承担「总指挥」。同理「副总指挥」不会被「总指挥」包含（方向相反，但「总指挥」→「副总指挥」是真实回归）。

修复：按语义分派：

```python
def _role_matches(member: dict, role: str) -> bool:
    """判断成员是否承担某角色：职务名精确/包含匹配，或总经理→总指挥/副总经理→副总指挥。"""
    pos = (member.get("position") or "") + (member.get("role") or "")
    if not pos:
        return False
    if role == "副总指挥":
        return "副总指挥" in pos or "副总经理" in pos
    if role == "总指挥":
        return ("总指挥" in pos and "副总指挥" not in pos) or "总经理" in pos
    return role in pos
```

补充测试：

```python
def test_role_matches_deputy_not_commander():
    from app.services.plan_quality_service import _role_matches
    assert _role_matches({"position": "副总指挥", "role": ""}, "副总指挥") is True
    assert _role_matches({"position": "副总指挥", "role": ""}, "总指挥") is False
    assert _role_matches({"position": "总经理", "role": ""}, "总指挥") is True
    assert _role_matches({"position": "副总经理", "role": ""}, "副总指挥") is True
```

#### 问题 2（一般）：C3 负向前瞻变体缺口

当前负向前瞻只排除「设置/分为/划分」，但「设定三级响应」「分设三级响应」「共三级响应」等变体可能漏。同时「设置」与「三级响应」之间有其他字（如「设置了三级响应」）时前瞻失效。

修复：改用「数量表述 + 级别名」的整段剔除：

```python
    # 排除数量表述：设置/设定/分为/划分为/划分/共/共设/设 三级响应（非级别名）
    level_text = re.sub(
        r"(?:设置|设定|分为|划分为|划分|共|共设|设)\s*[一二三]\s*(?:级|类)\s*(?:应急)?响应",
        "",
        full_text,
    )
    has_chinese = bool(re.search(r"一(?:级|类)(?:应急)?响应|二(?:级|类)(?:应急)?响应|三(?:级|类)(?:应急)?响应", level_text))
```

补充测试：

```python
def test_c3_more_quantity_phrases_excluded():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    for phrase in ("本预案设置三级响应", "将响应分为三级响应", "共设定三级响应"):
        result = check_plan(plan, enterprise, [
            _section("sec_3", "处置程序", f"<p>{phrase}。</p>"),
        ])
        assert not any("响应分级" in w["warning"] for w in result["warnings"]), phrase
```

### 步骤：追加测试

在 `backend\tests\test_plan_quality.py` 追加上述两个测试（含 _role_matches 单测与 C3 数量表述排除测试）。

### 完成标准

1. 2 个问题修复
2. 新增测试通过
3. 全量回归：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-fixes\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py` 全部通过

### Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-fixes
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality.py
git commit -m "fix(plan): fix role substring regression and C3 quantity-phrase exclusion (quality)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. 2 个问题修复方式
3. pytest 结果
4. commit SHA

不要提交其他文件；不要推送；不要动 TASKS.md。
