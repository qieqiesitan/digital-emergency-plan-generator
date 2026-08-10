# Codex Custom Subagents task handoff v1

Task: task_c16_import_completion

## 任务：导入抽屉 + 工作台完成度卡片（易用性优化计划 C1 任务 C1-6）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C1-5 提交（80bf721）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：ImportDrawer（单文件 + 资料包）

新建 `frontend/src/pages/Onboarding/ImportDrawer.tsx`：

```tsx
import { useState } from "react";
import { Drawer, Upload, message } from "antd";
import { importOnboardingFile, importOnboardingBatch } from "@/services/onboardingService";

interface Props {
  enterpriseId: string;
  open: boolean;
  onClose: () => void;
  onImported: (items: unknown[]) => void;
}

export default function ImportDrawer({ enterpriseId, open, onClose, onImported }: Props) {
  const [uploading, setUploading] = useState(false);
  return (
    <Drawer title="导入现有数据" open={open} onClose={onClose} width={520}>
      <p style={{ color: "#666", fontSize: 13 }}>
        支持 .xlsx / .csv / .docx / .pdf，AI 自动提取为候选供核对；也可上传多个文件作为「资料包」自动分流。
      </p>
      <Upload.Dragger
        multiple
        accept=".xlsx,.csv,.docx,.pdf,.txt"
        beforeUpload={async (file) => {
          setUploading(true);
          try {
            const result = await importOnboardingBatch(enterpriseId, [file as unknown as File]);
            const items = result.flatMap(r => r.candidates || []);
            onImported(items);
            message.success(`已提取 ${items.length} 条候选`);
          } catch (e: unknown) {
            message.error((e as Error)?.message || "导入失败");
          } finally {
            setUploading(false);
          }
          return false;
        }}
        showUploadList={false}
      >
        <p>点击或拖拽文件到这里</p>
        <p style={{ color: "#999", fontSize: 12 }}>
          {uploading ? "AI 分析提取中…" : "资料包（多文件）将自动识别并分流到各步骤"}
        </p>
      </Upload.Dragger>
    </Drawer>
  );
}
```

（错误提取用 `axios.isAxiosError` 取 `response.data.detail` 优先，回退 message。）

### 步骤 2：CompletionCard（工作台完成度卡片）

新建 `frontend/src/pages/Dashboard/CompletionCard.tsx`：

```tsx
import { useNavigate } from "react-router-dom";
import { Button, Progress } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useCurrentEnterprise } from "@/contexts/EnterpriseContext";
import { getEnterpriseCompletion } from "@/services/onboardingService";

export default function CompletionCard() {
  const navigate = useNavigate();
  const { currentEnterpriseId } = useCurrentEnterprise();
  const { data } = useQuery({
    queryKey: ["completion", currentEnterpriseId],
    queryFn: () => getEnterpriseCompletion(currentEnterpriseId!),
    enabled: !!currentEnterpriseId,
  });
  if (!data) return null;
  const undone = (data.modules || []).filter(m => !m.done);
  return (
    <div style={{ border: "1px solid #1677ff", borderRadius: 8, padding: 16, background: "#f0f7ff", marginBottom: 24 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>📋 企业数据完成度 {data.percent}%</div>
      <Progress percent={data.percent} showInfo={false} strokeColor="#1677ff" />
      <div style={{ fontSize: 13, color: "#555", margin: "8px 0" }}>
        {undone.length === 0
          ? "已完成全部数据模块，可以生成预案了"
          : `未完成：${undone.map(m => m.label).join("、")}`}
      </div>
      <Button
        type="primary"
        onClick={() => navigate(undone.length === 0 ? `/plans/new?enterprise_id=${currentEnterpriseId}` : `/onboarding?enterprise_id=${currentEnterpriseId}`)}
      >
        {undone.length === 0 ? "去生成预案" : "继续补数据"}
      </Button>
    </div>
  );
}
```

（先读 `frontend/src/contexts/EnterpriseContext.tsx` 确认 `useCurrentEnterprise` 导出；若无该 hook 用现有企业上下文模式。）

### 步骤 3：Dashboard 嵌入卡片

`frontend/src/pages/Dashboard/DashboardPage.tsx`：在统计卡之后、快捷新建之前插入 `<CompletionCard />`（import 组件）。

### 步骤 4：引导页接入 ImportDrawer（可选增强）

若 `OnboardingPage` 或各 Step 有「导入现有数据」入口位，可先不接（C1 计划中导入抽屉由步骤 3/4/5 使用）；本任务只创建组件与工作台卡片，引导页接入由后续迭代完成。保持 ImportDrawer 组件可用即可。

### 步骤 5：tsc + eslint 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/pages/Onboarding/ImportDrawer.tsx src/pages/Dashboard/CompletionCard.tsx src/pages/Dashboard/DashboardPage.tsx`

预期：无类型/ESLint 错误（无 no-explicit-any）。

### 步骤 6：Commit

```bash
git add frontend/src/pages/Onboarding/ImportDrawer.tsx frontend/src/pages/Dashboard/CompletionCard.tsx frontend/src/pages/Dashboard/DashboardPage.tsx
git commit -m "feat(onboarding): import drawer and dashboard completion card"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 EnterpriseContext.tsx / DashboardPage.tsx 确认接入点
2. 按步骤实现
3. tsc + eslint 验证
4. 提交
5. 自审：ImportDrawer 可用（上传/提取/反馈）？CompletionCard 显示/跳转正确（未完成→补数据、完成→生成预案）？Dashboard 嵌入位置正确？无 any？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
