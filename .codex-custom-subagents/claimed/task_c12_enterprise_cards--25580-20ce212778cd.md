# Codex Custom Subagents task handoff v1

Task: task_c12_enterprise_cards

## 任务：EnterpriseInfoCards 企业信息卡片组件（易用性优化计划 C1 任务 C1-2）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 c234d60。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：实现卡片组件（填/读两态）

新建 `frontend/src/components/enterprise/EnterpriseInfoCards.tsx`（按以下结构实现，字段以实际 Enterprise 类型为准）：

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

要求：
- 字段以 `frontend/src/types/enterprise.ts` 的 Enterprise 类型为准（若某字段不在类型中，用 `as any` 兼容或按实际字段调整）。
- readOnly 态：隐藏「展开全部字段」按钮、卡片不可编辑（名称输入框也可用展示代替——可接受当前结构，readOnly 时名称 Input 改为只读样式）。
- 企查查自动填充复用现有 `autofillEnterprise`。

### 步骤 2：tsc 验证

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

预期：无类型错误（若 Enterprise 类型缺字段，按实际补充或兼容）。

### 步骤 3：Commit

```bash
git add frontend/src/components/enterprise/EnterpriseInfoCards.tsx
git commit -m "feat(enterprise): reusable EnterpriseInfoCards component"
```

## 上下文

- 这是共享组件：引导第 1 步、企业创建/编辑页、详情基本信息 tab 四端复用（C2-1 会接入创建/编辑/详情）。
- 现有 `autofillEnterprise`（enterpriseService）返回 {fields} 或 {error}。
- 新增行 ≤100 字符。

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 types/enterprise.ts 与 enterpriseService.ts 确认字段/API
2. 按步骤实现
3. tsc 验证
4. 提交
5. 自审：字段与类型一致？readOnly 行为正确？企查查填充可用？新增行 ≤100？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc 结果、提交 SHA、自审发现
