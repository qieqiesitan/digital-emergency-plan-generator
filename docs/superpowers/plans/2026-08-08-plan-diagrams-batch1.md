# 预案附图扩展 第 1 批（LLM mermaid 图）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在现有流程图基础上，让 AI 在指定章节额外生成应急组织架构图、信息上报时序图、处置时间轴、演练甘特图四类 mermaid 图。

**架构：** 扩展 `generation.py` 的 `SECTION_DIAGRAM_TYPE_MAP` 与 `prompt_cache.py` 图提示词模板；组织架构图依据企业 `org_structure` 生成（注入真实数据），其余三类纯提示词驱动；渲染沿用现有 `_pre_render_mermaid_svgs` → `mermaid_svgs` 管线，本批不新增存储。

**技术栈：** FastAPI + SQLAlchemy async；mermaid（本地渲染）；React + TypeScript（本批仅后端）。

**规格：** `docs/superpowers/specs/2026-08-08-plan-diagrams-enhancement-design.md` §3、§3.1、§6.2（org_chart 部分）、§6.3

---

## 文件结构

**后端：**
- 修改 `backend/app/routers/generation.py` — 章节映射扩展、org_structure→mermaid 文本构建、enterprise_data 注入
- 修改 `backend/app/services/prompt_cache.py` — 新增 4 类图提示词模板
- 新增 `backend/tests/test_plan_diagram_prompts.py`

---

### 任务 1：章节图映射扩展

**文件：**
- 修改：`backend/app/routers/generation.py`（`SECTION_DIAGRAM_TYPE_MAP` / `FLOWCHART_SECTION_MAP` 附近）
- 测试：`backend/tests/test_plan_diagram_prompts.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagram_prompts.py
from app.routers.generation import (
    SECTION_ADDITIONAL_DIAGRAM_MAP,
)


def test_additional_diagram_map_covers_sections():
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_3"] == "org_chart"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_4_2"] == "report_sequence"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_5"] == "response_timeline"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_9_1"] == "drill_gantt"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_prompts.py -v`
预期：FAIL，`ImportError: cannot import name 'SECTION_ADDITIONAL_DIAGRAM_MAP'`

- [ ] **步骤 3：实现映射表**

```python
# backend/app/routers/generation.py  在 SECTION_DIAGRAM_TYPE_MAP 附近新增：
# 每个章节除主流程图外可附加的图类型（key 对应 plan_diagram_service 的 diagram key）
SECTION_ADDITIONAL_DIAGRAM_MAP: dict[str, str] = {
    "sec_3":   "org_chart",          # 应急组织机构及职责 → 组织架构图
    "sec_4_2": "report_sequence",    # 信息报告程序 → 上报时序图
    "sec_5":   "response_timeline",  # 应急响应 → 处置时间轴
    "sec_9_1": "drill_gantt",        # 培训与演练 → 演练甘特图
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_prompts.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/generation.py backend/tests/test_plan_diagram_prompts.py
git commit -m "feat(plan): add additional diagram type map for plan sections (diagrams batch1)"
```

---

### 任务 2：图提示词模板

**文件：**
- 修改：`backend/app/services/prompt_cache.py`
- 测试：`backend/tests/test_plan_diagram_prompts.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagram_prompts.py 追加
from app.services.prompt_cache import get_additional_diagram_prompt


def test_additional_diagram_prompts_exist():
    for key in ("org_chart", "report_sequence", "response_timeline", "drill_gantt"):
        assert get_additional_diagram_prompt(key), f"missing prompt for {key}"
    assert "org_structure" in get_additional_diagram_prompt("org_chart")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_prompts.py -v`
预期：FAIL，`AttributeError: module 'app.services.prompt_cache' has no attribute 'get_additional_diagram_prompt'`

- [ ] **步骤 3：实现模板与查询函数**

```python
# backend/app/services/prompt_cache.py  模块级新增：
ADDITIONAL_DIAGRAM_PROMPTS: dict[str, str] = {
    "org_chart": (
        "请根据以下企业应急组织架构数据，生成一张 Mermaid graph TD 组织架构图：\n"
        "{{org_structure}}\n"
        "要求：\n"
        "1. 顶层为应急救援指挥部（总指挥），下面按小组分组展示。\n"
        "2. 每个节点标注姓名与职务，格式：节点ID[姓名-职务]。\n"
        "3. 节点文字使用中文，全角括号保留原样，不要使用半角括号。\n"
        "4. 图片放在单独的 ```mermaid 代码块中。"
    ),
    "report_sequence": (
        "请为本章节生成一张 Mermaid sequenceDiagram 信息上报时序图，描述事故发生后"
        "从发现人到总指挥、再到外部救援（119/120）的逐级报告顺序。\n"
        "要求：\n"
        "1. 参与者包括：发现人、值班人员、应急救援指挥部、总指挥、应急小组、外部救援。\n"
        "2. 消息包含七要素（时间、地点、单位、类型、伤亡、影响、措施）的传递要点。\n"
        "3. 使用中文消息文本，全角括号保留原样。\n"
        "4. 图片放在单独的 ```mermaid 代码块中。"
    ),
    "response_timeline": (
        "请为本章节生成一张 Mermaid timeline 应急处置时间轴，按时间顺序展示"
        "从事故发生到响应结束的关键节点。\n"
        "要求：\n"
        "1. 时间轴按 T+分钟 标注（如 T+0 发现、T+5 报告、T+15 启动响应）。\n"
        "2. 每个节点一句话概括动作。\n"
        "3. 使用中文，全角括号保留原样。\n"
        "4. 图片放在单独的 ```mermaid 代码块中。"
    ),
    "drill_gantt": (
        "请为本章节生成一张 Mermaid gantt 应急演练甘特图，展示年度演练计划安排。\n"
        "要求：\n"
        "1. 按季度/月份安排 4-6 项演练任务（综合演练、专项演练、桌面推演、现场处置演练）。\n"
        "2. 每项任务给出合理的日期区间。\n"
        "3. 使用中文，全角括号保留原样。\n"
        "4. 图片放在单独的 ```mermaid 代码块中。"
    ),
}


def get_additional_diagram_prompt(diagram_key: str) -> str | None:
    """返回附加图提示词模板（无则 None）。"""
    return ADDITIONAL_DIAGRAM_PROMPTS.get(diagram_key)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_prompts.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/prompt_cache.py backend/tests/test_plan_diagram_prompts.py
git commit -m "feat(plan): add additional diagram prompt templates (diagrams batch1)"
```

---

### 任务 3：org_structure → mermaid 文本构建 + 章节提示词注入

**文件：**
- 修改：`backend/app/routers/generation.py`（`_build_section_prompt`、新增 `_build_org_chart_mermaid`）
- 测试：`backend/tests/test_plan_diagram_prompts.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_diagram_prompts.py 追加
from app.routers.generation import _build_org_chart_mermaid


def test_build_org_chart_mermaid_from_structure():
    org = [
        {"group_name": "应急救援指挥部", "members": [
            {"name": "张三", "position": "总指挥", "phone": "138", "responsibilities": "全面指挥"},
        ]},
        {"group_name": "抢险救援组", "members": [
            {"name": "李四", "position": "组长", "phone": "139", "responsibilities": "灭火"},
        ]},
    ]
    md = _build_org_chart_mermaid(org)
    assert "graph TD" in md
    assert "张三-总指挥" in md
    assert "李四-组长" in md


def test_build_org_chart_mermaid_empty_returns_none():
    assert _build_org_chart_mermaid([]) is None
    assert _build_org_chart_mermaid([{"group_name": "空组", "members": []}]) is None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_prompts.py -v`
预期：FAIL，`ImportError: cannot import name '_build_org_chart_mermaid'`

- [ ] **步骤 3：实现组织架构 mermaid 构建**

```python
# backend/app/routers/generation.py  模块级新增：
def _build_org_chart_mermaid(org_structure: list) -> str | None:
    """企业组织架构 → Mermaid graph TD 文本；无有效数据返回 None。"""
    groups = [g for g in (org_structure or []) if g.get("members")]
    if not groups:
        return None
    lines = ["graph TD", "    HQ[应急救援指挥部]"]
    node_id = 1
    for g in groups:
        group_node = f"G{node_id}[{g.get('group_name','应急小组')}]"
        lines.append(f"    HQ --> {group_node}")
        node_id += 1
        for m in g.get("members", []):
            name = m.get("name", "")
            position = m.get("position", "")
            if not name:
                continue
            label = f"{name}-{position}" if position else name
            member_node = f"M{node_id}[{label}]"
            lines.append(f"    {group_node} --> {member_node}")
            node_id += 1
    return "\n".join(lines)
```

- [ ] **步骤 4：`_build_section_prompt` 注入附加图指令**

在 `_build_section_prompt` 中，mermaid 指令拼接后追加附加图指令：

```python
    # 附加图（组织架构图等）：注入提示词
    additional_key = SECTION_ADDITIONAL_DIAGRAM_MAP.get(section_key or "")
    if additional_key:
        tmpl = get_additional_diagram_prompt(additional_key)
        if tmpl:
            variables = {"org_structure": json.dumps(
                enterprise_data.get("org_structure", []), ensure_ascii=False
            )} if additional_key == "org_chart" else {}
            additional = render_template(tmpl, variables)
            prompt += "\n\n" + additional
```

`get_additional_diagram_prompt` 与 `render_template` 从 `app.services.prompt_cache` 导入（`get_additional_diagram_prompt` 需加入顶部导入）。

注：org_chart 的「真实数据 mermaid」由生成后处理绘制（第 2 批 `plan_diagram_service`）；本批提示词注入用于让 AI 在正文中给出文字依据，实际图渲染在批 2 接入。

- [ ] **步骤 5：运行测试验证通过**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/test_plan_diagram_prompts.py -v`
预期：PASS

- [ ] **步骤 6：全量回归**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过（182+ 基线）

- [ ] **步骤 7：Commit**

```bash
git add backend/app/routers/generation.py backend/tests/test_plan_diagram_prompts.py
git commit -m "feat(plan): inject additional diagram prompts into section generation (diagrams batch1)"
```

---

### 任务 4：第 1 批收尾验证

- [ ] **步骤 1：后端全量回归**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 2：规格对照自检**

- [x] §3.1 sec_3/sec_4_2/sec_5/sec_9_1 映射 → 任务 1
- [x] §6.2 org_chart 提示词 → 任务 2
- [x] §6.3 生成流程注入 → 任务 3
- [x] org_structure 数据依据 → 任务 3（`_build_org_chart_mermaid`）

- [ ] **步骤 3：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): diagrams batch1 final verification"
```
