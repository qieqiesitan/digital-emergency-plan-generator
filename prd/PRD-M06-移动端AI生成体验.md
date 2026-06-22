# PRD-M06：移动端 AI 生成体验

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00, PRD-M01, PRD-M05, PRD-04（AI 生成引擎） | **关联文档**：移动端设计方案 §7

---

## 1. 模块概述

AI 生成是系统的核心差异化能力。移动端在复用桌面端全部生成 API 的基础上，专为小屏和触控设计流式生成展示、生成确认面板、批量生成引导和智能上下文感知。

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `mobile/components/plan/AIGenerationSheet.tsx` | AI 生成底部确认面板 |
| `mobile/components/plan/MobileEditor.tsx` | 编辑器（已含 AI 生成横幅，见 PRD-M05） |
| `mobile/hooks/useStreamGeneration.ts` | SSE 流式消费 Hook（新建） |
| `services/generationService.ts` | 共享 API（SSE 流式读取） |

**复用的后端 API**（不做任何修改）：

| 端点 | 用途 |
|------|------|
| `POST /api/v1/plans/{id}/generate/{section_key}` | 单章节 SSE 流式生成 |
| `POST /api/v1/plans/{id}/generate/batch` | 批量生成（一次性提交所有章节） |
| `POST /api/v1/enterprises/{id}/risk-sources/generate` | AI 生成风险源 |
| `POST /api/v1/enterprises/{id}/resources/generate` | AI 生成应急资源 |

---

## 2. useStreamGeneration Hook

```typescript
// 文件：mobile/hooks/useStreamGeneration.ts

interface StreamGenerationState {
  isGenerating: boolean;
  content: string;                // 累积的 Markdown 内容
  error: string | null;
  progress: {
    current: number;              // 当前正在生成的章节序号（批量模式）
    total: number;                // 总章节数（批量模式）
    sectionName: string;          // 正在生成的章节名
  } | null;
}

interface UseStreamGenerationOptions {
  onChunk: (chunk: string) => void;     // 每 token 回调 → 追加到编辑器
  onComplete: (fullContent: string) => void;
  onError: (error: string) => void;
}

function useStreamGeneration(options: UseStreamGenerationOptions): {
  state: StreamGenerationState;
  generateSingle: (planId: string, sectionKey: string) => Promise<void>;
  generateBatch: (planId: string, sectionKeys: string[]) => Promise<void>;
  cancel: () => void;
};
```

**实现逻辑**：
1. `generateSingle` 调用 `POST /api/v1/plans/{id}/generate/{section_key}`
2. 使用 `fetch` + `ReadableStream` 消费 SSE 流：
   ```typescript
   const response = await fetch(url, { ... });
   const reader = response.body!.getReader();
   const decoder = new TextDecoder();
   while (true) {
     const { done, value } = await reader.read();
     if (done) break;
     const text = decoder.decode(value, { stream: true });
     // 解析 SSE "data: {...}" 行
     // 每 token 调用 options.onChunk(token)
   }
   ```
3. `generateBatch`：依次调用 `generateSingle`（顺序生成），每完成一个章节自动开始下一个
4. `cancel`：`AbortController.abort()` 中断 fetch

---

## 3. AIGenerationSheet 组件（底部确认面板）

**文件**：`mobile/components/plan/AIGenerationSheet.tsx`

```typescript
interface AIGenerationSheetProps {
  open: boolean;
  onClose: () => void;
  mode: "single" | "batch";
  planId: string;
  sectionKey?: string;            // single 模式
  sectionName?: string;
  enterpriseName: string;
  contextSummary: {
    riskCount: number;
    resourceCount: number;
    // 用于展示 AI 会注入的数据摘要
  };
  chapters?: Array<{              // batch 模式的章节列表
    key: string;
    name: string;
    aiGeneratable: boolean;
  }>;
  onGenerate: (selectedChapters: string[]) => void;
}
```

**视觉布局**（BottomSheet，高度 60%）：

```
┌──────────────────────────────────────┐
│           ▬▬▬▬                       │  ← 拖拽指示条
│                                      │
│  ✨ AI 智能生成                       │  ← text-h2
│                                      │
│  [模式] single / batch               │  ← SegmentedControl（条件显示）
│                                      │
│  ┌─ 📊 将使用的上下文 ──────────────┐│
│  │ 企业：西安宝岳空间科技有限公司    ││  ← Collapsible Card
│  │ 风险源：火灾(高)、触电(中)...     ││     bg-neutral-50
│  │ 应急资源：灭火器(10个)、...       ││     rounded-md
│  │                          [展开]   ││
│  └──────────────────────────────────┘│
│                                      │
│  生成风格（可选）                     │
│  ┌────────┐ ┌────────┐ ┌────────┐   │
│  │ 标准化  │ │  详细   │ │  简洁   │  │  ← SegmentedControl (3 项)
│  └────────┘ └────────┘ └────────┘   │
│                                      │
│  [batch 模式] 选择章节               │
│  ☑ 1. 总则                          │  ← Checkbox 列表
│  ☑ 2. 应急组织机构及职责             │     每项 h-12 flex
│  ☐ 3. 应急响应                      │     左侧 Checkbox + 章节名
│  ☑ 4. 后期处置                      │
│  ☐ 5. 应急保障                      │
│                                      │
│  ┌──────────────────────────────┐    │
│  │       ✨ 开始生成              │    │  ← Button primary lg fullWidth
│  └──────────────────────────────┘    │
│                                      │
└──────────────────────────────────────┘
```

**模式切换**：
- `mode="single"`：当前编辑的单个章节，隐藏章节选择列表
- `mode="batch"`：从章节导航页触发，显示所有 `aiGeneratable=true` 的章节，默认全选

**上下文卡片**：
- 默认折叠（显示 2 行摘要）
- 点击「展开」→ 显示完整列表（风险源名称 + 等级、资源名称 + 数量）
- 目的：用户确认 AI 不会「编造信息」

**生成风格**：
- SegmentedControl 3 项，默认选中「标准化」
- 作为 `style` 参数传递到 API（若 API 支持）
- 若 API 不支持，作为提示词附加文本注入

**开始生成**：
1. BottomSheet 关闭
2. `onGenerate(selectedChapters)` 回调触发
3. 父组件（PlanEditorScreen）调用 `useStreamGeneration.generateBatch()` 或 `generateSingle()`
4. 编辑器进入「监听模式」：切换为只读 + 显示生成横幅

---

## 4. 流式生成打字机效果

**在 MobileEditor（TipTap）中的实现**：

```
编辑器进入生成模式（readOnly=true）
  │
  ├─ 显示 AI 生成横幅（顶部固定 50px，含取消按钮）
  │
  ├─ onChunk(token) → 追加到编辑器的 Markdown 末尾
  │   ├─ 每 100ms 批量插入一次（避免 50ms 太频繁的 DOM 更新）
  │   └─ 自动滚动到末尾（使用 editor.commands.scrollIntoView()）
  │
  ├─ 用户取消 → abort() → 保留已生成内容 → 横幅变橙 → 退出生成模式
  │
  └─ onComplete → 横幅变绿「✓ 生成完成」→ 2s 后消失 → readOnly=false → 用户可继续编辑
```

**性能优化**：
- Token 批量插入：收集 100ms 内的 tokens，一次性 `editor.commands.insertContent()`
- 滚动优化：使用 `requestAnimationFrame` 包裹滚动操作
- 长文本时：使用虚拟滚动（TipTap 内部优化）或 `contentVisibility: auto`

---

## 5. 批量生成引导流程

```
章节导航页 → 点击底部「✨ 批量生成」
  │
  ├─ BottomSheet 弹出（mode="batch"）
  │   ├─ 用户勾选/取消章节
  │   ├─ 确认上下文数据
  │   └─ 点击「开始生成」
  │
  ├─ BottomSheet 关闭
  │
  ├─ 切换到第一个选中章节的编辑模式
  │   ├─ 显示横幅：「AI 正在撰写『第 1 章 总则』…  1/4」
  │   ├─ 流式输出
  │   └─ onComplete → 2s 后自动切换到下一个章节
  │
  ├─ 切换到第二个章节
  │   ├─ 横幅：「AI 正在撰写『第 2 章 组织职责』…  2/4」
  │   └─ ...（重复）
  │
  └─ 所有章节完成 → 底部 ProgressBar 消失 → Toast「4 个章节已生成完毕」
```

**进度条**（批量生成模式）：
- 编辑器底部 ProgressBar（determinate，value = current/total × 100）
- 右侧文字：`3/7 章节`

**暂停与取消**：
- 生成横幅右侧「取消」→ 弹出确认：「确定取消剩余生成？已生成的 3 个章节将保留。」→「取消」「确认取消」
- 确认后 → abort() + 切换回章节导航

---

## 6. AI 生成风险源 / 应急资源

在企业风险源/资源列表页的「AI 生成」入口（NavBar 右侧 `Sparkles` 图标）：

```
风险源列表页 → 点击右上角 ✨
  │
  ├─ BottomSheet 弹出
  │   ├─ 标题：「AI 智能识别风险源」
  │   ├─ 上下文确认卡片（企业名称 + 行业 + 经营范围）
  │   └─ 按钮「开始分析」
  │
  ├─ 调用 POST /api/v1/enterprises/{id}/risk-sources/generate
  │
  ├─ 流式展示结果（非编辑器模式，独立 BottomSheet 展示区）
  │   ├─ 每个识别的风险源以卡片形式逐张出现
  │   └─ 显示：「正在分析企业特征…」「识别潜在风险源…」
  │
  └─ 生成完成 → BottomSheet 显示结果清单
      ├─ 用户勾选要添加的项 → 点击「确认添加」
      └─ POST 批量创建 → 刷新列表
```

---

## 7. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M06-01 | 单章节 AI 生成 → 底部确认面板 → 上下文展示 → 开始生成 | 自动化 |
| M06-02 | SSE 流式打字机效果：逐字追加、自动滚动、200ms 内可见首 token | 自动化 |
| M06-03 | 生成完成 → 横幅变绿 → 2s 后消失 → 编辑器可编辑 | 自动化 |
| M06-04 | 生成中「取消」→ 保留已生成内容 → 横幅变橙 → 编辑器可编辑 | 自动化 |
| M06-05 | 批量生成：章节选择 → 依次生成 → 进度条 → 全部完成 | 自动化 |
| M06-06 | 批量生成中途「取消」→ 保留已完成章节 | 自动化 |
| M06-07 | AI 生成风险源 → 结果清单 → 勾选添加 → 列表刷新 | 自动化 |
| M06-08 | 上下文卡片展开/折叠 | 手动 |
| M06-09 | 视觉铁律通过 | 代码审查 |

---

> **下一文档**：PRD-M07 移动端导出、版本管理与设置
