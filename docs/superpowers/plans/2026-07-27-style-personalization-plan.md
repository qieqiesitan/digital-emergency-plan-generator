# AI 生成风格个性化 实现计划

> **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development（推荐）逐任务实现。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 引入半自定义 AI 生成风格系统——用户通过风格面板（4 个参数）或高级模式（直接编辑 prompt）控制应急预案生成的文本风格

**架构：** System Prompt 拆分为 ROLE/STYLE/COMPLIANCE 三段式；风格参数存入 `plan_projects.style_preference` JSONB 列；`prompt_cache.py` 新增翻译引擎；`generation.py` 读取项目风格参数传入 LLM 调用

**技术栈：** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL JSONB + React/TypeScript（前端）+ React Native（移动端）

**规格文档：** `docs/superpowers/specs/2026-07-27-style-personalization-design.md`

---

## 多智能体分批策略

本计划支持 4 批执行：

| 批次 | 任务 | 并行数 | 依赖 |
|------|------|:---:|------|
| 第 1 批 | 任务1(数据模型) + 任务2(prompt_cache) | 2 | — |
| 第 2 批 | 任务3(generation.py) + 任务4(API+schema) | 2 | 第1批 |
| 第 3 批 | 任务5(Web) + 任务6(移动端) + 任务7(报告) | 3 | 第2批 |
| 收尾 | 任务8(集成测试) | 1 | 第3批 |

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|:--:|------|
| `backend/app/models/enterprise.py` | 修改 | PlanProject 新增 style_preference, advanced_prompt_overrides |
| `backend/app/models/user.py` | 修改 | User 新增 default_style_preference |
| `backend/app/services/prompt_cache.py` | 重构 | 三段式拆分 + 翻译引擎 + build_system_prompt_with_style() |
| `backend/app/routers/generation.py` | 修改 | 注入风格参数 + Mermaid 开关 + preview 端点 |
| `backend/app/routers/plans.py` | 修改 | PUT/GET 支持新字段；创建时继承用户默认风格 |
| `backend/app/routers/users.py` | 修改 | 新增 GET/PUT /users/me/style-preference |
| `backend/app/schemas/plan.py` | 修改 | Schema 增加 style_preference, advanced_prompt_overrides |
| `backend/app/services/risk_assessment_service.py` | 修改 | 风格注入 |
| `backend/app/services/resource_investigation_service.py` | 修改 | 风格注入 |
| `backend/db_migration_add_style_preference.sql` | 新建 | DDL 迁移 |
| `frontend/src/components/plan/StylePanel.tsx` | 新建 | Web 端标准模式风格面板 |
| `frontend/src/components/plan/AdvancedStylePanel.tsx` | 新建 | Web 端高级模式面板 |
| `frontend/src/pages/Plan/PlanEditorPage.tsx` | 修改 | 集成风格面板 |
| `frontend/src/mobile/components/plan/AIGenerationSheet.tsx` | 修改 | 改造为 4 参数风格面板 |

---

## 任务 1：数据模型变更

**文件：** `backend/app/models/enterprise.py`, `backend/app/models/user.py`, `backend/db_migration_add_style_preference.sql`

**子智能体任务：**

1. 在 `backend/app/models/enterprise.py` 的 PlanProject 类中，在 updated_at 字段之后、relationship 之前，添加：
```python
style_preference: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
advanced_prompt_overrides: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
```
确认文件顶部已 `from sqlalchemy.dialects.postgresql import JSONB`。

2. 在 `backend/app/models/user.py` 的 User 类中，已有字段之后添加：
```python
default_style_preference: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
```

3. 新建 `backend/db_migration_add_style_preference.sql`：
```sql
ALTER TABLE plan_projects ADD COLUMN IF NOT EXISTS style_preference JSONB;
ALTER TABLE plan_projects ADD COLUMN IF NOT EXISTS advanced_prompt_overrides JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_style_preference JSONB;
```

4. 验证：
```bash
cd backend && python -c "from app.models.enterprise import PlanProject; [c.name for c in PlanProject.__table__.columns if 'style' in c.name or 'advanced' in c.name]"
cd backend && python -c "from app.models.user import User; [c.name for c in User.__table__.columns if 'style' in c.name or 'default' in c.name]"
```
预期输出列出新增列名。

5. Commit: `feat: add style_preference/advanced_prompt_overrides to PlanProject, default_style_preference to User`

---

## 任务 2：prompt_cache.py 重构

**文件：** `backend/app/services/prompt_cache.py`

**子智能体任务：**

1. 在 FALLBACK_SYSTEM_PROMPT 定义之后（保留不动），添加三段式常量：

```python
ROLE_BLOCK = "你是一位持有国家注册安全工程师资格的应急预案编制专家，具有丰富的生产经营单位应急预案编制经验。你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，并严格遵循相关法律法规。"

STYLE_BLOCK_DEFAULT = (
    "【写作风格——必须严格遵守】\n"
    "一、公文语体要求\n"
    "1. 使用正式的政府公文语体，语言严谨、客观、准确、简洁。\n"
    "2. 高频动词：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查。\n"
    "3. 避免口语化表达、修辞性语言、主观评论。不使用"应该""大概""也许"等不确定词汇。\n"
    "4. 句式以短句为主，主语明确，逻辑清晰。\n"
    "5. 开篇应引用法律法规依据。\n\n"
    "二、结构范式\n"
    "综合应急预案：总则→事故风险描述→应急组织机构及职责→预警及信息报告→应急响应→信息公开→后期处置→保障措施→应急预案管理\n"
    "专项应急预案：事故风险分析→应急指挥机构及职责→处置程序与措施→应急保障\n"
    "现场处置方案：事故风险分析→应急工作职责→应急处置→注意事项"
)

COMPLIANCE_BLOCK = (
    "【术语标准与结构底线——必须严格遵守】\n"
    "1. 应急组织统一用：应急救援指挥部、总指挥、副总指挥、应急救援小组、抢险救援组、疏散引导组、医疗救护组、通讯联络组、后勤保障组、警戒疏散组。\n"
    "2. 响应级别统一表述为III级/II级/I级响应。\n"
    "3. 信息报告必须包含七要素。\n"
    "4. 请直接输出章节正文内容，不要重复章节标题。"
)
```

2. 添加风格翻译表：
```python
STYLE_PARAM_MAP: dict[str, dict[str, str]] = {
    "formality": {
        "formal": "使用正式的政府公文语体，语言严谨、客观、准确、简洁。高频动词：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查。禁止使用"应该""大概""也许"等不确定词汇。",
        "standard": "使用规范的公文语体，语言严谨、客观、准确。以陈述句为主，避免主观评论和口语化表达。",
        "practical": "使用实用简洁的工程文体，直接陈述事实和措施。避免冗余修饰和套话，以动词开头的短句为主。可以使用条目式、清单式表达。",
    },
    "detail_level": {
        "concise": "正文力求简洁，每个要点控制在2-3句话以内，只写关键信息。",
        "balanced": "正文详略得当，关键内容充分展开，非关键内容点到为止。",
        "comprehensive": "正文详尽展开，每个要点充分论述，提供具体说明和示例。",
    },
    "table_preference": {
        "minimal": "尽量不用表格，用文字段落描述数据关系。",
        "moderate": "在适合的场景使用表格呈现结构化数据，但不过度依赖。",
        "heavy": "优先使用表格呈现数据和流程，通过表格组织对照关系和清单。",
    },
    "diagram_preference": {
        "none": "不生成Mermaid流程图，用文字描述流程即可。",
        "mermaid": "在描述流程的章节末尾插入mermaid流程图，用图形辅助理解。",
    },
}
```

3. 添加翻译函数：
```python
def generate_style_instruction(style_preference: dict | None) -> str:
    if not style_preference:
        return "【写作风格——请严格遵循】\n" + STYLE_BLOCK_DEFAULT
    lines = ["【风格偏好——请严格遵循以下写作风格】"]
    for param, value in style_preference.items():
        if param in ("mode",):
            continue
        text = STYLE_PARAM_MAP.get(param, {}).get(value, "")
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if len(lines) > 1 else "【写作风格——请严格遵循】\n" + STYLE_BLOCK_DEFAULT
```

4. 添加三段式构建函数：
```python
def build_system_prompt_with_style(plan_type="*", style_preference=None, advanced_overrides=None):
    if advanced_overrides and advanced_overrides.get("system_prompt_override"):
        return advanced_overrides["system_prompt_override"]
    parts = [ROLE_BLOCK, generate_style_instruction(style_preference), COMPLIANCE_BLOCK]
    return "\n\n".join(parts)
```

5. 修改 get_system_prompt()：保留原有数据库查询逻辑，在最后 fallback 时改为调用 `build_system_prompt_with_style(plan_type)`。

6. 验证：
```bash
cd backend && python -c "
from app.services.prompt_cache import ROLE_BLOCK, STYLE_BLOCK_DEFAULT, COMPLIANCE_BLOCK, STYLE_PARAM_MAP, generate_style_instruction, build_system_prompt_with_style, get_system_prompt
print('=== Test: None style (default) ==='); print(build_system_prompt_with_style()[:200])
sp={'formality':'practical','detail_level':'concise','table_preference':'minimal','diagram_preference':'none'}
print(); print('=== Test: Style instruction ==='); print(generate_style_instruction(sp))
print(); print('=== Test: Advanced override ==='); print(build_system_prompt_with_style(advanced_overrides={'system_prompt_override':'Custom prompt.'}))
print(); print('=== Test: Backward compat ==='); print(get_system_prompt()[:200])
print(); print('ALL TESTS PASSED')
"
```

7. Commit: `refactor: split FALLBACK_SYSTEM_PROMPT into ROLE/STYLE/COMPLIANCE; add style translation engine`

---

## 任务 3：generation.py 风格注入

**文件：** `backend/app/routers/generation.py`

**子智能体任务：**

1. 将 import 中增加 `build_system_prompt_with_style`：
```python
from app.services.prompt_cache import (..., build_system_prompt_with_style, ...)
```

2. 修改 `_build_system_prompt` 函数：
```python
def _build_system_prompt(plan_type="*", style_preference=None, advanced_overrides=None):
    return build_system_prompt_with_style(plan_type, style_preference, advanced_overrides)
```

3. 在 `_get_mermaid_instruction` 函数开头增加开关：
```python
def _get_mermaid_instruction(section_key, section_title, diagram_preference="mermaid"):
    if diagram_preference == "none":
        return None
    # ... 已有逻辑保持不变 ...
```

4. `_build_section_prompt` 增加 `diagram_preference="mermaid"` 参数，传给 `_get_mermaid_instruction`。

5. `_stream_llm_chunks` 和 `_stream_llm` 增加 `style_preference=None, advanced_overrides=None` 参数，在构建 messages 时传入 `_build_system_prompt`。

6. `generate_section`：从 `p.style_preference` 读取 `diagram_preference`，传给 `_build_section_prompt` 和 `_stream_llm_chunks`。

7. `generate_batch`、`generate_batch_background`：同上处理。

8. `regenerate_selection`：`_stream_llm_chunks` 调用增加风格参数。

9. 新增 `PreviewRequest` Schema 和 `POST /{plan_id}/generate/preview` 端点（限制 300 tokens 预览，不落库）。

10. 验证: `cd backend && python -c "from app.routers.generation import router, PreviewRequest; print('OK')"`

11. Commit: `feat: inject style_preference into generation pipeline; add preview endpoint`

---

## 任务 4：API Schema 扩展

**文件：** `backend/app/schemas/plan.py`, `backend/app/routers/plans.py`, `backend/app/routers/users.py`

**子智能体任务：**

1. schemas/plan.py: PlanCreate/PlanUpdate/PlanResponse 各增加 `style_preference: Optional[dict] = None` 和 `advanced_prompt_overrides: Optional[dict] = None`

2. routers/plans.py — POST 创建预案：读取 `current_user.default_style_preference`，`body.style_preference` 优先否则继承用户默认

3. routers/plans.py — PUT 更新预案：增加 `.style_preference` 和 `.advanced_prompt_overrides` 的 setattr

4. routers/plans.py — GET 响应：增加两个新字段

5. routers/users.py — 新增 GET/PUT `/users/me/style-preference` 端点，Schema 为 `{formality, detail_level, table_preference, diagram_preference}`

6. 验证: `cd backend && python -c "from app.routers.users import StylePreferenceUpdate; print('OK')"`

7. Commit: `feat: add style_preference to plan CRUD; add user style-preference endpoints`

---

## 任务 5：Web 端风格面板

**文件：** 新建 `frontend/src/components/plan/StylePanel.tsx`, `frontend/src/components/plan/AdvancedStylePanel.tsx`；修改 `frontend/src/pages/Plan/PlanEditorPage.tsx`

**子智能体任务：**

1. StylePanel.tsx：4 个 SegmentedControl（formality/detail_level/table_preference/diagram_preference），"预览一段"按钮，"重置默认"按钮，"高级模式→"按钮

2. AdvancedStylePanel.tsx：textarea 编辑完整 system_prompt（带"恢复默认"按钮），逐章节自定义指令入口

3. 集成到 PlanEditorPage.tsx：在生成按钮上方渲染风格面板，切换参数时 debounce 500ms 调 PUT API 保存

4. 验证: `cd frontend && npx tsc --noEmit` 零错误

5. Commit: `feat: add StylePanel and AdvancedStylePanel`

---

## 任务 6：移动端改造

**文件：** `frontend/src/mobile/components/plan/AIGenerationSheet.tsx`

**子智能体任务：**

1. 阅读当前文件，将"生成风格" 3 项 SegmentedControl 替换为 4 参数风格面板（formality/detail_level/table_preference/diagram_preference）

2. 参数传给 generation API 调用

3. 验证: `cd frontend && npx tsc --noEmit` 零错误

4. Commit: `feat: upgrade mobile AI generation to 4-parameter style panel`

---

## 任务 7：报告风格注入

**文件：** `backend/app/services/risk_assessment_service.py`, `backend/app/services/resource_investigation_service.py`

**子智能体任务：**

1. 阅读两个文件，在 system prompt 构建处（build_chapter_prompt 等）注入风格参数

2. 调用 `build_system_prompt_with_style` 替换硬编码的 SYSTEM_PROMPT 变量

3. 验证: `cd backend && python -c "from app.services.risk_assessment_service import build_chapter_prompt; from app.services.resource_investigation_service import build_resource_investigation_context; print('OK')"`

4. Commit: `feat: inject style into risk assessment and resource investigation reports`

---

## 任务 8：集成测试

**子智能体任务：**

1. 执行数据库迁移脚本
2. `cd backend && python -m pytest tests/ -v` 全绿
3. `cd frontend && npx tsc --noEmit` 零错误
4. Docker 重启验证
5. 手动验证：创建预案→选风格→生成→内容符合预期

6. Commit: `test: integration tests pass for style personalization`
