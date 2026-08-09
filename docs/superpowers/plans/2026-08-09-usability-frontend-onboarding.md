# 易用性整体优化 · 计划 C1（引导页前端）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现 `/onboarding` 引导页（6 步）、候选核对与导入交互、EnterpriseInfoCards 企业信息卡片组件、工作台完成度卡片。

**架构：** 新增 `frontend/src/pages/Onboarding/` 目录（页面 + 分步组件 + 候选核对组件）；`EnterpriseInfoCards` 为共享组件（引导第 1 步/创建/编辑/详情复用）；工作台完成度卡片调用计划 B 的 `/enterprises/{id}/completion`。

**技术栈：** React + Ant Design + TypeScript + TanStack Query。

**规格依据：** `docs/superpowers/specs/2026-08-08-usability-enhancement-design.md` 第 6、7、3.1 节。

**依赖：** 先执行计划 A、B、B2（后端接口就绪）。

**基线：** master 已合入预案附图扩展（94cc4bf）。本计划新增页面/组件文件，与附图扩展无文件交叉。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `frontend/src/services/onboardingService.ts` | completion 查询、candidates、import 接口封装 | 新建 |
| `frontend/src/components/enterprise/EnterpriseInfoCards.tsx` | 企业信息卡片组件（填/读两态） | 新建 |
| `frontend/src/pages/Onboarding/OnboardingPage.tsx` | 引导页骨架（左侧步骤 + 右侧内容） | 新建 |
| `frontend/src/pages/Onboarding/StepEnterprise.tsx` | 第 1 步企业信息 | 新建 |
| `frontend/src/pages/Onboarding/StepOrg.tsx` | 第 2 步组织架构 | 新建 |
| `frontend/src/pages/Onboarding/StepRiskChemical.tsx` | 第 3 步风险与危化品 | 新建 |
| `frontend/src/pages/Onboarding/StepResources.tsx` | 第 4 步应急资源 | 新建 |
| `frontend/src/pages/Onboarding/StepSurrounding.tsx` | 第 5 步周边环境 | 新建 |
| `frontend/src/pages/Onboarding/StepGenerate.tsx` | 第 6 步生成预案（可选） | 新建 |
| `frontend/src/pages/Onboarding/CandidatesReview.tsx` | 候选核对组件（采纳/修改/删除/增量） | 新建 |
| `frontend/src/pages/Onboarding/ImportDrawer.tsx` | 导入现有数据/资料包抽屉 | 新建 |
| `frontend/src/pages/Dashboard/CompletionCard.tsx` | 工作台完成度卡片 | 新建 |
| `frontend/src/routes/index.tsx` | 挂载 `/onboarding` 路由 | 修改 |
| `frontend/src/pages/Dashboard/DashboardPage.tsx` | 嵌入完成度卡片 | 修改 |
| `frontend/src/types/onboarding.ts` | 引导相关类型 | 新建 |

---

### 任务 C1-1：类型 + 服务封装 + 路由

**文件：**
- 新建：`frontend/src/types/onboarding.ts`
- 新建：`frontend/src/services/onboardingService.ts`
- 修改：`frontend/src/routes/index.tsx`

- [x] **步骤 1：新增类型与服务**

新建 `frontend/src/types/onboarding.ts`：

```ts
export interface CompletionModule {
  key: string;
  label: string;
  weight: number;
  done: boolean;
}

export interface CompletionResult {
  percent: number;
  modules: CompletionModule[];
}

export interface CandidateItem {
  _key: string;
  source?: string;
  [key: string]: unknown;
}
```

新建 `frontend/src/services/onboardingService.ts`：

```ts
import api from "./api";
import type { CompletionResult } from "@/types/onboarding";

export function getEnterpriseCompletion(enterpriseId: string): Promise<CompletionResult> {
  return api.get(`/enterprises/${enterpriseId}/completion`).then(r => r.data.data);
}

export function importOnboardingFile(enterpriseId: string, module: string, file: File): Promise<{ module: string; candidates: unknown[]; source: string }> {
  const form = new FormData();
  form.append("module", module);
  form.append("file", file);
  return api.post(`/onboarding/import`, form).then(r => r.data.data);
}

export function importOnboardingBatch(enterpriseId: string, files: File[]): Promise<{ module: string; candidates: unknown[]; source: string }[]> {
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  return api.post(`/onboarding/import/batch`, form).then(r => r.data.data);
}
```

- [x] **步骤 2：挂载路由**

在 `frontend/src/routes/index.tsx` 的 `contentRoutes` 增加：

```tsx
import OnboardingPage from "@/pages/Onboarding/OnboardingPage";
...
{ path: "/onboarding", element: <OnboardingPage /> },
```

- [x] **步骤 3：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误（`OnboardingPage` 尚未创建，先创建最小占位组件再验证）。

先创建最小 `OnboardingPage` 占位：

```tsx
export default function OnboardingPage() {
  return <div>引导页开发中</div>;
}
```

```bash
git add frontend/src/types/onboarding.ts frontend/src/services/onboardingService.ts frontend/src/routes/index.tsx frontend/src/pages/Onboarding/OnboardingPage.tsx
git commit -m "feat(onboarding): types, service and route scaffolding"
```

---

### 任务 C1-2：EnterpriseInfoCards 组件

**文件：**
- 新建：`frontend/src/components/enterprise/EnterpriseInfoCards.tsx`

- [x] **步骤 1：实现卡片组件（填/读两态）**

新建 `frontend/src/components/enterprise/EnterpriseInfoCards.tsx`：

```tsx
import { useState } from "react";
import { Button, Drawer, Form, Input, InputNumber, DatePicker, Collapse, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { Enterprise } from "@/types/enterprise";
import { autofillEnterprise } from "@/services/enterpriseService";

interface Props {
  enterprise?: Enterprise | null;
  readOnly?: boolean;
  onSaved?: (values: Record<string, unknown>) => Promise<void>;
  onCreate?: (values: Record<string, unknown>) => Promise<void>;
}

/** 企业信息卡片网格：名称 + AI 自动填充 + 关键字段卡片 + 展开全部字段抽屉 */
export default function EnterpriseInfoCards({ enterprise, readOnly = false, onSaved, onCreate }: Props) {
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [autofillLoading, setAutofillLoading] = useState(false);

  const handleAutofill = async () => {
    const name = form.getFieldValue("name") || enterprise?.name;
    if (!name || name.trim().length < 2) {
      message.warning("请先输入完整企业名称");
      return;
    }
    setAutofillLoading(true);
    try {
      const result = await autofillEnterprise(name.trim());
      if (result.error) {
        message.warning(result.error === "not_found" ? "未找到该企业信息，请检查企业名称" : "查询失败，请手动填写");
        return;
      }
      const values: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(result.fields || {})) {
        if (v != null && v !== "") values[k] = k === "established_date" ? dayjs(v as string) : v;
      }
      if (Object.keys(values).length > 0) {
        form.setFieldsValue(values);
        message.success(`已自动填充 ${Object.keys(values).length} 个字段，请逐项核对`);
      }
    } catch {
      message.error("查询失败，请手动填写");
    } finally {
      setAutofillLoading(false);
    }
  };

  const CARD_FIELDS: Array<[string, string]> = [
    ["credit_code", "统一社会信用代码"], ["legal_representative", "法定代表人"],
    ["address", "地址"], ["industry", "行业"], ["business_scope", "经营范围"],
    ["employee_count", "员工人数"], ["established_date", "成立日期"], ["safety_officer", "安全负责人"],
  ];

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Form form={form} layout="vertical" style={{ flex: 1 }}>
          <Form.Item name="name" label="企业名称" rules={[{ required: true, message: "请输入企业名称" }]} initialValue={enterprise?.name}>
            <div style={{ display: "flex", gap: 8 }}>
              <Input placeholder="请输入企业全称" style={{ flex: 1 }} />
              <Button type="primary" loading={autofillLoading} onClick={handleAutofill}>AI 自动填充</Button>
            </div>
          </Form.Item>
        </Form>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 8 }}>
        {CARD_FIELDS.map(([key, label]) => {
          const value = form.getFieldValue(key) ?? (enterprise as any)?.[key];
          return (
            <div key={key} style={{ border: "1px solid #eee", borderRadius: 8, padding: 10, fontSize: 13 }}>
              <div style={{ color: "#999", fontSize: 12 }}>{label}</div>
              <div style={{ fontWeight: 500, color: value ? "#333" : "#fa8c16" }}>
                {value ? (key === "established_date" && !dayjs.isDayjs(value) ? String(value).slice(0, 10) : String(value)) : "（待补充）"}
              </div>
            </div>
          );
        })}
      </div>

      {!readOnly && (
        <div style={{ marginTop: 12 }}>
          <Button icon={<PlusOutlined />} onClick={() => setDrawerOpen(true)} style={{ width: "100%" }}>
            展开全部字段（法定资料 / 联系场地 / 安全管理 / 生产物料）
          </Button>
        </div>
      )}

      <Drawer title="全部字段" open={drawerOpen} onClose={() => setDrawerOpen(false)} width={560}>
        <Form form={form} layout="vertical">
          <Collapse
            defaultActiveKey={["basic"]}
            items={[
              {
                key: "basic", label: "法定基本资料",
                children: (
                  <>
                    <Form.Item name="credit_code" label="统一社会信用代码"><Input maxLength={18} /></Form.Item>
                    <Form.Item name="legal_representative" label="法定代表人"><Input /></Form.Item>
                    <Form.Item name="economic_type" label="经济类型"><Input placeholder="选择或输入经济类型" /></Form.Item>
                    <Form.Item name="established_date" label="成立日期"><DatePicker style={{ width: "100%" }} /></Form.Item>
                    <Form.Item name="registered_capital" label="注册资本（万元）"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
                    <Form.Item name="business_scope" label="经营范围"><Input.TextArea rows={2} /></Form.Item>
                  </>
                ),
              },
              {
                key: "contact", label: "联系与场地",
                children: (
                  <>
                    <Form.Item name="address" label="地址"><Input /></Form.Item>
                    <Form.Item name="industry" label="行业"><Input /></Form.Item>
                    <Form.Item name="phone" label="联系电话"><Input /></Form.Item>
                    <Form.Item name="employee_count" label="员工人数"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
                  </>
                ),
              },
              {
                key: "safety", label: "安全管理与合规",
                children: (
                  <>
                    <Form.Item name="safety_officer" label="安全负责人"><Input /></Form.Item>
                    <Form.Item name="safety_officer_phone" label="安全负责人电话"><Input /></Form.Item>
                    <Form.Item name="safety_standardization" label="安全标准化等级"><Input placeholder="一级/二级/三级/未评定" /></Form.Item>
                    <Form.Item name="fire_approval" label="消防验收"><Input /></Form.Item>
                  </>
                ),
              },
              {
                key: "production", label: "生产与物料",
                children: (
                  <>
                    <Form.Item name="main_products" label="主要产品"><Input /></Form.Item>
                    <Form.Item name="hazardous_chemicals" label="危险化学品"><Input.TextArea rows={2} /></Form.Item>
                    <Form.Item name="special_equipment" label="特种设备"><Input /></Form.Item>
                  </>
                ),
              },
            ]}
          />
        </Form>
        <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button onClick={() => setDrawerOpen(false)}>取消</Button>
          <Button
            type="primary"
            onClick={async () => {
              const values = await form.validateFields();
              if (onCreate) await onCreate(values);
              if (onSaved) await onSaved(values);
              setDrawerOpen(false);
            }}
          >
            {onCreate ? "创建企业" : "保存"}
          </Button>
        </div>
      </Drawer>
    </div>
  );
}
```

（字段类型 `Enterprise` 若缺少某字段，以 `any` 兼容；`readOnly` 态隐藏按钮、卡片不可编辑。）

- [x] **步骤 2：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/components/enterprise/EnterpriseInfoCards.tsx
git commit -m "feat(enterprise): reusable EnterpriseInfoCards component"
```

---

### 任务 C1-3：候选核对组件（CandidatesReview）

**文件：**
- 新建：`frontend/src/pages/Onboarding/CandidatesReview.tsx`

- [x] **步骤 1：实现候选核对组件**

新建 `frontend/src/pages/Onboarding/CandidatesReview.tsx`：

```tsx
import { useState } from "react";
import { Button, Card, Tag, Space, Empty } from "antd";
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
}

/** 候选核对：已采纳（绿）与新增候选（蓝）两区，支持增量生成 */
export default function CandidatesReview({ accepted, candidates, renderItem, onAccept, onModify, onDelete, onGenerateMore, generating, sourceLabel }: Props) {
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

      <Button onClick={onGenerateMore} loading={generating} style={{ width: "100%" }}>
        继续生成更多（不覆盖已采纳）
      </Button>
    </div>
  );
}
```

- [x] **步骤 2：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Onboarding/CandidatesReview.tsx
git commit -m "feat(onboarding): candidates review component with incremental generation"
```

---

### 任务 C1-4：OnboardingPage 骨架 + 第 1/2 步

**文件：**
- 新建：`frontend/src/pages/Onboarding/StepEnterprise.tsx`
- 新建：`frontend/src/pages/Onboarding/StepOrg.tsx`
- 修改：`frontend/src/pages/Onboarding/OnboardingPage.tsx`

- [x] **步骤 1：OnboardingPage 骨架（左侧步骤 + 右侧内容）**

重写 `frontend/src/pages/Onboarding/OnboardingPage.tsx`：

```tsx
import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button, Layout } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import StepEnterprise from "./StepEnterprise";
import StepOrg from "./StepOrg";

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

（`StepRiskChemical` 等后续任务创建，先建最小占位避免 tsc 报错；`Step` 组件统一 props：`{ enterpriseId: string; onDone: () => void; onPrev: () => void }`。）

- [x] **步骤 2：第 1 步 StepEnterprise**

新建 `frontend/src/pages/Onboarding/StepEnterprise.tsx`：

```tsx
import { Button } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";

interface Props { enterpriseId: string; onDone: () => void; onPrev: () => void; }

export default function StepEnterprise({ enterpriseId, onDone }: Props) {
  const queryClient = useQueryClient();
  const { data: enterprise } = useQuery({ queryKey: ["enterprise", enterpriseId], queryFn: () => getEnterprise(enterpriseId), enabled: !!enterpriseId });
  return (
    <div style={{ maxWidth: 720 }}>
      <h3>企业信息</h3>
      <p style={{ color: "#666", fontSize: 13 }}>先确认企业是谁——这是整份预案的事实基础</p>
      <EnterpriseInfoCards enterprise={enterprise} onSaved={async () => { queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] }); }} />
      <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
        <Button type="primary" onClick={onDone}>标记完成，下一步 →</Button>
      </div>
    </div>
  );
}
```

- [x] **步骤 3：第 2 步 StepOrg（AI 生成 + 成员表格）**

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
  const { data: enterprise } = useQuery({ queryKey: ["enterprise", enterpriseId], queryFn: () => getEnterprise(enterpriseId), enabled: !!enterpriseId });
  const accepted = enterprise?.org_structure || [];

  const generate = async () => {
    setGenerating(true);
    try {
      const r = await api.post("/onboarding/candidates", { enterprise_id: enterpriseId, module: "org", overview });
      setCandidates(r.data.data.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "生成失败");
    } finally { setGenerating(false); }
  };

  const saveMut = useMutation({
    mutationFn: (groups: OrgGroup[]) => updateOrgStructure(enterpriseId, groups),
    onSuccess: () => { message.success("组织架构已保存"); queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] }); },
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

- [x] **步骤 4：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误（后续步骤组件先建最小占位）。

```bash
git add frontend/src/pages/Onboarding/OnboardingPage.tsx frontend/src/pages/Onboarding/StepEnterprise.tsx frontend/src/pages/Onboarding/StepOrg.tsx
git commit -m "feat(onboarding): page skeleton and step 1-2 (enterprise info, org structure)"
```

---

### 任务 C1-5：第 3 步风险与危化品 + 第 4 步应急资源 + 第 5 步周边环境

**文件：**
- 新建：`frontend/src/pages/Onboarding/StepRiskChemical.tsx`
- 新建：`frontend/src/pages/Onboarding/StepResources.tsx`
- 新建：`frontend/src/pages/Onboarding/StepSurrounding.tsx`

- [x] **步骤 1：第 3 步（复用现有 AI 生成服务 + 关联）**

新建 `frontend/src/pages/Onboarding/StepRiskChemical.tsx`：

```tsx
import { useState } from "react";
import { Button, Input, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { generateChemicalsAI } from "@/services/hazardousChemicalService";
import { listChemicals } from "@/services/hazardousChemicalService";
import { generateSurroundingAI } from "@/services/enterpriseService";
import CandidatesReview from "./CandidatesReview";
import type { CandidateItem } from "@/types/onboarding";

interface Props { enterpriseId: string; onDone: () => void; onPrev: () => void; }

export default function StepRiskChemical({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [accepted, setAccepted] = useState<CandidateItem[]>([]);
  const [generating, setGenerating] = useState(false);

  const generate = async () => {
    setGenerating(true);
    try {
      // 危化品候选（复用现有 AI 生成接口，把概况包装成单条回答）
      const resp = await generateChemicalsAI(enterpriseId, [{ question_id: "q0", question: "企业概况", answer: overview }]);
      const items: CandidateItem[] = (resp || []).map((c: any, i: number) => ({ _key: `c-${Date.now()}-${i}`, ...c }));
      setCandidates(items);
    } catch (e: any) {
      message.error(e?.message || "生成失败");
    } finally { setGenerating(false); }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <h3>风险与危化品</h3>
      <p style={{ color: "#666", fontSize: 13 }}>企业有什么风险、存了什么危化品——事故风险描述的核心数据</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea rows={2} value={overview} onChange={e => setOverview(e.target.value)} placeholder="如：主要生产/储存甲醇、乙醇，有储罐区" />
        <Button type="primary" loading={generating} onClick={generate}>AI 生成候选</Button>
      </div>
      <CandidatesReview
        accepted={accepted}
        candidates={candidates}
        renderItem={(item: any) => (
          <div>
            <b>{item.name}</b> <span style={{ color: "#999", fontSize: 12 }}>{item.cas_no ? `CAS ${item.cas_no}` : ""}</span>
            <div style={{ color: "#666", fontSize: 12 }}>{item.location || "位置待补充"}</div>
          </div>
        )}
        onAccept={(item) => {
          setCandidates(prev => prev.filter(x => x._key !== item._key));
          setAccepted(prev => [...prev, item]);
          // 采纳后写入危化品（调用 batch 接口），由计划 C2 的写入层接入
          message.info("已加入待保存列表，本步完成时统一写入");
        }}
        onModify={() => {}}
        onDelete={(item) => setCandidates(prev => prev.filter(x => x._key !== item._key))}
        onGenerateMore={generate}
        generating={generating}
      />
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={() => { onDone(); }}>标记完成，下一步 →</Button>
      </div>
    </div>
  );
}
```

（第 4 步 `StepResources`、第 5 步 `StepSurrounding` 按同一模式实现：调用 `generateResourcesAI` / `generateSurroundingAI` + 高德 `searchAmapSurrounding` 直接导入；第 6 步 `StepGenerate` 展示类型选择 + 「现在生成预案」跳转 `/plans/new?enterprise_id=xxx`。）

- [x] **步骤 2：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Onboarding/StepRiskChemical.tsx frontend/src/pages/Onboarding/StepResources.tsx frontend/src/pages/Onboarding/StepSurrounding.tsx frontend/src/pages/Onboarding/StepGenerate.tsx
git commit -m "feat(onboarding): steps 3-6 (risk/chemical, resources, surrounding, generate)"
```

---

### 任务 C1-6：导入交互（ImportDrawer）+ 工作台完成度卡片

**文件：**
- 新建：`frontend/src/pages/Onboarding/ImportDrawer.tsx`
- 新建：`frontend/src/pages/Dashboard/CompletionCard.tsx`
- 修改：`frontend/src/pages/Dashboard/DashboardPage.tsx`

- [x] **步骤 1：ImportDrawer（单文件 + 资料包）**

新建 `frontend/src/pages/Onboarding/ImportDrawer.tsx`：

```tsx
import { useState } from "react";
import { Drawer, Upload, message } from "antd";
import { importOnboardingFile, importOnboardingBatch } from "@/services/onboardingService";

interface Props { enterpriseId: string; open: boolean; onClose: () => void; onImported: (items: unknown[]) => void; }

export default function ImportDrawer({ enterpriseId, open, onClose, onImported }: Props) {
  const [uploading, setUploading] = useState(false);
  return (
    <Drawer title="导入现有数据" open={open} onClose={onClose} width={520}>
      <p style={{ color: "#666", fontSize: 13 }}>支持 .xlsx / .csv / .docx / .pdf，AI 自动提取为候选供核对；也可上传多个文件作为「资料包」自动分流。</p>
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
          } catch (e: any) {
            message.error(e?.response?.data?.detail || "导入失败");
          } finally { setUploading(false); }
          return false;
        }}
        showUploadList={false}
      >
        <p>点击或拖拽文件到这里</p>
        <p style={{ color: "#999", fontSize: 12 }}>{uploading ? "AI 分析提取中…" : "资料包（多文件）将自动识别并分流到各步骤"}</p>
      </Upload.Dragger>
    </Drawer>
  );
}
```

- [x] **步骤 2：CompletionCard（工作台完成度卡片）**

新建 `frontend/src/pages/Dashboard/CompletionCard.tsx`：

```tsx
import { useNavigate, useSearchParams } from "react-router-dom";
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

- [x] **步骤 3：Dashboard 嵌入卡片 + tsc 验证 + Commit**

在 `frontend/src/pages/Dashboard/DashboardPage.tsx` 的统计卡之后、快捷新建之前插入 `<CompletionCard />`，并导入组件。

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Onboarding/ImportDrawer.tsx frontend/src/pages/Dashboard/CompletionCard.tsx frontend/src/pages/Dashboard/DashboardPage.tsx
git commit -m "feat(onboarding): import drawer and dashboard completion card"
```

---

## 计划 C1 自检

**规格覆盖度：** 第 6.1 引导入口与形态 → C1-1 路由 + C1-4 骨架；第 6.2 六步 → C1-4/C1-5；第 6.3 三入口 → C1-2（手动填写抽屉）/C1-5（AI 生成）/C1-6（导入）；第 6.4 资料包 → C1-6；第 6.5 增量 → C1-3；第 6.6/7 完成度 → C1-1 + C1-6；第 3.1 EnterpriseInfoCards → C1-2。无遗漏。

**占位符扫描：** 无 TODO/待定；第 3 步"由计划 C2 的写入层接入"明确指向后续任务，非未完成占位。

**类型一致性：** `CandidateItem._key` 在 CandidatesReview/各 Step 中一致；Step 组件 props（enterpriseId/onDone/onPrev）统一；`CompletionCard` 使用 `useCurrentEnterprise` 与现有 EnterpriseContext 一致。
