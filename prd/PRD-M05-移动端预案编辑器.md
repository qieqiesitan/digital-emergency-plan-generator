# PRD-M05：移动端预案编辑器

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00, PRD-M01, PRD-05（桌面端预案编辑器）, PRD-04（AI 生成引擎） | **关联文档**：移动端设计方案 §5.8~5.11

---

## 1. 模块概述

预案编辑器是移动端最核心的界面。桌面端采用章节树 + 富文本编辑器并排布局，移动端因屏幕限制改为**双态切换模式**：章节导航态 ↔ 编辑态。用户在章节导航中选择目标，全屏进入编辑，编辑完成返回导航。

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `mobile/screens/PlanCardsScreen.tsx` | 企业卡片式预案总览 |
| `mobile/screens/EnterprisePlanListScreen.tsx` | 某企业预案列表 |
| `mobile/screens/PlanCreateScreen.tsx` | 新建预案（类型选择 + 标题 + 事故类型） |
| `mobile/screens/PlanEditorScreen.tsx` | 预案编辑器主页面（双态切换） |
| `mobile/components/plan/ChapterTree.tsx` | 章节导航列表 |
| `mobile/components/plan/MobileEditor.tsx` | TipTap 移动端编辑器封装 |
| `mobile/components/plan/EditorToolbar.tsx` | 编辑工具栏（键盘上方固定） |
| `mobile/components/plan/PlanCard.tsx` | 预案列表卡片 |
| `mobile/components/plan/AIGenerationSheet.tsx` | AI 生成底部面板 |
| `services/planService.ts` | 共享 API |

**复用的后端 API**（不做任何修改）：

| 端点 | 用途 |
|------|------|
| `GET/POST /api/v1/plans` | 预案列表 / 创建 |
| `GET/PUT/DELETE /api/v1/plans/{id}` | 预案详情 / 更新 / 删除 |
| `GET/PUT /api/v1/plans/{id}/sections/{key}` | 章节读写 |
| `GET /api/v1/templates` | 模板列表 |
| `GET /api/v1/templates/{id}` | 模板详情（含章节结构） |

---

## 2. 页面详案

### 2.1 PlanCardsScreen（预案总览卡片）

**文件**：`mobile/screens/PlanCardsScreen.tsx`

**路由**：`/m/plans`

**布局**：2 列卡片网格

```
┌──────────────────────────────────────┐
│ ← 预案管理                           │  ← NavBar
├──────────────────────────────────────┤
│                                      │
│  ┌─────────────┐ ┌─────────────┐    │
│  │ 西安宝岳空间 │ │ 陕西华安化工 │    │  ← EnterpriseCard（2 列 Grid）
│  │ 科技有限公司 │ │ 有限公司     │    │
│  │             │ │             │    │
│  │ 综合 1      │ │ 综合 0      │    │  ← 预案类型计数
│  │ 专项 2      │ │ 专项 1      │    │
│  │ 现场 1      │ │ 现场 1      │    │
│  │             │ │             │    │
│  │ [+ 新建预案]│ │ [+ 新建预案]│    │
│  └─────────────┘ └─────────────┘    │
│                                      │
│  ┌─────────────┐                    │
│  │ 陕西矿业开发 │                    │
│  │ ...          │                    │
│  └─────────────┘                    │
│                                      │
└──────────────────────────────────────┘
```

**实现要点**：
- Grid: `grid grid-cols-2 gap-md px-md`
- 每张卡片：`bg-white rounded-md shadow-card p-md`
- 企业名称：`text-h3`，2 行截断
- 预案计数：3 行每行 `flex justify-between`，左侧 Badge（类型色），右侧数字
  - 综合：Badge info
  - 专项：Badge warning
  - 现场：Badge success
- 「+ 新建预案」按钮：`Chip` + `Plus` 图标，Primary 50 背景，点击 → `navigate("/m/plans/new?enterprise_id=xxx")`
- 卡片主体点击 → `navigate("/m/enterprises/:id/plans")`
- 空状态：EmptyState「暂无企业档案」

---

### 2.2 EnterprisePlanListScreen（企业专属预案列表）

**文件**：`mobile/screens/EnterprisePlanListScreen.tsx`

**路由**：`/m/enterprises/:id/plans`

**布局**：

```
┌──────────────────────────────────────┐
│ ← [企业名] 的预案                    │
├──────────────────────────────────────┤
│ [全部] [综合] [专项] [现场处置]       │  ← Chip 行 横向滚动 筛选
├──────────────────────────────────────┤
│                                      │
│ ┌─ 综合应急预案 ───────────────────┐│  ← PlanCard
│ │ 西安宝岳空间科技  ·  2小时前     ││
│ │ [综合] [已完成 ● ]               ││
│ └──────────────────────────────────┘│
│                                      │
│ ┌─ 火灾专项应急预案 ───────────────┐│
│ │ ...  [专项] [草稿 ○ ]            ││
│ └──────────────────────────────────┘│
│                                      │
│                     [◎]              │  ← FAB
└──────────────────────────────────────┘
```

**筛选**：Chip 行，`selected` 态蓝色边框。点击切换显示类型。

**PlanCard**：

```typescript
interface PlanCardProps {
  plan: {
    id: string;
    title: string;
    planType: "comprehensive" | "special" | "onsite";
    status: "draft" | "generating" | "completed";
    updatedAt: string;
  };
  onPress: () => void;
}
```

- 布局：`h-[80px]`，Card pressable
- 标题：`text-h3` Semibold
- 副标题：企业名 + `·` + 相对时间（`text-caption` Neutral 400）
- 底部：类型 Badge + 状态指示器
  - completed：绿色圆点 `●` +「已完成」
  - generating：蓝色圆点 `●` +「生成中」+ Spinner sm 动画
  - draft：灰色圆点 `●` +「草稿」
- 点击 → `navigate("/m/plans/:id/edit")`
- 左滑 → 删除（红色）

---

### 2.3 PlanCreateScreen（新建预案）

**文件**：`mobile/screens/PlanCreateScreen.tsx`

**路由**：`/m/plans/new?enterprise_id=xxx&type=comprehensive|special|onsite`

**布局**（单页完成，分段）：

```
┌──────────────────────────────────────┐
│ ← 新建预案                           │
├──────────────────────────────────────┤
│                                      │
│  选择预案类型                         │  ← text-h2
│                                      │
│  ┌─ 📋 综合应急预案 ───────────────┐│  ← 3 张可选卡片
│  │   从企业信息自动生成完整框架     ││     点击选中：border-primary-500
│  └──────────────────────────────────┘│     bg-primary-50
│                                      │
│  ┌─ 🎯 专项应急预案 ───────────────┐│
│  │   针对特定事故类型               ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 🏭 现场处置方案 ───────────────┐│
│  │   一线操作卡片式处置步骤         ││
│  └──────────────────────────────────┘│
│                                      │
│  [条件] 选择事故类型（专项/现场）     │
│  ┌──────────────────────────────┐    │
│  │ [火灾] [触电] [中毒] [机械]   │    │  ← Chip 多选（从企业风险源提取）
│  │ [+ 若无 → 先去添加风险源]      │    │     无风险源时显示空态提示
│  └──────────────────────────────┘    │
│                                      │
│  预案标题                             │
│  ┌──────────────────────────────┐    │
│  │ 西安宝岳空间科技 综合应急预案  │    │  ← 预填默认标题 + 可编辑
│  └──────────────────────────────┘    │
│                                      │
│  所属企业                     ▼      │  ← 若从 query param 有 enterprise_id
│  西安宝岳空间科技有限公司             │     自动填充，否则 SelectSheet
│                                      │
│  ┌──────────────────────────────┐    │
│  │          创建预案             │    │  ← Button primary lg fullWidth
│  └──────────────────────────────┘    │     sticky bottom
└──────────────────────────────────────┘
```

**预填标题逻辑**：
```typescript
const defaultTitle = selectedType === "comprehensive"
  ? `${enterpriseName} 综合应急预案`
  : selectedType === "special"
  ? `${enterpriseName} ${selectedAccidentType}专项应急预案`
  : `${enterpriseName} ${selectedAccidentType}现场处置方案`;
```

**创建逻辑**：
1. `POST /api/v1/plans`（body: `{ enterprise_id, template_id, plan_type, title, accident_type }`）
2. 后端自动绑定对应模板的章节结构 → 返回预案 ID
3. `navigate("/m/plans/:newId/edit")`

---

### 2.4 PlanEditorScreen（预案编辑器 — 双态切换）

**文件**：`mobile/screens/PlanEditorScreen.tsx`

**路由**：`/m/plans/:id/edit`

这是全系统最复杂的 Screen。实现为**两个状态**的单页面：

```typescript
type EditorMode = "navigate" | "edit";

interface PlanEditorState {
  mode: EditorMode;
  planId: string;
  chapters: ChapterNode[];                     // 章节树数据
  selectedChapter: ChapterNode | null;         // 当前编辑的章节
  sectionContent: Record<string, string>;      // key → Markdown 内容
}
```

---

#### 2.4.1 状态 A：章节导航模式（EditorMode = "navigate"）

```
┌──────────────────────────────────────┐
│ ← 综合应急预案               ⋮       │  ← NavBar: 预案标题 + more-horizontal
├──────────────────────────────────────┤
│                                      │
│ ○ 批准页                             │  ← 章节列表（ChapterTree）
│ ○ 1. 总则                            │
│ ✓ 2. 应急组织机构及职责               │  ← ✓ = 已完成 (check-circle, Success)
│   ○ 2.1 应急指挥部                   │     缩进 16px
│   ✓ 2.2 应急办公室                   │
│ ★ 3. 应急响应                        │  ← ★ = AI 已生成未审核 (sparkles, Info)
│   ○ 3.1 预警分级                     │
│   ○ 3.2 响应启动                     │
│ ! 4. 后期处置                        │  ← ! = 必填但为空 (alert-circle, Warning)
│ ○ 5. 应急保障                        │
│ ○ 6. 附件                            │
│                                      │
├──────────────────────────────────────┤
│ [✨ 批量生成]   [⬇ 导出]   [⏱ 版本] │  ← 底部工具栏
└──────────────────────────────────────┘
```

**ChapterTree 组件**：

```typescript
interface ChapterNode {
  key: string;
  title: string;
  children?: ChapterNode[];
  aiGeneratable: boolean;
  required: boolean;
  level: number;              // 0=父, 1+=子 (用于缩进)
}

interface ChapterTreeProps {
  chapters: ChapterNode[];
  sectionStates: Record<string, {
    hasContent: boolean;
    aiGenerated: boolean;
  }>;
  selectedKey: string | null;
  onSelect: (chapter: ChapterNode) => void;
}
```

- 每行高度：48px
- 子章节缩进：`level * 16px`
- 折叠/展开箭头（父章节左侧）：`ChevronRight` 旋转 90° 表示展开，0° 表示折叠
- 右侧状态图标：
  - `hasContent=true` → `CheckCircle` 18px Success
  - `aiGenerated=true` → `Sparkles` 18px Info
  - `required=true && !hasContent` → `AlertCircle` 18px Warning
  - 其他 → `Circle` 18px Neutral 300
- 点击 → `onSelect(chapter)` → 切换到编辑模式

**底部工具栏**：
- 三按钮水平排列，高度 56px，`bg-white` + 顶部 `1px Neutral 100` 边框
- 「✨ 批量生成」：`flex-1`，Button variant="secondary" size="md" icon=`Sparkles`
- 「⬇ 导出」：44×44，icon=`Download`
- 「⏱ 版本」：44×44，icon=`GitBranch`

---

#### 2.4.2 状态 B：章节编辑模式（EditorMode = "edit"）

```
┌──────────────────────────────────────┐
│ ← 2. 应急组织机构及职责       ✨     │  ← NavBar: 章节标题 + AI生成按钮
├──────────────────────────────────────┤
│ [AI 生成横幅: 撰写中… 🔄]    [取消]  │  ← 条件显示（generating 时）
│                                      │
│ 2.1 应急指挥部                        │  ← 富文本编辑区（MobileEditor）
│                                      │
│ 总指挥由企业主要负责人担任，副总指挥  │
│ 由分管安全工作的副总经理担任。应急指  │
│ 挥部下设应急办公室，负责日常应急管理  │
│ 工作。                               │
│                                      │
│ 2.2 应急办公室                        │
│                                      │
│ 应急办公室设在安全管理部，负责...     │
│                                      │
├──────────────────────────────────────┤
│ [B] [I] [H] [≡] [🔗] [↩] [↪]       │  ← EditorToolbar (键盘上方固定)
├──────────────────────────────────────┤
│ 字数：1,234    自动保存中…            │  ← 状态栏
└──────────────────────────────────────┘
```

**MobileEditor 组件**：

```typescript
interface MobileEditorProps {
  content: string;                    // Markdown
  onChange: (markdown: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  onAIGenerate?: () => void;
}
```

- 基于 TipTap（ProseMirror），与桌面端共享编辑器内核
- 触摸优化：
  - 最小点击区 44×44pt 用于各类节点（链接、列表 marker）
  - 双击标题节点 → 在 H2/H3/Paragraph 之间循环
  - 长按 → 系统选择菜单
- Placeholder：章节级别的 placeholder（如「点击开始编写或使用 AI 生成本章内容」）
- 自动保存：
  - 内容变更 3 秒防抖 → `PUT /api/v1/plans/{id}/sections/{key}`
  - 网络断开 → 存 IndexedDB（`draftStore.addDraft`）
  - 联网后自动同步

**EditorToolbar 组件**：

```typescript
interface EditorToolbarProps {
  editor: Editor | null;
  visible: boolean;        // 键盘可见时显示
}
```

- 水平排列，固定于键盘上方
- 高度：44px，`bg-white` + 顶部细线
- 按钮（从左到右）：
  - **B** — Bold（`Bold` 图标，激活态 Primary 600 背景）
  - **I** — Italic（`Italic` 图标）
  - **H** — Heading（`Heading` 图标，点击在 H2/H3/P 之间循环）
  - **≡** — Bullet List（`List` 图标）
  - **🔗** — Link（`Link` 图标，点击弹出链接输入框）
  - **↩** — Undo（`Undo` 图标）
  - **↪** — Redo（`Redo` 图标）
- 每个按钮：36×36px 点击区，间距 4px（图标区 + padding 够 44px）
- 编辑器未聚焦时（keyboard 隐藏时）：工具栏不显示

**键盘联动**：
- `useKeyboard` Hook 监听 `visualViewport` 变化
- 键盘弹出 → `EditorToolbar visible=true` + 编辑区 padding-bottom 增加工具栏高度
- 键盘收起 → `EditorToolbar visible=false`

**AI 生成横幅**（生成中）：
- 高度：50px，`bg-primary-50` 背景 + `border-b border-primary-100`
- 左侧：`Loader2` 旋转 Spinner sm
- 文字：「AI 正在撰写『应急组织机构及职责』…」（`text-body-sm` Primary 600）
- 右侧：「取消」文字按钮（`text-danger`）
- 生成完成：横幅变绿「✓ 生成完成」，2 秒后自动消失
- 取消：横幅变橙「已取消，已保留已生成内容」，2 秒后消失

---

## 3. PlanEditorScreen 数据流

```
PlanEditorScreen mount
  │
  ├─ 1. useQuery(["plan", planId]) → GET /api/v1/plans/{id}
  │   → 获取 plan 元数据 + 状态
  │
  ├─ 2. useQuery(["plan-sections", planId]) → GET 所有章节
  │   → 构建 chapters 树 + sectionStates
  │
  └─ 3. 渲染：根据 mode 显示章节导航或编辑器

章节导航模式 → 点击章节
  │
  ├─ setMode("edit")
  ├─ setSelectedChapter(chapter)
  ├─ useQuery(["section", planId, chapter.key]) → GET 章节内容
  └─ 内容注入 MobileEditor

编辑模式 → 点击返回
  │
  ├─ 触发自动保存（防抖中的立即保存）
  ├─ setMode("navigate")
  └─ 刷新 sectionStates（query invalidation）
```

**章节内容缓存策略**：
- React Query `staleTime: 60_000`（1 分钟）
- 但编辑器内部有本地状态优先机制：编辑中内容不覆盖本地状态

---

## 4. 关键交互细节

### 4.1 草稿保存与恢复

```
用户编辑 → 3s 防抖 → PUT API
                    ↓ 失败（离线）
                  draftStore.addDraft({
                    planId, sectionKey, content, updatedAt
                  })
                    ↓ 网络恢复
                  useOfflineSync Hook → 遍历 pendingDrafts → PUT API
```

**冲突解决**（联网同步时服务端时间戳 > 本地草稿时间戳）：
- 弹出 Dialog：「服务端内容已更新（张三，2 分钟前）。保留您的版本还是使用服务端版本？」
  - 「保留我的」→ PUT 本地内容
  - 「使用服务端」→ GET 服务端内容，丢弃本地

### 4.2 批量生成跳转

底部工具栏「批量生成」→ BottomSheet 弹出 → 章节选择 → 确认 → 依次逐个生成。详见 PRD-M06。

### 4.3 导出与版本

底部工具栏「导出」→ `navigate("/m/plans/:id/preview")`
底部工具栏「版本」→ `navigate("/m/plans/:id/versions")`

---

## 5. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M05-01 | 预案总览卡片 2 列网格正确渲染 | 自动化 |
| M05-02 | 企业卡片预案计数正确 | 自动化 |
| M05-03 | 企业专属预案列表 + 类型 Chip 筛选 | 自动化 |
| M05-04 | 新建预案：类型卡片选择 + 事故类型 Chip + 标题预填 | 自动化 |
| M05-05 | 新建预案提交 → 后端创建 → 跳转编辑器 | 自动化 |
| M05-06 | 章节导航：树形缩进 + 折叠/展开 + 状态图标 | 自动化 |
| M05-07 | 点击章节 → 切换编辑模式 → 内容加载 | 自动化 |
| M05-08 | MobileEditor 富文本编辑（加粗、斜体、标题、列表） | 手动 |
| M05-09 | 编辑器内容变更 → 3s 自动保存 → 章节状态更新 | 自动化 |
| M05-10 | 离线编辑 → IndexedDB 存储 → 联网后同步 | 手动（断网） |
| M05-11 | EditorToolbar 键盘弹出/收起正确联动 | 真机测试 |
| M05-12 | 底部工具栏 3 按钮功能正确 | 自动化 |
| M05-13 | 视觉铁律通过 | 代码审查 |

---

> **下一文档**：PRD-M06 移动端 AI 生成体验
