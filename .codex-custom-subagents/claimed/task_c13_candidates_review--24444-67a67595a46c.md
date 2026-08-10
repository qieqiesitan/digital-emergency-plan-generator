# Codex Custom Subagents task handoff v1

Task: task_c13_candidates_review

## 任务：候选核对组件 CandidatesReview（易用性优化计划 C1 任务 C1-3）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C1-2 提交（cc2c48a）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：实现候选核对组件

新建 `frontend/src/pages/Onboarding/CandidatesReview.tsx`：

```tsx
import { Empty } from "antd";
import type { CandidateItem } from "@/types/onboarding";

interface Props {
  accepted: CandidateItem[];
  candidates: CandidateItem[];
  renderItem: (item: CandidateItem) => React.ReactNode;
  onAccept: (item: CandidateItem) => void;
  onModify: (item: CandidateItem) => void;
  onDelete: (item: CandidateItem) => void;
  onGenerateMore: () => void;
  generating?: boolean;
  sourceLabel?: string;
  generateMoreLabel?: string;
}

/** 候选核对：已采纳（绿）与新增候选（蓝）两区，支持增量生成 */
export default function CandidatesReview({
  accepted, candidates, renderItem, onAccept, onModify, onDelete,
  onGenerateMore, generating, sourceLabel, generateMoreLabel = "继续生成更多（不覆盖已采纳）",
}: Props) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#52c41a", marginBottom: 6 }}>
        ✓ 已采纳（{accepted.length} 条，已保存，AI 不会改动）
      </div>
      {accepted.length === 0 ? (
        <Empty description="暂无已采纳数据" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: "8px 0" }} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 }}>
          {accepted.map(item => (
            <div key={item._key} style={{ border: "1px solid #d9f7be", background: "#f6ffed", borderRadius: 8, padding: 8 }}>
              {renderItem(item)}
            </div>
          ))}
        </div>
      )}

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        新增候选{sourceLabel ? `（${sourceLabel}）` : ""}（{candidates.length} 条）
      </div>
      {candidates.length === 0 ? (
        <Empty description="暂无候选，可输入概况生成或导入文件" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: "8px 0" }} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 }}>
          {candidates.map(item => (
            <div key={item._key} style={{ border: "1px solid #1677ff", background: "#f0f7ff", borderRadius: 8, padding: 8 }}>
              {renderItem(item)}
              <div style={{ marginTop: 6, display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <span style={{ color: "#1677ff", cursor: "pointer" }} onClick={() => onModify(item)}>修改</span>
                <span style={{ color: "#52c41a", fontWeight: 600, cursor: "pointer" }} onClick={() => onAccept(item)}>采纳 ✓</span>
                <span style={{ color: "#999", cursor: "pointer" }} onClick={() => onDelete(item)}>删除</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onGenerateMore}
        disabled={generating}
        style={{ width: "100%", padding: 6, cursor: generating ? "not-allowed" : "pointer" }}
      >
        {generating ? "生成中…" : generateMoreLabel}
      </button>
    </div>
  );
}
```

要求：
- 新增行 ≤100 字符；eslint 无错误（无 no-explicit-any）。
- `CandidateItem` 类型来自 `@/types/onboarding`（当前 _key 必填；若需调整在 C1-4 处理，本任务按现状使用）。
- 按钮用原生 button 而非 antd Button 亦可，保持一致即可。

### 步骤 2：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误。

### 步骤 3：Commit

```bash
git add frontend/src/pages/Onboarding/CandidatesReview.tsx
git commit -m "feat(onboarding): candidates review component with incremental generation"
```

## 上下文

- 这是引导页各数据步骤共用的候选核对组件（C1-4/C1-5 会使用）。
- 语义：已采纳区绿色只读（AI 不会改动），新增候选区蓝色可采纳/修改/删除，底部「继续生成更多」。

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述实现
2. tsc 验证
3. 提交
4. 自审：两区布局/交互正确？props 契约清晰？无 any？新增行 ≤100？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc 结果、提交 SHA、自审发现
