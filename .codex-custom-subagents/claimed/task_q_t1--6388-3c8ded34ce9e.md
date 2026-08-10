# Codex Custom Subagents task handoff v1

Task: task_q_t1

## 任务：C0 基础修正（必含章节粒度 + 地址片段匹配）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check`

这是 git 分支 `codex/quality-check-enhancement` 的隔离 worktree（基于 7365e77）。`backend\.venv` 已 junction 链接，但主工作区 venv 的 pytest 损坏，**测试必须用 Docker 容器跑**（挂载 worktree 的 backend 目录 + 2_chroma_cache 卷）。启动时 `cd` 到该目录，`git status` 确认干净。

### 测试命令（必须挂 2_chroma_cache 卷）

```powershell
docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v
```

### 背景

`backend\app\services\plan_quality_service.py` 的「档案字段未体现」目前逐章节检查且整串匹配，导致非必含章节误报、地址前缀差异误报。本次改为：仅必含章节检查（comprehensive=sec_2 / special=sec_1 / onsite=sec_1），地址用关键片段匹配。

### 步骤 1：编写失败的测试

在 `backend\tests\test_plan_quality.py` 末尾追加（文件顶部已有 `_section` 辅助函数与 MagicMock 导入）：

```python
from app.services.plan_quality_service import (
    check_plan, _extract_address_fragments, _must_have_section_key,
)


def test_must_have_section_keys():
    assert _must_have_section_key("comprehensive") == "sec_2"
    assert _must_have_section_key("special") == "sec_1"
    assert _must_have_section_key("onsite") == "sec_1"
    assert _must_have_section_key("unknown") is None


def test_extract_address_fragments():
    frags = _extract_address_fragments("陕西省西安市经济技术开发区民经一路726号2幢12402室")
    assert any("民经一路726号" in f for f in frags)
    assert any("经济技术开发区" in f for f in frags)


def test_non_must_have_section_no_archive_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号2幢12402室",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [_section("sec_3", "处置程序与措施", "<p>内容</p>")])
    assert not any("未体现" in w["warning"] for w in result["warnings"])


def test_must_have_section_address_fragment_match_no_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号2幢12402室",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>公司位于民经一路726号，法定代表人为刘昕野，安全负责人刘昕野。</p>")
    ])
    assert not any("未体现" in w["warning"] for w in result["warnings"])
```

### 步骤 2：运行测试验证失败

运行 pytest 命令。
预期：FAIL，`ImportError: cannot import name '_must_have_section_key'`

### 步骤 3：实现 C0

修改 `backend\app\services\plan_quality_service.py`：

1. 模块级新增：

```python
MUST_HAVE_SECTION = {"comprehensive": "sec_2", "special": "sec_1", "onsite": "sec_1"}


def _must_have_section_key(plan_type: str) -> str | None:
    return MUST_HAVE_SECTION.get(plan_type)


def _extract_address_fragments(address: str) -> list:
    """从档案地址提取关键片段：区县/路街/门牌级别，用于模糊匹配。"""
    if not address:
        return []
    frags = []
    m = re.search(r"[\u4e00-\u9fa5]{2,12}(?:路|街|大道)[0-9０-９]*号?", address)
    if m:
        frags.append(m.group(0))
    m = re.search(r"[\u4e00-\u9fa5]{2,10}(?:区|县|开发区|新区)", address)
    if m:
        frags.append(m.group(0))
    return frags
```

2. `check_plan` 内删除原「逐章节 for field」的档案字段块，替换为：

```python
        # C0：档案字段未体现 —— 仅必含章节检查，地址用关键片段匹配
        must_key = _must_have_section_key(getattr(plan, "plan_type", ""))
        if s.section_key == must_key:
            norm_text = _normalize(text)
            for field, label, use_frag in [
                (getattr(enterprise, "address", None), "地址", True),
                (getattr(enterprise, "legal_representative", None), "法定代表人", False),
                (getattr(enterprise, "safety_officer", None), "安全负责人", False),
            ]:
                if not field or field in ("（待补充）",):
                    continue
                if use_frag:
                    frags = _extract_address_fragments(field)
                    matched = any(_normalize(f) in norm_text for f in frags) if frags else _normalize(field) in norm_text
                else:
                    matched = _normalize(field) in norm_text
                if not matched:
                    warnings.append({
                        "section_key": s.section_key,
                        "section_title": s.title,
                        "warning": f"正文未体现企业档案{label}：{field}",
                    })
```

### 步骤 4：运行测试验证通过 + 全量回归

运行：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/test_plan_quality.py -v`
预期：PASS

运行：`docker run --rm -v "C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check\backend:/app" -v "2_chroma_cache:/root/.cache/chroma" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

### 步骤 5：Commit

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-quality-check
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality.py
git commit -m "fix(plan): check archive fields only in must-have section with fragment matching (quality C0)"
```

### 完成报告

最终回复报告：
1. 状态：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
2. pytest 最终输出与全量回归结果
3. commit SHA（`git rev-parse --short HEAD`）
4. 如有疑虑，说明具体内容

不要提交其他文件；不要推送；不要动 TASKS.md。
