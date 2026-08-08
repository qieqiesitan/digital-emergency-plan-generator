# 预案附图扩展 第 3 批（前端展示 + 导出接入）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 前端展示 `diagram_svgs`（预渲染 SVG + 占位块）、缺数据提示条与一键补图入口；docx 导出插入附图、占位转文字。

**架构：** `MermaidRenderer.tsx` 扩展为 DiagramRenderer（兼容现有 mermaid 块 + 新增 diagram_svgs 预渲染与占位展示）；`PlanEditorPage` 增加缺数据提示与补图按钮；`export.py`/`docx_template.py` 读取 `diagram_svgs` 走现有 SVG→PNG 路径。

**技术栈：** React + TypeScript + Antd；python-docx（导出）。

**规格：** `docs/superpowers/specs/2026-08-08-plan-diagrams-enhancement-design.md` §4.2、§5、§6.4、§6.5

---

## 文件结构

**前端：**
- 修改 `frontend/src/types/plan.ts` — PlanSection + diagram_svgs
- 修改 `frontend/src/components/plan/MermaidRenderer.tsx` — 扩展 DiagramRenderer
- 修改 `frontend/src/pages/Plan/PlanEditorPage.tsx` — 缺数据提示条、补图按钮
- 修改 `frontend/src/services/planService.ts` — regenerateMissingDiagrams

**后端：**
- 修改 `backend/app/routers/export.py` — 预览/导出读取 diagram_svgs
- 修改 `backend/app/services/docx_template.py` — 占位转文字、SVG→PNG 插入
- 修改 `backend/tests/test_plan_diagrams_api.py`（导出相关断言）

---

### 任务 1：前端类型 + API 客户端

**文件：**
- 修改：`frontend/src/types/plan.ts`
- 修改：`frontend/src/services/planService.ts`

- [ ] **步骤 1：类型扩展**

```typescript
// frontend/src/types/plan.ts  PlanSection 追加：
  diagram_svgs: Record<string, {
    key?: string;
    placeholder?: boolean;
    reason?: string;
    svg?: string;
  }>;
```

- [ ] **步骤 2：API 客户端**

```typescript
// frontend/src/services/planService.ts 追加：
export async function regenerateMissingDiagrams(
  planId: string
): Promise<{ regenerated: number; skipped: number; placeholders_remaining: number }> {
  const res = await api.post<ApiResponse<{ regenerated: number; skipped: number; placeholders_remaining: number }>>(
    `/plans/${planId}/diagrams/regenerate-missing`
  );
  return res.data.data;
}
```

- [ ] **步骤 3：类型检查**

运行：`cd frontend && npx tsc -b`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/types/plan.ts frontend/src/services/planService.ts
git commit -m "feat(plan): add diagram_svgs types and regenerate API client (diagrams batch3)"
```

---

### 任务 2：MermaidRenderer 扩展为 DiagramRenderer

**文件：**
- 修改：`frontend/src/components/plan/MermaidRenderer.tsx`
- 修改：`frontend/src/components/plan/RichTextEditor.tsx`（调用处传 diagramSvgs）

- [ ] **步骤 1：实现 DiagramRenderer 逻辑**

在 `MermaidRenderer.tsx` 中扩展 props 与渲染：

```typescript
interface MermaidRendererProps {
  html: string;
  diagramSvgs?: Record<string, {
    key?: string;
    placeholder?: boolean;
    reason?: string;
    svg?: string;
  }>;
}

export default function MermaidRenderer({ html, diagramSvgs = {} }: MermaidRendererProps) {
  // 现有 mermaid code block 渲染保持不变...

  // 新增：diagram_svgs 预渲染 SVG 与占位块
  const diagramHtml = Object.entries(diagramSvgs)
    .filter(([, meta]) => meta?.placeholder)
    .map(([key, meta]) => (
      `<div class="diagram-placeholder" data-diagram-key="${key}" style="border:2px dashed #d9d9d9;border-radius:8px;padding:24px;text-align:center;color:#999;margin:16px 0;">
         <div style="font-size:14px;font-weight:500;color:#666;">【${key}】</div>
         <div style="font-size:12px;margin-top:8px;">待补充企业数据后生成（${meta?.reason || ""}）</div>
       </div>`
    ))
    .join("");

  // 非占位 SVG 直接内嵌
  const svgHtml = Object.values(diagramSvgs)
    .filter((meta) => meta?.svg && !meta?.placeholder)
    .map((meta) => meta!.svg!)
    .join("");

  return (
    <div
      ref={containerRef}
      dangerouslySetInnerHTML={{ __html: html + svgHtml + diagramHtml }}
    />
  );
}
```

- [ ] **步骤 2：RichTextEditor 传 diagramSvgs**

`RichTextEditor.tsx` props 增加 `diagramSvgs`，透传给 `MermaidRenderer`：

```typescript
      {showMermaid ? (
        <MermaidRenderer html={content} diagramSvgs={diagramSvgs} />
      ) : (
```

`PlanEditorPage` 调用 `RichTextEditor` 时传 `diagramSvgs={currentSection?.diagram_svgs}`。

- [ ] **步骤 3：类型检查与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：通过

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/plan/MermaidRenderer.tsx frontend/src/components/plan/RichTextEditor.tsx frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "feat(plan): render diagram_svgs and placeholders in editor preview (diagrams batch3)"
```

---

### 任务 3：缺数据提示条 + 补图按钮

**文件：**
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`
- 修改：`frontend/src/services/planService.ts`（已加）

- [ ] **步骤 1：提示条与按钮**

`PlanEditorPage` 顶部（PageHeader 下方）新增：

```typescript
  const missingDiagrams = useMemo(() => {
    const keys = new Set<string>();
    (sections || []).forEach((s) => {
      Object.entries(s.diagram_svgs || {}).forEach(([k, meta]) => {
        if (meta?.placeholder) keys.add(k);
      });
    });
    return Array.from(keys);
  }, [sections]);

  const regenerateDiagramsMut = useMutation({
    mutationFn: () => regenerateMissingDiagrams(id!),
    onSuccess: (r) => {
      message.success(`已重新生成 ${r.regenerated} 张附图`);
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
    },
    onError: () => message.error("重新生成附图失败"),
  });
```

渲染（有占位时）：

```typescript
        {missingDiagrams.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message={`该企业缺部分数据，${missingDiagrams.length} 张图未生成`}
            description={missingDiagrams.join("、")}
            action={
              <Space>
                <Button size="small" onClick={() => navigate("/enterprises")}>
                  去补数据
                </Button>
                <Button size="small" type="primary" onClick={() => regenerateDiagramsMut.mutate()}>
                  重新生成缺失附图
                </Button>
              </Space>
            }
          />
        )}
```

（`Alert`/`Space` 从 antd 导入；`navigate` 目标按实际路由调整。）

- [ ] **步骤 2：类型检查与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：通过

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "feat(plan): show missing-diagram notice and regenerate button in editor (diagrams batch3)"
```

---

### 任务 4：导出接入（预览 + docx）

**文件：**
- 修改：`backend/app/routers/export.py`
- 修改：`backend/app/services/docx_template.py`
- 测试：`backend/tests/test_plan_diagrams_api.py`（追加导出断言）

- [ ] **步骤 1：预览接入**

`export.py::get_export_preview` 中，每个章节处理完 mermaid 后追加 diagram_svgs：

```python
        # 附图：非占位 SVG 内嵌，占位转文字
        for key, meta in (section.diagram_svgs or {}).items():
            if isinstance(meta, dict) and meta.get("placeholder"):
                html_parts.append(
                    f'<p class="diagram-placeholder">【{key}】待补充数据后生成'
                    f"（{meta.get('reason','')}）</p>"
                )
            elif isinstance(meta, dict) and meta.get("svg"):
                svg = meta["svg"]
                m = re.search(r"<svg[^>]*>.*?</svg>", svg, re.DOTALL)
                if m:
                    html_parts.append(
                        '<div class="mermaid-diagram" style="margin:16px 0;padding:16px;'
                        'background:#fafafa;border:1px solid #e8e8e8;border-radius:6px;'
                        'text-align:center;">' + m.group(0) + "</div>"
                    )
```

- [ ] **步骤 2：docx 接入**

`docx_template.py::generate_plan_docx` 的章节数据增加 `diagram_svgs`，在 Mermaid 图片插入后追加：

```python
        # 附图：非占位 SVG → PNG 插入；占位 → 文字行
        for key, meta in (section.get("diagram_svgs") or {}).items():
            if isinstance(meta, dict) and meta.get("placeholder"):
                add_normal_paragraph(doc, f"【{key}】待补充企业数据后生成")
            elif isinstance(meta, dict) and meta.get("svg"):
                try:
                    png_bytes = await _asyncio.to_thread(render_svg_to_png, meta["svg"])
                    img_stream = io.BytesIO(png_bytes)
                    doc.add_picture(img_stream, width=Cm(14.6))
                    if doc.paragraphs:
                        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception as e:
                    logger.warning("Diagram %s render failed: %s", key, e)
                    add_normal_paragraph(doc, f"【{key}】附图渲染失败")
```

（`render_svg_to_png` 已由 export.py 导入，docx_template 需补导入；`section` 数据构建处传入 `diagram_svgs`。）

`export.py::export_plan_docx` 的 `sections_data` 构建追加 `"diagram_svgs": s.diagram_svgs or {}`。

- [ ] **步骤 3：测试与全量回归**

追加测试（`test_plan_diagrams_api.py`）：mock 章节含占位 diagram_svgs，调用 `get_export_preview` 断言响应含「待补充数据后生成」；含 SVG 断言含 `<svg`。

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 4：Commit**

```bash
git add backend/app/routers/export.py backend/app/services/docx_template.py backend/tests/test_plan_diagrams_api.py
git commit -m "feat(plan): export diagram_svgs in preview and docx (diagrams batch3)"
```

---

### 任务 5：第 3 批收尾验证

- [ ] **步骤 1：后端全量回归**

运行：`docker run --rm -v "${PWD}:/app" -w /app 2-backend python -m pytest tests/ -q --ignore=tests/test_autofill_research.py`
预期：全部通过

- [ ] **步骤 2：前端构建与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：通过

- [ ] **步骤 3：规格对照自检**

- [x] §4.2 编辑页提示 + 跳转 → 任务 3
- [x] §5 占位展示 → 任务 2、4
- [x] §6.4 DiagramRenderer → 任务 2
- [x] §6.5 预览/docx 导出 → 任务 4
- [x] §4.3 补图按钮 → 任务 3

- [ ] **步骤 4：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): diagrams batch3 final verification"
```
