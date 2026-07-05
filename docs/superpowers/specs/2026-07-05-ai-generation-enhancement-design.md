# AI 生成增强：自定义提示词 + 局部重生成 + 快捷指令 — 设计规格

> **日期**：2026-07-05 | **状态**：设计中 | **依赖**：PRD-04, PRD-05

---

## 1. 概述

在现有单章节 AI 生成基础上，新增三个能力：

1. **单章节生成前自定义提示词** — 后端正支持，前端缺 UI 入口
2. **框选局部重新生成** — 全新，选中编辑器文本后 AI 仅重写该段落
3. **快捷指令模板** — 预设常用调整指令，一键填入

辅助增强：AI 内容视觉标记、生成前后 Diff 对比弹窗。

---

## 2. 现有基础

| 组件 | 现状 |
|------|------|
| `POST /plans/{id}/generate/{key}` | 已支持 `custom_instruction` |
| `generationService.ts` → `generateSectionStream` | 第4参数 `customInstruction` 已定义 |
| `AIGenerateButton.tsx` | 调用时传 `undefined` |
| `RichTextEditor.tsx` | 基于 TipTap，原生支持文本选区 |
| `PromptManagePage` | 已有提示词 CRUD（YWT 同步 + 本地DB） |

---

## 3. 功能详设

### 3.1 单章节生成自定义提示词（P0）

**改动：** `AIGenerateButton.tsx`

点击"AI 生成"→ Modal 弹窗：
- 标题：「生成「章节名」」
- 文本域：自定义提示词（placeholder: "例如：重点描述三级响应启动条件..."）
- 快捷指令 Chip 行（见 3.3）
- 「取消」「生成」按钮
- 确认后 `generateSectionStream(planId, sectionKey, customInstruction, ...)`

### 3.2 框选局部重生成（P1）

**后端：** `POST /plans/{plan_id}/sections/{section_key}/regenerate`

请求体：
```json
{
  "selected_text": "string",
  "surrounding_context_before": "string | null",
  "surrounding_context_after": "string | null", 
  "custom_instruction": "string | null"
}
```

Prompt 构建策略：
- 系统提示词同上
- 用户 prompt：全文上下文 + 标记选中段落 + 修改要求
- SSE 流式返回替换文本

**前端：**
- `RichTextEditor.tsx`：监听 TipTap selection，选区非空时浮动工具栏出现「AI 重写」按钮
- 点击 → 同样的 Modal（标题改为「重写选中内容」）
- 后端返回后 `editor.chain().deleteSelection().insertContent(text).run()`

### 3.3 快捷指令模板（P0）

存储在 `localStorage`，键名 `plan_quick_prompts`。

默认预设：
```
更详细 / 更简洁 / 按GB/T规范 / 补充操作步骤 / 增加定量数据 / 公文语体
```

新增 `frontend/src/utils/quickPrompts.ts`：
- `getQuickPrompts()` — 读取（预设合并用户自定义）
- `addQuickPrompt(label, text)` — 用户添加
- `removeQuickPrompt(id)` — 删除

### 3.4 AI 内容视觉标记（P2）

CSS 类 `.ai-generated-section`：左边框蓝色、背景微蓝。
章节 `ai_generated === true` 时在 `RichTextEditor` 容器上添加该类。

局部重生成后的新文本：`.ai-regenerated-flash` 淡绿色边框，3s fade。

### 3.5 Diff 对比弹窗（P2）

组件 `DiffPreviewModal.tsx`：
- Props：`oldText`, `newText`, `onAccept`, `onReject`
- 双栏并排，差异高亮
- 接受 → 替换内容回调；拒绝 → 关闭

---

## 4. 文件清单

| 文件 | 操作 | 功能 |
|------|------|------|
| `backend/app/routers/generation.py` | 修改 | +`regenerate_selection` 端点 |
| `backend/app/schemas/plan.py` | 修改 | +`RegenerateRequest` |
| `frontend/src/components/plan/AIGenerateButton.tsx` | 重构 | 自定义提示词弹窗 + 选区模式 + 快捷指令 |
| `frontend/src/components/plan/RichTextEditor.tsx` | 修改 | 选区监听 + 浮动工具栏 + AI 标记 |
| `frontend/src/components/plan/DiffPreviewModal.tsx` | 新增 | 生成前后对比 |
| `frontend/src/utils/quickPrompts.ts` | 新增 | 快捷指令模板管理 |
| `frontend/src/styles/global.css` | 修改 | AI标记样式 |

---

## 5. 自检

- [x] 无占位符/TODO
- [x] 后端 custom_instruction 已存在，前端只补 UI，无重复开发
- [x] 快捷指令用 localStorage，零后端改动
- [x] 选区重生成仅桌面端（TipTap），移动端 textarea 不支持，降级为隐藏该按钮
- [x] 无新依赖
