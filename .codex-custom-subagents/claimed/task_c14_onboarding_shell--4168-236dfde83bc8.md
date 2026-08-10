# Codex Custom Subagents task handoff v1

Task: task_c14_onboarding_shell

## 任务：引导页骨架 + 第 1/2 步（易用性优化计划 C1 任务 C1-4）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 C1-3 提交（a9d1777）。启动时 `cd` 到该目录，git status 确认干净。

### 背景

- `frontend/src/pages/Onboarding/OnboardingPage.tsx` 是占位（C1-1 创建），本任务重写为完整骨架。
- `frontend/src/components/enterprise/EnterpriseInfoCards.tsx` 已就绪（C1-2）。
- 后端接口：GET /enterprises/{id}/completion、POST /onboarding/candidates（org 模块）。
- 本任务实现：OnboardingPage 骨架（左侧步骤列表 + 右侧内容）、StepEnterprise（第 1 步）、StepOrg（第 2 步）。

### 步骤 1：重写 OnboardingPage 骨架

`frontend/src/pages/Onboarding/OnboardingPage.tsx`（替换占位）：

```tsx
import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button, Layout } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import StepEnterprise from "./StepEnterprise";
import StepOrg from "./StepOrg";
import StepRiskChemical from "./StepRiskChemical";
import StepResources from "./StepResources";
import StepSurrounding from "./StepSurrounding";
import StepGenerate from "./StepGenerate";

const STEPS = [
  { key: "enterprise", label: "企业信息", component: StepEnterprise },
  { key: "org", label: "组织架构", component: StepOrg },
  { key: "risk", label: "风险与危化品", component: StepRiskChemical },
  { key: "resources", label: "应急资源", component: StepResources },
  { key: "surrounding", label: "周边环境", component: StepSurrounding },
  { key: "generate", label: "生成并导出预案", optional: true, component: StepGenerate },
];

export default function OnboardingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const enterpriseId = searchParams.get("enterprise_id");
  const [current, setCurrent] = useState(0);
  const [completed, setCompleted] = useState<Set<string>>(new Set());

  const { data: completion } = useQuery({
    queryKey: ["completion", enterpriseId],
    queryFn: () => getEnterpriseCompletion(enterpriseId!),
    enabled: !!enterpriseId,
  });

  if (!enterpriseId) {
    return <div style={{ padding: 48 }}>请先选择企业（缺少 enterprise_id 参数）</div>;
  }

  const Step = STEPS[current].component;

  return (
    <Layout style={{ minHeight: "100vh", background: "#fff" }}>
      <Layout.Sider width={220} theme="light" style={{ borderRight: "1px solid #f0f0f0", padding: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>完成企业数据</div>
        {STEPS.map((s, i) => (
          <div
            key={s.key}
            onClick={() => setCurrent(i)}
            style={{
              padding: "6px 10px", borderRadius: 6, cursor: "pointer", marginBottom: 2,
              background: i === current ? "#e6f4ff" : "transparent",
              fontWeight: i === current ? 600 : 400,
              color: completed.has(s.key) ? "#52c41a" : s.optional ? "#fa8c16" : "#333",
            }}
          >
            {completed.has(s.key) ? "✓ " : i === current ? "▶ " : ""}{i + 1} {s.label}
            {s.optional && <span style={{ fontSize: 10, background: "#fff7e6", borderRadius: 4, padding: "0 4px", marginLeft: 4 }}>可选</span>}
          </div>
        ))}
        <div style={{ marginTop: 16, fontSize: 12, color: "#999" }}>
          🔒 进度自动保存
          <div style={{ marginTop: 8 }}>
            <Button size="small" onClick={() => navigate("/dashboard")}>稍后继续</Button>
          </div>
        </div>
      </Layout.Sider>
      <Layout.Content style={{ padding: 24 }}>
        <Step
          enterpriseId={enterpriseId}
          onDone={() => {
            const next = new Set(completed);
            next.add(STEPS[current].key);
            setCompleted(next);
            if (current < STEPS.length - 1) setCurrent(current + 1);
          }}
          onPrev={() => current > 0 && setCurrent(current - 1)}
        />
      </Layout.Content>
    </Layout>
  );
}
```

（Step 组件统一 props：`{ enterpriseId: string; onDone: () => void; onPrev: () => void }`。）

### 步骤 2：第 1 步 StepEnterprise

新建 `frontend/src/pages/Onboarding/StepEnterprise.tsx`：

```tsx
import { Button } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";

interface Props { enterpriseId: string; onDone: () => void; onPrev: () => void; }

export default function StepEnterprise({ enterpriseId, onDone }: Props) {
  const queryClient = useQueryClient();
  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });
  return (
    <div style={{ maxWidth: 720 }}>
      <h3>企业信息</h3>
      <p style={{ color: "#666", fontSize: 13 }}>先确认企业是谁——这是整份预案的事实基础</p>
      <EnterpriseInfoCards
        enterprise={enterprise}
        onSaved={async () => {
          queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
          queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
        }}
      />
      <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
        <Button type="primary" onClick={onDone}>标记完成，下一步 →</Button>
      </div>
    </div>
  );
}
```

（若企业不存在，可显示创建企业引导：`onDone` 前需保证有企业——本步在企业已存在场景使用；若 enterprise 为 null 显示「企业不存在或已删除」+ 返回按钮。）

### 步骤 3：第 2 步 StepOrg（AI 生成 + 成员表格）

新建 `frontend/src/pages/Onboarding/StepOrg.tsx`：

```tsx
import { useState } from "react";
import { Button, Input, Table, message } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateOrgStructure } from "@/services/enterpriseService";
import api from "@/services/api";
import type { OrgGroup } from "@/types/enterprise";

interface Props { enterpriseId: string; onDone: () => void; onPrev: () => void; }

export default function StepOrg({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<OrgGroup[]>([]);
  const [generating, setGenerating] = useState(false);
  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });
  const accepted = enterprise?.org_structure || [];

  const generate = async () => {
    setGenerating(true);
    try {
      const r = await api.post("/onboarding/candidates", {
        enterprise_id: enterpriseId, module: "org", overview,
      });
      setCandidates(r.data.data.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const saveMut = useMutation({
    mutationFn: (groups: OrgGroup[]) => updateOrgStructure(enterpriseId, groups),
    onSuccess: () => {
      message.success("组织架构已保存");
      queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    },
  });

  const adoptAll = () => {
    const merged = [...accepted];
    candidates.forEach(g => {
      const key = g.group_key || `g-${merged.length}`;
      if (!merged.some(x => x.group_key === key)) merged.push({ ...g, group_key: key });
    });
    saveMut.mutate(merged);
    setCandidates([]);
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <h3>组织架构</h3>
      <p style={{ color: "#666", fontSize: 13 }}>突发事件谁来指挥、谁负责什么——预案「应急组织机构及职责」章节直接用它</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea rows={2} value={overview} onChange={e => setOverview(e.target.value)} placeholder="企业概况（可留空，AI 按行业/规模自动生成）" />
        <Button type="primary" loading={generating} onClick={generate}>AI 生成候选</Button>
      </div>
      {candidates.length > 0 && (
        <>
          {candidates.map(g => (
            <div key={g.group_key} style={{ border: "1px solid #1677ff", borderRadius: 8, padding: 10, marginBottom: 8, background: "#f0f7ff" }}>
              <b>{g.group_name}</b>
              <div style={{ color: "#666", fontSize: 12, margin: "4px 0" }}>{g.responsibilities}</div>
              <Table
                size="small" pagination={false} rowKey={(_, i) => `m-${i}`}
                dataSource={g.members || []}
                columns={[
                  { title: "角色", dataIndex: "role" },
                  { title: "姓名", dataIndex: "name", render: (v: string) => v || <span style={{ color: "#fa8c16" }}>待填</span> },
                  { title: "公司职位", dataIndex: "position", render: (v: string) => v || "-" },
                  { title: "电话", dataIndex: "phone", render: (v: string) => v || <span style={{ color: "#fa8c16" }}>待填</span> },
                ]}
              />
            </div>
          ))}
          <Button type="primary" onClick={adoptAll} style={{ marginBottom: 12 }}>全部采纳（姓名电话请到企业详情补充）</Button>
        </>
      )}
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={onDone}>标记完成，下一步 →</Button>
      </div>
    </div>
  );
}
```

（注意：`api` 的 `e?.response?.data?.detail` 访问需用 `as any` 或类型化——用 `catch (e: unknown)` + 类型守卫避免 no-explicit-any。）

### 步骤 4：为第 3-6 步创建最小占位（本任务不实现，避免 tsc 报错）

新建 `frontend/src/pages/Onboarding/StepRiskChemical.tsx`、`StepResources.tsx`、`StepSurrounding.tsx`、`StepGenerate.tsx`（各一个最小占位，接受同一 Props 接口）：

```tsx
interface Props { enterpriseId: string; onDone: () => void; onPrev: () => void; }
export default function StepRiskChemical({ enterpriseId, onDone, onPrev }: Props) {
  return <div style={{ maxWidth: 760 }}><h3>风险与危化品</h3><p style={{ color: "#666" }}>开发中</p></div>;
}
```

### 步骤 5：tsc + eslint 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/pages/Onboarding/`

预期：无类型/ESLint 错误（无 no-explicit-any）。

### 步骤 6：Commit

```bash
git add frontend/src/pages/Onboarding/
git commit -m "feat(onboarding): page skeleton and step 1-2 (enterprise info, org structure)"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 enterpriseService.ts（getEnterprise/updateOrgStructure）、api.ts、types/enterprise.ts 确认签名
2. 按步骤实现
3. tsc + eslint 验证
4. 提交
5. 自审：骨架步骤列表/进度/稍后继续可用？第 1 步保存后 completion 刷新？第 2 步 AI 生成/采纳/成员表格可用？无 any？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
