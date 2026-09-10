# 报告工作台（风险评估 / 应急资源调查）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让风险评估报告与应急资源调查报告获得与预案一致的「章节化文档工作台」：富文本编辑、单章生成/重生成、AI 审查修订、创作风格、章节保存；两报告共用一套前端组件（ReportWorkspace + ReportAdapter + TiptapEditor），后端补齐章节级接口。

**架构：** 后端把单章生成从全量循环中抽出独立端点并新增章节保存/审查/风格端点，风格偏好存报告表 `style_preference` 列；前端把预案 RichTextEditor 的编辑器内核抽成 `TiptapEditor`（预案对外行为不变），新建 `ReportWorkspace` 编排 + 每个报告一个 `ReportAdapter`，两个 Tab 变薄壳。

**技术栈：** FastAPI + SQLAlchemy(async) + SSE（sse_starlette）、python-docx（已有）；React 19 + antd + TipTap + markdown-it + vitest；docker（backend 8000 / frontend 5173 / shuzihuayuan 8082）为运行验证环境。

**执行约定：**
- 后端源码与测试：宿主编译后通过 `docker exec -w /app emergency-plan-backend python -m pytest ...` 运行（`/app/app` 为 bind mount，测试文件需 `docker cp` 进 `/app/tests`）。
- 前端测试：`docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run <file>"`；类型检查 `node node_modules/typescript/bin/tsc -b`（frontend 目录）。
- 每次后端代码改动后需 `docker restart emergency-plan-backend` 才生效（bind mount 无热载）；前端 dev(5173) 热更新，8082 需重建 dist 并 `docker cp`。
- Commit 只 add 本计划文件/本功能文件，TASKS.md 与既有他人未提交文件不 add。

---

## 文件结构

**后端（创建）**
- `backend/db_migration_20260903_report_workspace.sql`：两个报告表加 `style_preference JSONB NOT NULL DEFAULT '{}'`（幂等）。
- `backend/app/services/report_review_service.py`：报告章节规则审查 + 章节内容工具函数。
- `backend/tests/test_report_review_service.py`：审查规则单测。
- `backend/tests/test_report_chapter_storage.py`：summary.chapters 更新工具单测。

**后端（修改）**
- `backend/app/models/report_base.py`：加 `style_preference` 列（RiskAssessmentReport / ResourceInvestigationReport 继承共享）。
- `backend/app/routers/risk_assessment.py`：新增单章生成/重生成、章节保存、审查、风格端点。
- `backend/app/routers/resource_investigation.py`：同上（对称）。
- `backend/app/services/risk_assessment_service.py`：`build_chapter_prompt` 支持 `style_preference` 注入。
- `backend/app/services/resource_investigation_service.py`：同上（对称）。
- `backend/app/routers/report_versions.py` 或 main.py：如需在详情返回 style，随任务调整（默认不动）。

**前端（创建）**
- `frontend/src/components/report/TiptapEditor.tsx`：从预案 RichTextEditor 抽出的编辑器内核。
- `frontend/src/components/report/ReportWorkspace.tsx`：通用工作台。
- `frontend/src/components/report/ReportChapterActions.tsx`：单章生成/重写按钮（交互仿预案 AIGenerateButton）。
- `frontend/src/components/report/ReviewDrawer.tsx`：审查面板（复用 DiffPreviewModal）。
- `frontend/src/services/reportAdapters.ts`：risk/resource 两个 adapter。
- `frontend/src/types/reportWorkspace.ts`：ReportChapter/ReportDocument/ReportAdapter 类型。
- `frontend/src/services/reportAdapters.test.ts`：adapter 单测。

**前端（修改）**
- `frontend/src/components/plan/RichTextEditor.tsx`：内部改用 TiptapEditor（对外 props 不变）。
- `frontend/src/pages/Enterprise/RiskAssessmentTab.tsx` / `ResourceInvestigationTab.tsx`：改为薄壳接入 ReportWorkspace。
- `frontend/src/types/riskAssessment.ts`、`frontend/src/types/resourceInvestigation.ts`：补 style_preference 与 chapters 结构。
- `frontend/src/services/riskAssessmentService.ts` / `resourceInvestigationService.ts`：新增单章/审查/风格 API 函数。

---

## 任务 1：TiptapEditor 抽取（预案回归保障）

**文件：**
- 创建：`frontend/src/components/report/TiptapEditor.tsx`
- 修改：`frontend/src/components/plan/RichTextEditor.tsx`

**背景**：预案 RichTextEditor 同时承担“编辑器”与“AI 重写按钮”，且 props 要求 `planId/sectionKey`。抽取纯编辑器组件供报告工作台复用，预案页面对外行为不变。

`TiptapEditor.tsx` 内容（新建，从 RichTextEditor 迁移编辑器相关部分）：

```tsx
import { useEffect, useRef } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Placeholder from "@tiptap/extension-placeholder";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { Button, Tooltip } from "antd";
import { LoadingOutlined } from "@ant-design/icons";
import {
  BoldOutlined, ItalicOutlined, UnderlineOutlined, StrikethroughOutlined,
  OrderedListOutlined, UnorderedListOutlined, TableOutlined,
  UndoOutlined, RedoOutlined, AlignLeftOutlined, AlignCenterOutlined, AlignRightOutlined,
} from "@ant-design/icons";
import type { Editor } from "@tiptap/core";

export interface TiptapEditorHandle {
  getEditor: () => Editor | null;
}

interface TiptapEditorProps {
  content: string;
  onChange: (html: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  onReady?: (editor: Editor) => void;
  onSelectionUpdate?: (editor: Editor) => void;
}

function ToolbarButton({
  onClick, active, disabled, title, children,
}: {
  onClick: () => void; active?: boolean; disabled?: boolean; title: string; children: React.ReactNode;
}) {
  return (
    <Tooltip title={title}>
      <Button
        type={active ? "primary" : "text"} size="small"
        disabled={disabled} onClick={onClick}
        style={{ minWidth: 28, padding: "0 6px" }}
      >
        {children}
      </Button>
    </Tooltip>
  );
}

export default function TiptapEditor({
  content, onChange, readOnly, placeholder, onReady, onSelectionUpdate,
}: TiptapEditorProps) {
  const isInternalChange = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({ placeholder: placeholder || "编辑章节内容..." }),
      Table.configure({ resizable: true }),
      TableRow, TableCell, TableHeader,
    ],
    content,
    editable: !readOnly,
    onUpdate: ({ editor: ed }) => {
      isInternalChange.current = true;
      onChange(ed.getHTML());
      isInternalChange.current = false;
    },
    onSelectionUpdate: ({ editor: ed }) => {
      onSelectionUpdate?.(ed);
    },
  });

  useEffect(() => {
    if (!editor) return;
    if (isInternalChange.current) return;
    const html = editor.getHTML();
    const next = content || "";
    if (html !== next) {
      editor.commands.setContent(next, false);
    }
  }, [content, editor]);

  useEffect(() => {
    if (editor && onReady) onReady(editor);
  }, [editor, onReady]);

  if (!editor) {
    return <div style={{ minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <LoadingOutlined /> <span style={{ marginLeft: 8 }}>编辑器初始化中...</span>
    </div>;
  }

  const btn = (
    action: (ed: Editor) => void,
    opts: { active?: boolean; disabled?: boolean; title: string },
  ) => (
    <ToolbarButton
      title={opts.title}
      active={opts.active}
      disabled={opts.disabled || readOnly}
      onClick={() => action(editor)}
    >
      {opts.title === "加粗" ? <BoldOutlined /> : null}
    </ToolbarButton>
  );

  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 8, overflow: "hidden" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, padding: "6px 8px", borderBottom: "1px solid #f0f0f0", background: "#fafafa" }}>
        <ToolbarButton title="撤销" disabled={readOnly || !editor.can().undo()} onClick={() => editor.chain().focus().undo().run()}>
          <UndoOutlined />
        </ToolbarButton>
        <ToolbarButton title="重做" disabled={readOnly || !editor.can().redo()} onClick={() => editor.chain().focus().redo().run()}>
          <RedoOutlined />
        </ToolbarButton>
        <ToolbarButton title="加粗" active={editor.isActive("bold")} disabled={readOnly} onClick={() => editor.chain().focus().toggleBold().run()}>
          <BoldOutlined />
        </ToolbarButton>
        <ToolbarButton title="斜体" active={editor.isActive("italic")} disabled={readOnly} onClick={() => editor.chain().focus().toggleItalic().run()}>
          <ItalicOutlined />
        </ToolbarButton>
        <ToolbarButton title="下划线" active={editor.isActive("underline")} disabled={readOnly} onClick={() => editor.chain().focus().toggleUnderline().run()}>
          <UnderlineOutlined />
        </ToolbarButton>
        <ToolbarButton title="删除线" active={editor.isActive("strike")} disabled={readOnly} onClick={() => editor.chain().focus().toggleStrike().run()}>
          <StrikethroughOutlined />
        </ToolbarButton>
        <ToolbarButton title="有序列表" active={editor.isActive("orderedList")} disabled={readOnly} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
          <OrderedListOutlined />
        </ToolbarButton>
        <ToolbarButton title="无序列表" active={editor.isActive("bulletList")} disabled={readOnly} onClick={() => editor.chain().focus().toggleBulletList().run()}>
          <UnorderedListOutlined />
        </ToolbarButton>
        <ToolbarButton title="插入表格" disabled={readOnly} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>
          <TableOutlined />
        </ToolbarButton>
        <ToolbarButton title="左对齐" active={editor.isActive({ textAlign: "left" })} disabled={readOnly} onClick={() => editor.chain().focus().setTextAlign("left").run()}>
          <AlignLeftOutlined />
        </ToolbarButton>
        <ToolbarButton title="居中" active={editor.isActive({ textAlign: "center" })} disabled={readOnly} onClick={() => editor.chain().focus().setTextAlign("center").run()}>
          <AlignCenterOutlined />
        </ToolbarButton>
        <ToolbarButton title="右对齐" active={editor.isActive({ textAlign: "right" })} disabled={readOnly} onClick={() => editor.chain().focus().setTextAlign("right").run()}>
          <AlignRightOutlined />
        </ToolbarButton>
      </div>
      <EditorContent editor={editor} style={{ minHeight: 320, padding: "12px 16px" }} />
    </div>
  );
}
```

- [ ] **步骤 1：编写测试验证 TiptapEditor 渲染可用**

创建 `frontend/src/components/report/TiptapEditor.test.tsx`：

```tsx
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import TiptapEditor from "./TiptapEditor";

describe("TiptapEditor", () => {
  it("初始化不抛错并可输出 HTML", () => {
    const html = renderToString(
      <TiptapEditor content="<p>测试</p>" onChange={() => {}} />,
    );
    expect(html).toContain("编辑器初始化中");
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run src/components/report/TiptapEditor.test.tsx"`
预期：FAIL，`Failed to load url ./TiptapEditor`（文件不存在）。

- [ ] **步骤 3：创建 `frontend/src/components/report/TiptapEditor.tsx`**（内容见上）

- [ ] **步骤 4：运行测试验证通过**

同上命令。预期：PASS。

- [ ] **步骤 5：修改预案 RichTextEditor 内部改用 TiptapEditor**

打开 `frontend/src/components/plan/RichTextEditor.tsx`，保留其 props 与 AI 重写逻辑，做以下替换：
1. 删除 `useEditor`/扩展/`EditorContent`/工具栏按钮相关 JSX，替换为：
   ```tsx
   <TiptapEditor
     content={content}
     onChange={onChange}
     readOnly={readOnly}
     placeholder={placeholder}
     onReady={(ed) => { editorRef.current = ed; }}
     onSelectionUpdate={(ed) => {
       const { from, to } = ed.state.selection;
       lastSelectionFrom.current = from;
       lastSelectionTo.current = to;
       setSelectionText(ed.state.doc.textBetween(from, to, " "));
     }}
   />
   ```
2. 把原有 `const editor = useEditor({...})` 改为 `const editorRef = useRef<Editor | null>(null);`，凡引用 `editor.` 的地方改为 `editorRef.current?.`；AI 重写/续写等逻辑使用 `editorRef.current?.chain().focus().insertContent(...)` 保持原语义。
3. 保留原组件其余逻辑（selection 弹层、AI 重写按钮、MermaidRenderer 展示区等）不变。
4. 顶部新增 `import TiptapEditor from "@/components/report/TiptapEditor";`。

- [ ] **步骤 6：类型检查与回归**

运行：`cd frontend && node node_modules/typescript/bin/tsc -b`
预期：exit 0。
运行：`docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run"`
预期：全部既有测试通过。
手工：浏览器打开一个预案编辑页，确认富文本可编辑、加粗/表格可用、AI 重写按钮行为与之前一致。

- [ ] **步骤 7：Commit**

```bash
git add frontend/src/components/report/TiptapEditor.tsx frontend/src/components/report/TiptapEditor.test.tsx frontend/src/components/plan/RichTextEditor.tsx
git commit -m "refactor(editor): extract TiptapEditor kernel from plan RichTextEditor"
```

---

## 任务 2：后端模型与迁移——style_preference 列

**文件：**
- 修改：`backend/app/models/report_base.py`
- 创建：`backend/db_migration_20260903_report_workspace.sql`

- [ ] **步骤 1：ReportBase 加列**

`backend/app/models/report_base.py` 中 `summary` 字段后新增：

```python
    style_preference: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
```

（文件顶部已 import `JSONB`，无需新增 import。）

- [ ] **步骤 2：创建幂等迁移脚本**

`backend/db_migration_20260903_report_workspace.sql`：

```sql
-- 2026-09-03 报告工作台：报告级创作风格偏好列
ALTER TABLE risk_assessment_reports
  ADD COLUMN IF NOT EXISTS style_preference JSONB NOT NULL DEFAULT '{}';

ALTER TABLE resource_investigation_reports
  ADD COLUMN IF NOT EXISTS style_preference JSONB NOT NULL DEFAULT '{}';
```

- [ ] **步骤 3：执行迁移（本库）并验证幂等**

```bash
Get-Content -LiteralPath "backend/db_migration_20260903_report_workspace.sql" -Encoding UTF8 -Raw | docker exec -i emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1
```
再执行一次，预期两次都成功（UPDATE/ALTER 幂等，第二次输出不含错误）。

- [ ] **步骤 4：验证列存在**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -t -c "SELECT column_name FROM information_schema.columns WHERE table_name IN ('risk_assessment_reports','resource_investigation_reports') AND column_name='style_preference';"
```
预期：两行 `style_preference`。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/models/report_base.py backend/db_migration_20260903_report_workspace.sql
git commit -m "feat(report): add style_preference column (draft for report workspace)"
```

---

## 任务 3：summary.chapters 章节工具 + 单测

**文件：**
- 创建：`backend/app/services/report_chapter_utils.py`
- 创建：`backend/tests/test_report_chapter_storage.py`

章节草稿读写统一入口，两个报告共用，杜绝各处手写 dict 操作。

- [ ] **步骤 1：编写失败测试**

`backend/tests/test_report_chapter_storage.py`：

```python
from app.services.report_chapter_utils import (
    get_chapters,
    upsert_chapter,
    update_chapter_content,
)


def test_get_chapters_from_summary():
    assert get_chapters({"chapters": [{"key": "a", "content": "x"}]}) == [
        {"key": "a", "content": "x"},
    ]
    assert get_chapters({}) == []


def test_upsert_chapter_appends_and_updates():
    chapters = get_chapters({})
    chapters = upsert_chapter(chapters, "ch1", "标题", "内容A")
    chapters = upsert_chapter(chapters, "ch1", "标题", "内容B")
    chapters = upsert_chapter(chapters, "ch2", "标题2", "内容C")
    assert [c["key"] for c in chapters] == ["ch1", "ch2"]
    assert chapters[0]["content"] == "内容B"


def test_update_chapter_content_only_matches_key():
    chapters = [{"key": "a", "title": "A", "content": "1"}, {"key": "b", "title": "B", "content": "2"}]
    updated = update_chapter_content(chapters, "a", "new")
    assert updated[0]["content"] == "new"
    assert updated[1]["content"] == "2"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
docker cp backend/tests/test_report_chapter_storage.py emergency-plan-backend:/app/tests/test_report_chapter_storage.py
docker exec -w /app emergency-plan-backend python -m pytest tests/test_report_chapter_storage.py -q
```
预期：FAIL（ModuleNotFoundError: report_chapter_utils）。

- [ ] **步骤 3：创建 `backend/app/services/report_chapter_utils.py`**

```python
"""报告草稿章节（summary.chapters）读写工具。"""
from typing import Any


def get_chapters(summary: dict | None) -> list[dict]:
    if not summary or not isinstance(summary.get("chapters"), list):
        return []
    return summary["chapters"]


def upsert_chapter(chapters: list[dict], key: str, title: str, content: str) -> list[dict]:
    for ch in chapters:
        if ch.get("key") == key:
            ch["title"] = title
            ch["content"] = content
            return chapters
    chapters.append({"key": key, "title": title, "content": content})
    return chapters


def update_chapter_content(chapters: list[dict], key: str, content: str) -> list[dict]:
    for ch in chapters:
        if ch.get("key") == key:
            ch["content"] = content
            return chapters
    return chapters


def chapters_to_summary(chapters: list[dict]) -> dict[str, Any]:
    return {"chapters": chapters}
```

- [ ] **步骤 4：运行测试验证通过**

同步骤 2 命令。预期：3 passed。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/report_chapter_utils.py backend/tests/test_report_chapter_storage.py
git commit -m "feat(report): shared summary.chapters helpers"
```

---

## 任务 4：后端风格注入（build_chapter_prompt 支持 style）

**文件：**
- 修改：`backend/app/services/risk_assessment_service.py`
- 修改：`backend/app/services/resource_investigation_service.py`
- 修改：`backend/tests/test_report_data_injection.py`

- [ ] **步骤 1：编写失败测试**

在 `backend/tests/test_report_data_injection.py` 追加：

```python
def test_risk_prompt_includes_style_instruction():
    style = {
        "formality": "formal",
        "detail_level": "comprehensive",
        "table_preference": "heavy",
        "diagram_preference": "none",
        "mode": "panel",
    }
    prompt = ra_build("ch1_hazard_id", RA_CTX, style_preference=style)
    assert "正式" in prompt or "公文语体" in prompt
```

- [ ] **步骤 2：运行测试验证失败**

```bash
docker cp backend/tests/test_report_data_injection.py emergency-plan-backend:/app/tests/test_report_data_injection.py
docker exec -w /app emergency-plan-backend python -m pytest tests/test_report_data_injection.py::test_risk_prompt_includes_style_instruction -q
```
预期：FAIL（TypeError: build_chapter_prompt() got an unexpected keyword argument 'style_preference'）。

- [ ] **步骤 3：两个 service 增加 style_preference 参数并注入**

`risk_assessment_service.py` 的 `build_chapter_prompt` 签名改为：

```python
def build_chapter_prompt(
    chapter_key,
    context,
    previous_chapters=None,
    custom_instruction=None,
    style_preference: dict | None = None,
):
```

函数末尾（`prompt = "\n".join(lines_out)` 之后、法规追加之前）插入：

```python
    if style_preference:
        from app.services.prompt_cache import generate_style_instruction

        style = dict(style_preference)
        style["diagram_preference"] = "none"  # 报告正文禁用 mermaid
        prompt += "\n\n【创作风格——请严格遵循】\n" + generate_style_instruction(style)
```

`resource_investigation_service.py` 做完全相同的签名与注入修改。

- [ ] **步骤 4：运行测试验证通过**

同上命令，预期：PASS。随后跑该文件全量：`... python -m pytest tests/test_report_data_injection.py -q`（4 passed）。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_assessment_service.py backend/app/services/resource_investigation_service.py backend/tests/test_report_data_injection.py
git commit -m "feat(report): inject per-report style preference into chapter prompts"
```

---

## 任务 5：后端报告审查服务（规则审查）

**文件：**
- 创建：`backend/app/services/report_review_service.py`
- 创建：`backend/tests/test_report_review_service.py`

审查基于草稿章节内容做确定性规则检查（供前端 diff 后应用），规则含：内容为空/过短、占位符残留、Markdown 表格分隔线、Mermaid 代码块、HTML 标签未闭合、章节标题重复。

- [ ] **步骤 1：编写失败测试**

`backend/tests/test_report_review_service.py`：

```python
from app.services.report_review_service import review_report_chapters


def test_short_chapter_reported():
    issues = review_report_chapters([{"key": "ch1", "title": "一、辨识", "content": "太短"}])
    assert any(i["section_key"] == "ch1" and i["severity"] == "error" for i in issues)


def test_markdown_table_and_mermaid_reported():
    content = "正文\n| a | b |\n| --- | --- |\n```mermaid\nflowchart TD\n```"
    issues = review_report_chapters([{"key": "ch2", "title": "二、汇总", "content": content}])
    kinds = {i["kind"] for i in issues}
    assert "markdown_table" in kinds
    assert "mermaid_block" in kinds


def test_placeholder_reported():
    issues = review_report_chapters([{"key": "ch3", "title": "三、评估", "content": "内容含 XXX 与 xxx" * 5}])
    assert any(i["kind"] == "placeholder" for i in issues)


def test_clean_chapter_no_issues():
    issues = review_report_chapters([{"key": "ch4", "title": "四、措施", "content": "（内容完整）" * 60}])
    assert issues == []
```

- [ ] **步骤 2：运行测试验证失败**

```bash
docker cp backend/tests/test_report_review_service.py emergency-plan-backend:/app/tests/test_report_review_service.py
docker exec -w /app emergency-plan-backend python -m pytest tests/test_report_review_service.py -q
```
预期：FAIL（ModuleNotFoundError）。

- [ ] **步骤 3：创建 `backend/app/services/report_review_service.py`**

```python
"""报告草稿章节的确定性规则审查（供前端展示并人工确认修订）。"""

import re


def review_report_chapters(chapters: list[dict]) -> list[dict]:
    """返回 issues：{severity, section_key, kind, issue, suggestion}。"""
    issues: list[dict] = []
    for ch in chapters:
        key = ch.get("key", "")
        title = ch.get("title", "")
        content = ch.get("content", "") or ""
        text = content.strip()
        if not text:
            issues.append(_issue(key, "error", "empty", "章节内容为空", "请生成或补充该章节内容"))
            continue
        if len(text) < 80:
            issues.append(_issue(key, "warning", "too_short", f"章节内容过短（{len(text)} 字）", "请重新生成或补充内容"))
        if re.search(r"XXX|x{3,}", text, re.IGNORECASE):
            issues.append(_issue(key, "warning", "placeholder", "正文残留占位符 XXX/xxx", "请用实际内容替换占位符"))
        if re.search(r"^\s*\|[\s:\-|]+\|\s*$", text, re.MULTILINE):
            issues.append(_issue(key, "warning", "markdown_table", "正文含 Markdown 表格分隔线", "请改用 HTML 表格"))
        if "```mermaid" in text or re.search(r"\nmermaid\n(flowchart|graph|sequenceDiagram)", text):
            issues.append(_issue(key, "warning", "mermaid_block", "正文含 Mermaid 代码块", "请删除代码块，仅保留正文"))
        if content.count("<p>") != content.count("</p>"):
            issues.append(_issue(key, "error", "html_unbalanced", "HTML 段落标签未闭合", "请修复标签配对"))
        first_line = text.splitlines()[0].strip() if text.splitlines() else ""
        if title and first_line == title:
            issues.append(_issue(key, "info", "title_duplicate", "章节首行重复了章节标题", "删除首行标题"))
    return issues


def _issue(section_key: str, severity: str, kind: str, issue: str, suggestion: str) -> dict:
    return {
        "severity": severity,
        "section_key": section_key,
        "kind": kind,
        "issue": issue,
        "suggestion": suggestion,
    }
```

- [ ] **步骤 4：运行测试验证通过**

同步骤 2 命令，预期：4 passed。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/report_review_service.py backend/tests/test_report_review_service.py
git commit -m "feat(report): deterministic chapter review rules"
```

---

## 任务 6：后端章节/审查/风格端点（risk-assessment）

**文件：**
- 修改：`backend/app/routers/risk_assessment.py`
- 修改：`backend/app/schemas/risk_assessment.py`（或文件内定义请求模型）
- 修改：`backend/app/routers/resource_investigation.py`（对称复制端点，仅前缀/模型/上下文不同）

端点需求（见设计规格第 4 节）。以 risk 为例给出实现要点；resource 对称实现。

**6.1 单章生成 / 重生成（SSE）**

在 `risk_assessment.py` 新增请求模型与端点（放在现有 `generate` 端点之后）：

```python
class SectionGenerateRequest(BaseModel):
    chapter_key: str
    custom_instruction: str | None = None


@router.post("/{enterprise_id}/risk-assessment/generate/section")
async def generate_risk_assessment_section(
    enterprise_id: str,
    body: SectionGenerateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    context = await build_risk_management_context(enterprise_id, db)
    if context["total_events"] == 0:
        raise HTTPException(400, "请先录入风险分级管控数据")
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    ck = body.chapter_key
    cdef = next((c for c in RA_CHAPTER_DEFINITIONS if c["key"] == ck), None)
    if not cdef:
        raise HTTPException(400, "未知章节")
    report = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status.in_(["draft", "generating", "completed"]),
    ).order_by(RiskAssessmentReport.id))).scalars().first()
    if not report:
        report = RiskAssessmentReport(enterprise_id=enterprise_id, title="", status="draft")
        db.add(report)
    report.status = "draft"
    style_pref = report.style_preference or None
    await db.commit()
    from app.services.report_chapter_utils import get_chapters, upsert_chapter, chapters_to_summary

    async def event_generator():
        try:
            yield sse_event("progress", message=f"正在生成「{cdef['title']}」...",
                            current=1, total=1, section_key=ck)
            ch_prompt = build_chapter_prompt(
                ck, context,
                custom_instruction=body.custom_instruction,
                style_preference=style_pref,
            )
            messages = [
                {"role": "system", "content": _get_ra_system_prompt()},
                {"role": "user", "content": ch_prompt},
            ]
            ch_content = ""
            async for chunk_content in _stream_llm_with_messages_chunked(messages, ai_config):
                ch_content += chunk_content
                yield sse_event("chunk", content=chunk_content, section_key=ck)
            async with async_session() as bg_db:
                bg_report = (await bg_db.execute(select(RiskAssessmentReport).where(
                    RiskAssessmentReport.id == report.id))).scalar_one_or_none()
                if bg_report:
                    chapters = get_chapters(bg_report.summary)
                    chapters = upsert_chapter(chapters, ck, cdef["title"], ch_content)
                    bg_report.summary = chapters_to_summary(chapters)
                    await bg_db.commit()
            yield sse_event("section_done", section_key=ck, message=f"「{cdef['title']}」生成完成",
                            completed=1, total=1)
        except Exception as e:
            import traceback
            logger.error(f"Risk assessment section generation failed: {e}\n{traceback.format_exc()}")
            yield sse_event("error", message=str(e))

    return EventSourceResponse(event_generator())
```

`re-generate` 端点与上完全一致（路由 `/sections/{chapter_key}/regenerate`，body 仅 `custom_instruction`），实现可直接复用上面的生成函数，抽一个内部 `async def _stream_report_section(...)` 供两个路由调用。

**6.2 章节保存**

```python
class SectionContentUpdate(BaseModel):
    content: str


@router.put("/{enterprise_id}/risk-assessment/sections/{chapter_key}")
async def save_risk_assessment_section(
    enterprise_id: str, chapter_key: str, body: SectionContentUpdate,
    current_user=Depends(get_current_user), db=Depends(get_db),
):
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status.in_(["draft", "generating"]),
    ))).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    title = next((c["title"] for c in RA_CHAPTER_DEFINITIONS if c["key"] == chapter_key), chapter_key)
    chapters = get_chapters(report.summary)
    chapters = upsert_chapter(chapters, chapter_key, title, body.content)
    report.summary = chapters_to_summary(chapters)
    await db.commit()
    return ApiResponse(data={"content_length": len(body.content)})
```

**6.3 审查**

```python
class ReportReviewRequest(BaseModel):
    section_keys: list[str] | None = None


@router.post("/{enterprise_id}/risk-assessment/review")
async def review_risk_assessment(
    enterprise_id: str, body: ReportReviewRequest | None = None,
    current_user=Depends(get_current_user), db=Depends(get_db),
):
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status.in_(["draft", "generating", "completed"]),
    ))).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    chapters = get_chapters(report.summary)
    keys = set(body.section_keys) if body and body.section_keys else None
    targets = [c for c in chapters if keys is None or c.get("key") in keys]
    issues = review_report_chapters(targets)
    return ApiResponse(data={"report_id": report.id, "issues": issues})
```

**6.4 应用修订（LLM 重写单章，返回 diff 供前端确认，不落库）**

```python
@router.post("/{enterprise_id}/risk-assessment/review/apply")
async def apply_risk_assessment_review(
    enterprise_id: str, body: ReportReviewRequest,
    current_user=Depends(get_current_user), db=Depends(get_db),
):
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status.in_(["draft", "generating", "completed"]),
    ))).scalars().first()
    if not report:
        raise HTTPException(404, "请先生成报告")
    chapters = get_chapters(report.summary)
    keys = set(body.section_keys or [])
    issues = review_report_chapters([c for c in chapters if c.get("key") in keys])
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")
    applied = []
    for c in chapters:
        if c.get("key") not in keys:
            continue
        ch_issues = [i for i in issues if i["section_key"] == c.get("key")]
        if not ch_issues:
            continue
        issue_text = "；".join(f"{i['issue']}（建议：{i['suggestion']}）" for i in ch_issues)
        prompt = (
            "你是注册安全工程师。以下报告章节存在质量问题，请仅重写该章节正文，"
            "保留原章节标题语义，修正问题，不得编造企业数据；表格用 HTML 表格。\n"
            f"【问题】{issue_text}\n"
            f"【原内容】{c.get('content', '')}\n"
            "直接输出修订后的章节正文："
        )
        messages = [
            {"role": "system", "content": _get_ra_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        revised = ""
        try:
            async for chunk_content in _stream_llm_with_messages_chunked(messages, ai_config):
                revised += chunk_content
        except Exception as e:
            raise HTTPException(500, f"AI 修订失败：{e}")
        if not revised.strip() or len(revised.strip()) < 30:
            continue
        applied.append({"section_key": c["key"], "title": c.get("title", ""),
                        "original": c.get("content", ""), "revised": revised})
    return ApiResponse(data={"applied": applied})
```

**6.5 风格端点**

```python
class StyleUpdate(BaseModel):
    style_preference: dict


@router.get("/{enterprise_id}/risk-assessment/style")
async def get_risk_assessment_style(enterprise_id: str,
                                    current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id))).scalars().first()
    return ApiResponse(data={"style_preference": (report.style_preference if report else {}) or {}})


@router.put("/{enterprise_id}/risk-assessment/style")
async def save_risk_assessment_style(enterprise_id: str, body: StyleUpdate,
                                     current_user=Depends(get_current_user), db=Depends(get_db)):
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    report = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id))).scalars().first()
    if not report:
        report = RiskAssessmentReport(enterprise_id=enterprise_id, title="", status="draft")
        db.add(report)
    style = dict(body.style_preference)
    style["diagram_preference"] = "none"
    report.style_preference = style
    await db.commit()
    return ApiResponse(data={"style_preference": style})
```

resource_investigation.py 按同一模式补齐 6.1–6.5（章节标题来自 `RI_CHAPTER_DEFINITIONS`，系统提示词 `_get_ri_system_prompt`，审查系统词用应急专家措辞）。两端点文件顶部需要新增 import：`from pydantic import BaseModel`、`get_chapters/upsert_chapter/chapters_to_summary`、`review_report_chapters`、`get_system_ai_config`（部分已存在则去重）。

验证（两个文件共用）：

- [ ] **步骤 1：后端 import 冒烟**

```bash
docker exec -w /app emergency-plan-backend python -c "import app.routers.risk_assessment; import app.routers.resource_investigation; print('ok')"
```

- [ ] **步骤 2：重启并真实调用（复用上一轮测试 token 方案，仅验证单章保存与风格，避免消耗 LLM）**

```bash
docker restart emergency-plan-backend
```
用企业 94804158-cc33-464d-9aef-025ec90226be 依次验证：
`GET /style` → 200 且 `style_preference` 为对象；`PUT /style` 写回 `{}`；`PUT /sections/ch1_hazard_id`（内容取当前 draft 的 ch1 片段）→ 200；`POST /review` → 200 且 issues 为数组。LLM 类端点（单章生成、review/apply）保留到最终手工验收。

- [ ] **步骤 3：Commit**

```bash
git add backend/app/routers/risk_assessment.py backend/app/routers/resource_investigation.py
git commit -m "feat(report): section generate/save, review and style endpoints"
```

---

## 任务 7：前端 API 函数与类型

**文件：**
- 修改：`frontend/src/services/riskAssessmentService.ts`
- 修改：`frontend/src/services/resourceInvestigationService.ts`
- 修改：`frontend/src/types/riskAssessment.ts`、`frontend/src/types/resourceInvestigation.ts`
- 创建：`frontend/src/types/reportWorkspace.ts`

- [ ] **步骤 1：类型扩展**

`frontend/src/types/riskAssessment.ts` 中 `RiskAssessmentReport` 增加：

```ts
  style_preference?: Record<string, string> | null;
```

`summary` 字段类型由 `RiskAssessmentSummary` 改为兼容草稿结构：

```ts
  summary: Partial<RiskAssessmentSummary> & {
    chapters?: Array<{ key: string; title: string; content: string }>;
  };
```

`resourceInvestigation.ts` 的 `ResourceInvestigationReport` 同步扩展（先读文件确认其 summary 类型后同样处理）。

- [ ] **步骤 2：新建 `frontend/src/types/reportWorkspace.ts`**

```ts
import type { ReportVersionItem } from "@/types/riskAssessment";

export interface ReportChapter {
  key: string;
  title: string;
  content: string;
}

export interface ReportDocument {
  id: string;
  title: string;
  content: string;
  status: string;
  chapters: ReportChapter[];
  stylePreference?: Record<string, string> | null;
}

export interface ReportIssue {
  severity: "error" | "warning" | "info";
  section_key: string;
  kind: string;
  issue: string;
  suggestion: string;
}

export interface ReportSSECallback {
  onEvent: (event: any) => void;
  onError: (error: string) => void;
  onComplete: () => void;
}

export interface ReportAdapter {
  load(enterpriseId: string): Promise<ReportDocument>;
  saveChapter(enterpriseId: string, key: string, content: string): Promise<void>;
  generateChapter(enterpriseId: string, key: string, cb: ReportSSECallback): AbortController;
  regenerateChapter(enterpriseId: string, key: string, cb: ReportSSECallback): AbortController;
  generateAll(enterpriseId: string, cb: ReportSSECallback): AbortController;
  review(enterpriseId: string, sectionKeys: string[] | null): Promise<ReportIssue[]>;
  applyReview(enterpriseId: string, sectionKeys: string[]): Promise<
    Array<{ section_key: string; title: string; original: string; revised: string }>
  >;
  getStyle(enterpriseId: string): Promise<Record<string, string>>;
  saveStyle(enterpriseId: string, style: Record<string, string>): Promise<void>;
  merge(enterpriseId: string, chapters: ReportChapter[]): Promise<void>;
  listVersions(enterpriseId: string): Promise<ReportVersionItem[]>;
  exportUrl(enterpriseId: string): string;
}
```

- [ ] **步骤 3：`riskAssessmentService.ts` 追加 API 函数**

```ts
export function generateRiskAssessmentSectionStream(
  enterpriseId: string,
  chapterKey: string,
  cb: {
    onEvent: (event: SSEEvent) => void;
    onError: (error: string) => void;
    onComplete: () => void;
  },
): AbortController {
  return ssePost(`/enterprises/${enterpriseId}/risk-assessment/generate/section`, { chapter_key: chapterKey }, cb);
}
```

把当前重复的 fetch/reader 解析逻辑抽成模块内 `ssePost(path, body, cb)`（与现 `generateRiskAssessmentStream` 解析一致），让 generate/regenerate 共用；随后：

```ts
export async function saveRiskAssessmentSection(
  enterpriseId: string, chapterKey: string, content: string,
): Promise<void> {
  await api.put(`/enterprises/${enterpriseId}/risk-assessment/sections/${chapterKey}`, { content });
}

export async function reviewRiskAssessment(
  enterpriseId: string, sectionKeys: string[] | null = null,
): Promise<ReportIssue[]> {
  const res = await api.post(`/enterprises/${enterpriseId}/risk-assessment/review`, { section_keys: sectionKeys });
  return res.data.data.issues;
}

export async function applyRiskAssessmentReview(
  enterpriseId: string, sectionKeys: string[],
): Promise<Array<{ section_key: string; title: string; original: string; revised: string }>> {
  const res = await api.post(`/enterprises/${enterpriseId}/risk-assessment/review/apply`, { section_keys: sectionKeys });
  return res.data.data.applied;
}

export async function getRiskAssessmentStyle(
  enterpriseId: string,
): Promise<Record<string, string>> {
  const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment/style`);
  return res.data.data.style_preference || {};
}

export async function saveRiskAssessmentStyle(
  enterpriseId: string, style: Record<string, string>,
): Promise<void> {
  await api.put(`/enterprises/${enterpriseId}/risk-assessment/style`, { style_preference: style });
}
```

`resourceInvestigationService.ts` 提供同构函数（`saveResourceInvestigationSection` / `reviewResourceInvestigation` / `applyResourceInvestigationReview` / `get/saveResourceInvestigationStyle` / `generateResourceInvestigationSectionStream`）。

- [ ] **步骤 4：新建 `frontend/src/services/reportAdapters.ts`**

```ts
import type {
  ReportAdapter, ReportChapter, ReportDocument, ReportIssue, ReportSSECallback,
} from "@/types/reportWorkspace";
import * as ra from "./riskAssessmentService";
import * as ri from "./resourceInvestigationService";

function chaptersFrom(report: { summary?: { chapters?: ReportChapter[] } }): ReportChapter[] {
  return report.summary?.chapters ?? [];
}

function makeAdapter(
  kind: "risk" | "resource",
): ReportAdapter {
  const svc = kind === "risk" ? ra : ri;
  const path = kind === "risk" ? "risk-assessment" : "resource-investigation";
  return {
    async load(enterpriseId) {
      const doc = kind === "risk"
        ? await ra.getRiskAssessment(enterpriseId)
        : await ri.getResourceInvestigation(enterpriseId);
      return {
        id: doc.id,
        title: doc.title,
        content: doc.content,
        status: doc.status,
        chapters: chaptersFrom(doc as never),
        stylePreference: (doc as { style_preference?: Record<string, string> }).style_preference,
      };
    },
    saveChapter: (id, key, content) => kind === "risk"
      ? ra.saveRiskAssessmentSection(id, key, content)
      : ri.saveResourceInvestigationSection(id, key, content),
    generateChapter: (id, key, cb) => kind === "risk"
      ? ra.generateRiskAssessmentSectionStream(id, key, cb)
      : ri.generateResourceInvestigationSectionStream(id, key, cb),
    regenerateChapter: (id, key, cb) => generateChapter(id, key, cb),
    generateAll: (id, cb) => kind === "risk"
      ? ra.generateRiskAssessmentStream(id, undefined, cb.onEvent, cb.onError, cb.onComplete)
      : ri.generateResourceInvestigationStream(id, undefined, cb.onEvent, cb.onError, cb.onComplete),
    review: (id, keys) => kind === "risk"
      ? ra.reviewRiskAssessment(id, keys)
      : ri.reviewResourceInvestigation(id, keys),
    applyReview: (id, keys) => kind === "risk"
      ? ra.applyRiskAssessmentReview(id, keys)
      : ri.applyResourceInvestigationReview(id, keys),
    getStyle: (id) => kind === "risk"
      ? ra.getRiskAssessmentStyle(id)
      : ri.getResourceInvestigationStyle(id),
    saveStyle: (id, style) => kind === "risk"
      ? ra.saveRiskAssessmentStyle(id, style)
      : ri.saveResourceInvestigationStyle(id, style),
    merge: (id, chapters) => kind === "risk"
      ? ra.mergeRiskAssessment(id, chapters)
      : ri.mergeResourceInvestigation(id, chapters),
    listVersions: (id) => kind === "risk"
      ? ra.listRiskAssessmentVersions(id)
      : ri.listResourceInvestigationVersions(id),
    exportUrl: (id) => `/api/v1/enterprises/${id}/${path}/export?token=${localStorage.getItem("access_token")}`,
  };
}

export const riskAssessmentAdapter: ReportAdapter = makeAdapter("risk");
export const resourceInvestigationAdapter: ReportAdapter = makeAdapter("resource");
```

（`generateChapter` 与 `regenerateChapter` 内部均调用对应 service 的 section 流；regenerate 可先同 generate。）

- [ ] **步骤 5：类型检查**

`cd frontend && node node_modules/typescript/bin/tsc -b`，预期 exit 0。

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/riskAssessment.ts frontend/src/types/resourceInvestigation.ts frontend/src/types/reportWorkspace.ts frontend/src/services/riskAssessmentService.ts frontend/src/services/resourceInvestigationService.ts frontend/src/services/reportAdapters.ts
git commit -m "feat(report): workspace types, api functions and adapters"
```

---

## 任务 8：ReportWorkspace 工作台

**文件：**
- 创建：`frontend/src/components/report/ReportWorkspace.tsx`
- 创建：`frontend/src/components/report/ReportChapterActions.tsx`
- 创建：`frontend/src/components/report/ReviewDrawer.tsx`

工作台由以下状态驱动（组件内 useState/useRef）：

```ts
interface ReportWorkspaceProps {
  adapter: ReportAdapter;
  enterpriseId: string;
  meta: { emptyTitle: string; emptyDesc: string; generateLabel: string };
}
```

`ReportChapterActions`（单章生成/重写按钮，交互对齐预案 AIGenerateButton 的 Modal+确认）：

```tsx
interface ReportChapterActionsProps {
  generate: () => void;       // 全章生成
  regenerate: () => void;     // 重新生成
  disabled?: boolean;
  loading?: boolean;
}
```

`ReviewDrawer`：

```tsx
interface ReviewDrawerProps {
  open: boolean;
  issues: ReportIssue[];
  onClose: () => void;
  onApply: (sectionKeys: string[]) => void;
  applying: boolean;
}
```

实现时复用：
- `DiffPreviewModal`（`frontend/src/components/plan/DiffPreviewModal.tsx`）
- `StylePanel`（`frontend/src/components/plan/StylePanel.tsx`，value/onChange 受控）
- `renderReportMarkdown`（本轮已建）
- `AiNotConfiguredHint` / `aiErrorDisplay`

关键逻辑（ReportWorkspace 内）：
1. `useEffect` 挂载后 `adapter.load` → `doc.chapters` 回填；无报告则空章节（章节定义来自 adapter 静态 getChapters 或后端 `/chapters`，RiskAssessmentTab 已有 FALLBACK_CHAPTERS/后端拉取逻辑，工作台接受 `chapters` prop 或 adapter 提供）。
2. 章节内容编辑：`TiptapEditor content=章节.content onChange→防抖 1.5s saveChapter`；保存状态显示在顶栏。
3. 全量生成：调 `adapter.generateAll`，SSE chunk 按 `section_key` 写对应章节并刷新编辑器；失败章节（`error` 事件）计入列表可重试。
4. 单章生成：`ReportChapterActions` 触发 `adapter.generateChapter` 流式写当前章节。
5. 审查：`ReviewDrawer` 列出 `adapter.review` 结果，勾选章节后 `adapter.applyReview` 得 revised，逐条 DiffPreviewModal 确认接受（接受 → 更新内存章节并 `saveChapter`）。
6. 风格：顶栏按钮弹 Modal 内嵌 `StylePanel`，onChange 保存本地，确定后 `adapter.saveStyle`。
7. 工具栏：重新生成全量、停止、审查、创作风格、保存版本（`adapter.listVersions` 列表 Modal 或跳转现有版本页——本轮先做“保存版本”调用 POST /versions + 成功提示）、导出（`window.open(adapter.exportUrl)`）、合并定稿、预览（跳转 `/enterprises/{id}/risk-assessment/preview`）。

- [ ] **步骤 1：编写 adapter 行为测试（红灯）**

`frontend/src/services/reportAdapters.test.ts`：

```ts
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { riskAssessmentAdapter } from "./reportAdapters";
import * as ra from "./riskAssessmentService";

describe("riskAssessmentAdapter", () => {
  it("load 返回统一 ReportDocument 结构（chapters 来自 summary.chapters）", async () => {
    vi.spyOn(ra, "getRiskAssessment").mockResolvedValue({
      id: "r1", enterprise_id: "e1", title: "T", content: "",
      status: "draft", generated_by: "ai", generated_at: null,
      created_at: "", updated_at: "",
      summary: { chapters: [{ key: "ch1", title: "一、辨识", content: "x" }] },
    } as never);
    const doc = await riskAssessmentAdapter.load("e1");
    expect(doc.chapters).toEqual([{ key: "ch1", title: "一、辨识", content: "x" }]);
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

```bash
docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run src/services/reportAdapters.test.ts"
```
预期：FAIL（模块 reportAdapters 不存在，或 API 函数不存在）。

- [ ] **步骤 3：实现任务 7 全部文件后测试转绿**

任务 7 的 API 函数与 adapter 完成后重跑，预期 PASS。若先实现本任务，需先完成任务 7 的 service 函数（按顺序执行，任务 7 在前）。

- [ ] **步骤 4：实现 ReportWorkspace / ReportChapterActions / ReviewDrawer（代码见上节接口）并接入**

组件实现要点：所有 `adapter.*` 调用以 try/catch 包裹，错误经 `aiErrorDisplay` 显示；SSE 回调统一 `onError→停生成、onComplete→刷新保存状态`。

- [ ] **步骤 5：类型检查与既有测试**

`node node_modules/typescript/bin/tsc -b`（exit 0）；`docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run"`（全部通过）。

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/components/report frontend/src/services/reportAdapters.ts frontend/src/services/reportAdapters.test.ts
git commit -m "feat(report): generic ReportWorkspace with chapter actions and review drawer"
```

---

## 任务 9：两个报告 Tab 接入工作台

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskAssessmentTab.tsx`
- 修改：`frontend/src/pages/Enterprise/ResourceInvestigationTab.tsx`

把两个 Tab 主体替换为薄壳：

```tsx
export default function RiskAssessmentTab({ enterpriseId }: Props) {
  return (
    <ReportWorkspace
      adapter={riskAssessmentAdapter}
      enterpriseId={enterpriseId}
      meta={{
        emptyTitle: "尚未生成风险评估报告",
        emptyDesc: "根据法规要求，编制应急预案前需先完成风险评估。系统将基于风险分级管控数据自动生成。",
        generateLabel: "AI 生成风险评估报告",
      }}
    />
  );
}
```

保留原组件中“已有报告时展示完成态/重新生成/导出/预览”的语义由工作台内部状态覆盖：`doc.status === "completed"` 时正文只读展示（TiptapEditor readOnly + markdown-it 渲染）；draft 时进入可编辑。

- [ ] **步骤 1：类型检查**

`cd frontend && node node_modules/typescript/bin/tsc -b`，预期 exit 0。

- [ ] **步骤 2：全量前端测试**

`docker exec emergency-plan-frontend sh -c "cd /app && npx vitest run"`，预期全绿。

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskAssessmentTab.tsx frontend/src/pages/Enterprise/ResourceInvestigationTab.tsx
git commit -m "feat(report): wire risk/resource tabs to ReportWorkspace"
```

---

## 任务 10：端到端验证与部署

- [ ] **步骤 1：后端重启与冒烟**

```bash
docker restart emergency-plan-backend
```
健康检查 `curl http://localhost:8000/api/v1/health` → 200。

- [ ] **步骤 2：真实企业 API 走查（企业 94804158-cc33-464d-9aef-025ec90226be）**

按任务 6 步骤 2 的 token 方案验证：`GET /style`、`PUT /sections/ch1_hazard_id`、`POST /review`。再手工触发一次单章生成（页面按钮），观察 SSE 流式写入编辑器。

- [ ] **步骤 3：前端构建并同步**

```bash
docker exec emergency-plan-frontend sh -c "cd /app && npm run build"
docker cp "emergency-plan-frontend:/app/dist/." "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\"
docker cp "C:\Users\55061\Documents\数字化预案自动生成 2\frontend\dist\." "shuzihuayuan:/app/dist/"
```

- [ ] **步骤 4：手工验收清单**

1. 预案编辑器：富文本编辑、加粗/表格、AI 重写与预案一致（回归）。
2. 风险评估报告：全量生成 → 章节可编辑（富文本）→ 单章重新生成 → 审查出 issues → 应用修订 diff 确认 → 风格面板保存 → 合并 → 预览/导出。
3. 应急资源调查报告：同上全流程。
4. 移动端（8082 `/m`）报告页不受影响。

- [ ] **步骤 5：更新 TASKS.md 快照并汇报**

---

## 自检结果

- 规格覆盖：设计文档第 4 节 8 个端点 → 任务 6；第 5 节迁移 → 任务 2；第 6 节前端结构 → 任务 1/7/8/9；第 7 节数据流/第 8 节错误处理/第 9 节测试 → 任务 8/10；第 10 节顺序 → 任务顺序一致。
- 占位符：无 TODO/待定；每个代码步骤均给出代码或明确改动说明。
- 类型一致性：`ReportAdapter` 方法名在 types/adapter/Workspace/测试中一致（load/saveChapter/generateChapter/regenerateChapter/generateAll/review/applyReview/getStyle/saveStyle/merge/listVersions/exportUrl）。
