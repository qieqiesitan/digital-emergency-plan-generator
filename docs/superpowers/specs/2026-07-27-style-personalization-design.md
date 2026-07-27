<!--
  文档元信息
  创建日期: 2026-07-27
  作者: Codex
  版本: 1.0
  状态: 待审查
  依赖: PRD-04(AI生成引擎), PRD-M06(移动端AI生成体验)
-->

# AI 生成风格个性化 — 完整设计方案

## 1. 概述

### 1.1 背景

当前系统所有用户共用同一套 AI 提示词模板，生成的应急预案风格单一。不同企业用户对预案文本的正式程度、详略程度、表格使用频率、流程图需求各有偏好。本方案引入**半自定义风格系统**：80% 用户通过开关式风格面板调整参数，20% 高级用户可直接编辑底层提示词。

### 1.2 核心设计原则

- **三段式 System Prompt**：拆分为角色指令（不可变）、风格指令（面板控制）、合规底线（不可变）
- **风格挂在项目上**：每个预案项目独立保存风格参数，默认继承用户偏好
- **面板与高级模式互斥**：选一种控制方式，避免指令冲突
- **向后兼容**：已有预案无风格参数 → 自动使用"标准"风格（等同于当前默认行为）

### 1.3 用户故事速览

**场景 A — 普通用户**：在预案编辑页看到一个"创作风格"面板（四个选项），勾选即生效，不需要写任何提示词。

**场景 B — 高级用户**：在风格面板切换"高级模式"，直接编辑 system prompt 和逐章节的章节 prompt。

**场景 C — 多企业切换**：同一个用户给 A 企业和 B 企业做预案，两个项目各自保存独立风格，互不影响。

---

## 2. 数据模型变更

### 2.1 PlanProject 表新增字段

```sql
ALTER TABLE plan_projects ADD COLUMN style_preference JSONB;
ALTER TABLE plan_projects ADD COLUMN advanced_prompt_overrides JSONB;
```

**style_preference** 结构（标准模式）：

```json
{
  "formality": "standard",
  "detail_level": "balanced",
  "table_preference": "moderate",
  "diagram_preference": "mermaid",
  "mode": "panel"
}
```

字段说明：

| 字段 | 类型 | 可选值 | 默认值 | 含义 |
|------|------|--------|--------|------|
| `formality` | enum | `formal` / `standard` / `practical` | `standard` | 正式程度 |
| `detail_level` | enum | `concise` / `balanced` / `comprehensive` | `balanced` | 详略程度 |
| `table_preference` | enum | `minimal` / `moderate` / `heavy` | `moderate` | 表格使用倾向 |
| `diagram_preference` | enum | `none` / `mermaid` | `mermaid` | 是否生成 Mermaid 流程图 |
| `mode` | enum | `panel` / `advanced` | `panel` | 普通面板模式/高级模式 |

**advanced_prompt_overrides** 结构（高级模式）：

```json
{
  "system_prompt_override": "你是一位...（用户自定义全文）",
  "section_overrides": {
    "sec_2": "请用清单体写作，一级标题用中文数字...(仅覆盖此章节的user_prompt)"
  }
}
```

### 2.2 User 表新增字段

```sql
ALTER TABLE users ADD COLUMN default_style_preference JSONB;
```

结构同 `style_preference`，无 `mode` 字段。创建新预案时自动复制到 `PlanProject.style_preference`。

### 2.3 SQLAlchemy 模型映射

```python
# enterprise.py — PlanProject 新增
from sqlalchemy.dialects.postgresql import JSONB

class PlanProject(Base):
    # ... 已有字段 ...
    style_preference: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    advanced_prompt_overrides: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
```

---

## 3. System Prompt 三段式重构

### 3.1 当前问题

`prompt_cache.py` 中的 `FALLBACK_SYSTEM_PROMPT`（178行）将角色定义、风格要求、术语标准、格式规则混在一起。面板无法安全替换中间块。

### 3.2 重构后结构

```
┌─────────────────────────────────┐
│ ROLE_BLOCK                      │  ← 永远不变
│ "你是国家注册安全工程师..."       │
├─────────────────────────────────┤
│ STYLE_BLOCK                     │  ← 面板控制/DB模板/fallback
│ 默认: "使用正式公文语体..."       │
│ 面板选"practical": 被翻译文本替换 │
│ 高级模式: 用户自定义文本替换      │
├─────────────────────────────────┤
│ COMPLIANCE_BLOCK                │  ← 永远不变
│ "术语标准: 救援指挥部..."        │
└─────────────────────────────────┘
```

### 3.3 代码实现（prompt_cache.py 新增）

```python
# ── 三段式组件 ──

ROLE_BLOCK = (
    "你是一位持有国家注册安全工程师资格的应急预案编制专家，"
    "具有丰富的生产经营单位应急预案编制经验。"
    "你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，"
    "并严格遵循相关法律法规。"
)

STYLE_DEFAULTS = {
    "standard": (
        "【写作风格】\n"
        "使用正式公文语体，语言严谨、客观、准确、简洁。\n"
        "避免口语化表达、修辞性语言、主观评论。\n"
        "句式以短句为主，主语明确，逻辑清晰。\n"
    ),
}

COMPLIANCE_BLOCK = (
    "【术语与结构底线——必须严格遵守】\n"
    "1. 应急组织统一使用：应急救援指挥部、总指挥、副总指挥...\n"
    "2. 响应级别统一表述为 III级/II级/I级响应。\n"
    "3. 信息报告必须包含七要素。\n"
    "4. 章节必须包含 GB/T 29639 规定的必备要素。"
)


def build_system_prompt_with_style(
    plan_type: str = "*",
    style_preference: dict | None = None,
    advanced_overrides: dict | None = None,
) -> str:
    """构建三段式 System Prompt，支持风格参数注入。"""

    # 1. 角色指令（永远第一段）
    parts = [ROLE_BLOCK]

    # 2. 风格指令
    if advanced_overrides and advanced_overrides.get("system_prompt_override"):
        return advanced_overrides["system_prompt_override"]

    style_text = (
        generate_style_instruction(style_preference)
        if style_preference
        else STYLE_DEFAULTS["standard"]
    )
    parts.append(style_text)

    # 3. 合规底线
    parts.append(COMPLIANCE_BLOCK)

    return "\n\n".join(parts)
```

**向后兼容**：`get_system_prompt()` 不修改签名，内部改为调用 `build_system_prompt_with_style(plan_type)`（无风格参数 → 标准默认）。所有已有调用点零破坏。

---

## 4. 风格参数翻译引擎

### 4.1 纯函数

```python
# prompt_cache.py 新增

STYLE_PARAM_MAP: dict[str, dict[str, str]] = {
    "formality": {
        "formal": (
            "使用正式的政府公文语体，语言严谨、客观、准确、简洁。"
            "高频动词：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查。"
            '禁止使用"应该""大概""也许"等不确定词汇。'
        ),
        "standard": (
            "使用规范的公文语体，语言严谨、客观、准确。"
            "以陈述句为主，避免主观评论和口语化表达。"
        ),
        "practical": (
            "使用实用简洁的工程文体，直接陈述事实和措施。"
            "避免冗余修饰和套话，以动词开头的短句为主。"
            "可以使用条目式、清单式表达。"
        ),
    },
    "detail_level": {
        "concise": "正文力求简洁，每个要点控制在 2-3 句话以内，只写关键信息。",
        "balanced": "正文详略得当，关键内容充分展开，非关键内容点到为止。",
        "comprehensive": "正文详尽展开，每个要点充分论述，提供具体说明和示例。",
    },
    "table_preference": {
        "minimal": "尽量不用表格，用文字段落描述数据关系。",
        "moderate": "在适合的场景使用表格呈现结构化数据，但不过度依赖。",
        "heavy": "优先使用表格呈现数据和流程，通过表格组织对照关系和清单。",
    },
    "diagram_preference": {
        "none": "不生成 Mermaid 流程图，用文字描述流程即可。",
        "mermaid": "在描述流程的章节末尾插入 mermaid 流程图，用图形辅助理解。",
    },
}


def generate_style_instruction(style_preference: dict) -> str:
    """将风格参数翻译为自然语言注入指令。"""
    lines = ["【风格偏好——请严格遵循以下写作风格】"]

    for param, value in style_preference.items():
        if param == "mode":
            continue
        text = STYLE_PARAM_MAP.get(param, {}).get(value, "")
        if text:
            lines.append(f"- {text}")

    return "\n".join(lines)
```

### 4.2 翻译效果示例

用户选择：`formality=practical, detail_level=concise, table_preference=moderate, diagram_preference=none`

实际生成注入文本：

```
【风格偏好——请严格遵循以下写作风格】
- 使用实用简洁的工程文体，直接陈述事实和措施。避免冗余修饰和套话，以动词开头的短句为主。可以使用条目式、清单式表达。
- 正文力求简洁，每个要点控制在 2-3 句话以内，只写关键信息。
- 在适合的场景使用表格呈现结构化数据，但不过度依赖。
- 不生成 Mermaid 流程图，用文字描述流程即可。
```

---

## 5. 生成流程变更

### 5.1 应急预案生成（generation.py）

**当前流程**：

```
用户触发 → 读 AIConfig → _build_section_prompt(从缓存读模板) → 调 LLM
```

**变更后流程**：

```
用户触发 → 读 AIConfig
         → 读 PlanProject.style_preference / advanced_prompt_overrides
         → _build_system_prompt_with_style(style_preference, advanced_overrides)
         → _build_section_prompt(从缓存读模板)
           如果 diagram_preference == "none" → 跳过 Mermaid 指令
         → 保留 custom_instruction 作为一次性追加
         → 调 LLM
```

**具体改动**：

1. `generation.py` 的 `_stream_llm_chunks`、`_stream_llm`、`generate_section`、`generate_batch`、`generate_batch_background` —— 所有调用 `_build_system_prompt` 的地方，改为传入 `p.style_preference` 和 `p.advanced_prompt_overrides`

2. `_build_section_prompt` 增加 `diagram_preference` 参数，传给 `_get_mermaid_instruction` 做判断

3. `_get_mermaid_instruction` 增加开关逻辑：

   ```python
   def _get_mermaid_instruction(section_key, section_title, diagram_preference="mermaid"):
       if diagram_preference == "none":
           return None  # 不生成流程图
       # ... 原有逻辑 ...
   ```

4. `regenerate_selection` 端点同样传递风格参数

### 5.2 风险评估报告生成（risk_assessment_service.py）

当前 `build_chapter_prompt` 从缓存读取模板，不涉及风格参数。报告生成 API 端点需要从 `PlanProject`（或从请求参数）获取风格配置，注入 system prompt。

### 5.3 应急资源调查报告生成（resource_investigation_service.py）

同上，需要风格注入。

### 5.4 chat.py 聊天助手

**不受影响**。聊天助手的 system prompt 是操作导向的（控制 CRUD），风格参数对聊天无意义。

---

## 6. API 变更

### 6.1 生成 API（无需前端传参）

所有生成端点内部自动从 `PlanProject` 读取风格参数，**前端无需额外传参**。`custom_instruction` 参数保留不变。

### 6.2 预案 CRUD 扩展

`PUT /api/v1/plans/{plan_id}` 请求体扩展：

```json
{
  "title": "xxx",
  "style_preference": {
    "formality": "practical",
    "detail_level": "concise",
    "table_preference": "moderate",
    "diagram_preference": "none",
    "mode": "panel"
  },
  "advanced_prompt_overrides": null
}
```

`GET /api/v1/plans/{plan_id}` 响应体同步扩展。

### 6.3 用户默认风格 API（新增）

```
GET  /api/v1/users/me/style-preference    → 返回用户默认风格
PUT  /api/v1/users/me/style-preference    → 更新用户默认风格
```

请求/响应体结构同 `style_preference`（不含 `mode` 字段）。

### 6.4 风格预览 API（新增，轻量）

```
POST /api/v1/plans/{plan_id}/generate/preview
```

请求体：`{ "section_key": "sec_1", "max_tokens": 300 }`

行为：用当前项目的风格参数生成一个短预览，SSE 流式返回，不落库。

---

## 7. 前端变更

### 7.1 Web 端 — 预案编辑器新增风格面板

**位置**：预案编辑器页面顶部，AI 生成按钮旁边区域。

**面板布局（标准模式）**：

```
┌─── 创作风格 ───────────────────────────────┐
│                                             │
│ 正式程度  ○ 正式  ● 标准  ○ 实用            │
│ 详略程度  ○ 简短  ● 适中  ○ 详尽            │
│ 表格使用  ○ 少用  ● 按需  ○ 多用            │
│ 流程图    ● 生成  ○ 不生成                   │
│                                             │
│              [ 预览一段 ]  [ 重置默认 ]      │
│                          [ 高级模式 → ]      │
└─────────────────────────────────────────────┘
```

**交互细节**：
- 切换选项后自动保存（debounce 500ms → `PUT /plans/{id}`）
- 点击"预览一段" → 调 preview API，SSE 输出 200-300 字预览在弹层中
- 点击"高级模式" → 面板切换为下文高级模式视图

**面板布局（高级模式）**：

```
┌─── 创作风格（高级模式）── [退出高级模式] ─────┐
│                                                │
│ ── 系统角色指令 ──                             │
│ ┌────────────────────────────────────────────┐ │
│ │ [可编辑的 textarea，内容为当前完整          │ │
│ │  system_prompt]                            │ │
│ │                               [恢复默认]   │ │
│ └────────────────────────────────────────────┘ │
│                                                │
│ ── 各章节个性化指令 ──                         │
│ 总则                  [使用默认]                │
│ 事故风险描述          [自定义 ✓]                │
│ 应急组织机构          [使用默认]                │
│ ...                                           │
└───────────────────────────────────────────────┘
```

### 7.2 移动端 — 与 Web 端统一

移动端 PRD-M06 已设计"生成风格" 3 项 SegmentedControl（标准化/详细/简洁），需改造为与 Web 端一致的 4 参数风格面板。风格数据从 `PlanProject.style_preference` 读取。

移动端不做高级模式（高级模式面向桌面端专业用户）。

### 7.3 系统设置 — 用户默认风格

在系统设置页新增"默认创作风格"区域，选项与预案编辑器风格面板一致。此处设置的风格将在创建新预案时自动带入。

---

## 8. 兼容与迁移

### 8.1 向后兼容

- `PlanProject.style_preference` 为 `NULL` → 自动使用标准风格 `{"formality":"standard","detail_level":"balanced","table_preference":"moderate","diagram_preference":"mermaid","mode":"panel"}`，等同于当前默认行为
- `get_system_prompt()` 原签名不变，内部改为调 `build_system_prompt_with_style(plan_type)` 无参版本
- 所有已有 API 调用、chat 聊天助手、报告生成不受影响

### 8.2 数据库迁移

```sql
ALTER TABLE plan_projects ADD COLUMN IF NOT EXISTS style_preference JSONB;
ALTER TABLE plan_projects ADD COLUMN IF NOT EXISTS advanced_prompt_overrides JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_style_preference JSONB;
```

已有行默认为 `NULL`，运行时 fallback 到标准风格。无需批量回填。

---

## 9. 受影响文件清单

| 文件 | 变更类型 | 变更说明 |
|------|---------|---------|
| `backend/app/models/enterprise.py` | 修改 | PlanProject 新增 style_preference, advanced_prompt_overrides |
| `backend/app/models/user.py` | 修改 | User 新增 default_style_preference |
| `backend/app/services/prompt_cache.py` | 重构 | 三段式拆分；新增 build_system_prompt_with_style()、generate_style_instruction()、STYLE_PARAM_MAP |
| `backend/app/routers/generation.py` | 修改 | 风格注入 + Mermaid 开关 + preview 端点 |
| `backend/app/services/risk_assessment_service.py` | 修改 | 风格参数注入 |
| `backend/app/services/resource_investigation_service.py` | 修改 | 风格参数注入 |
| `backend/app/routers/plans.py` | 修改 | PUT/GET 支持新字段 |
| `backend/app/routers/users.py` | 修改 | 新增 style-preference 端点 |
| `backend/app/schemas/plan.py` | 修改 | Schema 增加 style_preference, advanced_prompt_overrides |
| `frontend/src/pages/Plan/PlanEditorPage.tsx` | 修改 | 集成风格面板 |
| （新建）`frontend/src/components/plan/StylePanel.tsx` | 新建 | 标准模式风格面板 |
| （新建）`frontend/src/components/plan/AdvancedStylePanel.tsx` | 新建 | 高级模式面板 |
| `frontend/src/mobile/components/plan/AIGenerationSheet.tsx` | 修改 | 改造为 4 参数风格面板 |
| `prd/PRD-04-AI生成引擎.md` | 修改 | 补充风格个性化章节 |
| `prd/PRD-M06-移动端AI生成体验.md` | 修改 | 更新生成风格为 4 参数 |

### （不变更的文件）

| 文件 | 原因 |
|------|------|
| `backend/app/routers/prompts.py` | 全局提示词模板 CRUD 保持不动 |
| `backend/app/models/prompt.py` | PromptTemplate 表结构不变 |
| `backend/app/routers/chat.py` | 聊天助手不受影响 |
| `backend/app/services/chat_dispatch.py` | 同上 |
| `backend/app/routers/export.py` | DOCX 导出不受影响 |
| `backend/app/services/docx_template.py` | 同上 |
| `backend/app/regulations/` | 法规模块不变 |

---

## 10. 实施顺序

| 阶段 | 任务 | 估算 | 依赖 |
|------|------|------|------|
| **Phase 1A** | System Prompt 三段式重构 + prompt_cache.py 新增翻译函数 | 0.5d | — |
| **Phase 1B** | 数据模型变更（plan_projects + users）+ Alembic 迁移 | 0.5d | — |
| **Phase 1C** | generation.py 风格注入 + Mermaid 开关 + preview 端点 | 1d | 1A, 1B |
| **Phase 1D** | plans.py / users.py / schemas 扩展 | 0.5d | 1B |
| **Phase 1E** | Web 端风格面板组件开发 + 集成 | 2d | 1C, 1D |
| **Phase 1F** | 移动端 AIGenerationSheet 改造 | 1d | 1C |
| **Phase 1G** | 风险评估 + 资源调查报告风格注入 | 0.5d | 1A |
| **Phase 1H** | 集成测试 + 回归测试 | 1d | 全部 |
| **合计** | | **7d** | |

---

## 11. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC-S01 | System Prompt 三段式可独立编排 | 自动化：build_system_prompt_with_style({formality:"practical"}) → 含 ROLE+翻译+COMPLIANCE |
| AC-S02 | 风格面板选择不同参数生成效果不同 | E2E：选 formal → 正式；选 practical → 简洁；对比有显著差异 |
| AC-S03 | 高级模式自定义 system_prompt 覆盖默认 | E2E：写入特定指令 → 生成体现该指令 |
| AC-S04 | 面板和高级模式互斥 | 自动化：同时设 panel 和 overrides → 面板生效 |
| AC-S05 | 旧预案无 style_preference → 标准风格 | 自动化：NULL → 行为等同当前系统 |
| AC-S06 | 不同项目风格参数独立 | E2E：项目A formal / 项目B practical → 独立生效 |
| AC-S07 | 新建预案继承用户默认风格 | E2E：用户默认 practical → 新建项目 style_preference 继承 |
| AC-S08 | diagram_preference=none 时不输出流程图 | 自动化：含 flowchart 章节无 mermaid 代码块 |
| AC-S09 | custom_instruction 保留且优先追加 | 自动化：custom_instruction 内容在生成结果中体现 |
| AC-S10 | 预览端点返回受限片段 | 自动化：preview 端点 tokens ≤ max_tokens |
| AC-S11 | 风险评估和资源调查报告受风格影响 | E2E：改参数 → 报告详略/正式度变化 |
| AC-S12 | 迁移后现有功能不受影响 | 自动化：运行迁移 → 现有测试套件全绿 |
| AC-S13 | 移动端支持 4 参数风格选择 | E2E：移动端选参数 → 生成符合预期 |
| AC-S14 | 聊天助手不受风格参数影响 | 自动化：修改参数 → 聊天行为不变 |
