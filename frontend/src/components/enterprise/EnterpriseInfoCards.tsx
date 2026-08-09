import { useState } from "react";
import { Button, Collapse, DatePicker, Drawer, Form, Input, InputNumber, message, Typography } from "antd";
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

const CARD_FIELDS: Array<{ key: keyof Enterprise | string; label: string }> = [
  { key: "credit_code", label: "统一社会信用代码" },
  { key: "legal_representative", label: "法定代表人" },
  { key: "address", label: "地址" },
  { key: "industry", label: "行业" },
  { key: "business_scope", label: "经营范围" },
  { key: "employee_count", label: "员工人数" },
  { key: "established_date", label: "成立日期" },
  { key: "safety_officer", label: "安全负责人" },
];

const DATE_FIELDS = ["established_date", "fire_approval_date", "last_plan_filing_date"];

function displayValue(key: string, raw: unknown): string | undefined {
  if (raw === null || raw === undefined || raw === "") return undefined;
  if (key === "established_date") {
    const d = dayjs(raw as string | dayjs.Dayjs);
    return d.isValid() ? d.format("YYYY-MM-DD") : undefined;
  }
  return String(raw);
}

export default function EnterpriseInfoCards({
  enterprise,
  readOnly = false,
  onSaved,
  onCreate,
}: Props) {
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [autofillLoading, setAutofillLoading] = useState(false);
  const watchedValues = Form.useWatch([], form);

  const enterpriseRecord = (enterprise ?? {}) as Record<string, unknown>;

  const fieldInit = (key: string) => {
    const raw = enterpriseRecord[key];
    if (raw === null || raw === undefined) return undefined;
    if (DATE_FIELDS.includes(key)) {
      return raw ? dayjs(raw as string) : undefined;
    }
    return raw;
  };

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
        message.warning(
          result.error === "not_found" ? "未找到该企业信息，请检查企业名称" : "查询失败，请手动填写",
        );
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

  return (
    <div>
      <div
        style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "flex-start" }}
      >
        <Form form={form} layout="vertical" style={{ flex: 1 }}>
          <Form.Item
            name="name"
            label="企业名称"
            rules={[{ required: true, message: "请输入企业名称" }]}
            initialValue={enterprise?.name}
          >
            <Input
              placeholder="请输入企业全称"
              readOnly={readOnly}
              style={
                readOnly
                  ? { background: "#fafafa", color: "#333" }
                  : undefined
              }
            />
          </Form.Item>
        </Form>
        {!readOnly && (
          <Button
            type="primary"
            loading={autofillLoading}
            onClick={handleAutofill}
            style={{ marginTop: 30 }}
          >
            AI 自动填充
          </Button>
        )}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 8,
        }}
      >
        {CARD_FIELDS.map(({ key, label }) => {
          const raw = watchedValues?.[key] ?? enterpriseRecord[key];
          const value = raw === null || raw === undefined || raw === "" ? undefined : raw;
          const text = displayValue(key, value);
          return (
            <div
              key={String(key)}
              style={{ border: "1px solid #eee", borderRadius: 8, padding: 10, fontSize: 13 }}
            >
              <div style={{ color: "#999", fontSize: 12 }}>{label}</div>
              <Typography.Paragraph
                ellipsis={{
                  rows: 2,
                  expandable: "collapsible",
                  symbol: (expanded) => (expanded ? "收起" : "展开"),
                }}
                style={{
                  marginBottom: 0,
                  fontWeight: 500,
                  color: text ? "#333" : "#fa8c16",
                }}
              >
                {text || "（待补充）"}
              </Typography.Paragraph>
            </div>
          );
        })}
      </div>

      {!readOnly && (
        <div style={{ marginTop: 12 }}>
          <Button
            icon={<PlusOutlined />}
            onClick={() => setDrawerOpen(true)}
            style={{ width: "100%" }}
          >
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
                key: "basic",
                label: "法定基本资料",
                children: (
                  <>
                    <Form.Item
                      name="credit_code"
                      label="统一社会信用代码"
                      initialValue={fieldInit("credit_code")}
                    >
                      <Input maxLength={18} />
                    </Form.Item>
                    <Form.Item
                      name="legal_representative"
                      label="法定代表人"
                      initialValue={fieldInit("legal_representative")}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="economic_type"
                      label="经济类型"
                      initialValue={fieldInit("economic_type")}
                    >
                      <Input placeholder="选择或输入经济类型" />
                    </Form.Item>
                    <Form.Item
                      name="established_date"
                      label="成立日期"
                      initialValue={fieldInit("established_date")}
                    >
                      <DatePicker style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item
                      name="registered_capital"
                      label="注册资本（万元）"
                      initialValue={fieldInit("registered_capital")}
                    >
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item
                      name="business_scope"
                      label="经营范围"
                      initialValue={fieldInit("business_scope")}
                    >
                      <Input.TextArea rows={2} />
                    </Form.Item>
                  </>
                ),
              },
              {
                key: "contact",
                label: "联系与场地",
                children: (
                  <>
                    <Form.Item name="address" label="地址" initialValue={fieldInit("address")}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="industry" label="行业" initialValue={fieldInit("industry")}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="phone" label="联系电话" initialValue={fieldInit("phone")}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="fax" label="传真" initialValue={fieldInit("fax")}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="postal_code" label="邮政编码" initialValue={fieldInit("postal_code")}>
                      <Input maxLength={6} />
                    </Form.Item>
                    <Form.Item name="land_area" label="占地面积（㎡）" initialValue={fieldInit("land_area")}>
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item name="building_area" label="建筑面积（㎡）" initialValue={fieldInit("building_area")}>
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item name="building_overview" label="建筑/厂区概况" initialValue={fieldInit("building_overview")}>
                      <Input.TextArea rows={2} />
                    </Form.Item>
                    <Form.Item
                      name="employee_count"
                      label="员工人数"
                      initialValue={fieldInit("employee_count")}
                    >
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                  </>
                ),
              },
              {
                key: "safety",
                label: "安全管理与合规",
                children: (
                  <>
                    <Form.Item
                      name="safety_officer"
                      label="安全负责人"
                      initialValue={fieldInit("safety_officer")}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="safety_officer_phone"
                      label="安全负责人电话"
                      initialValue={fieldInit("safety_officer_phone")}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="safety_staff_count"
                      label="安全管理人员数"
                      initialValue={fieldInit("safety_staff_count")}
                    >
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item
                      name="safety_standardization"
                      label="安全标准化等级"
                      initialValue={fieldInit("safety_standardization")}
                    >
                      <Input placeholder="一级/二级/三级/未评定" />
                    </Form.Item>
                    <Form.Item
                      name="fire_approval"
                      label="消防验收"
                      initialValue={fieldInit("fire_approval")}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="fire_approval_date"
                      label="消防验收日期"
                      initialValue={fieldInit("fire_approval_date")}
                    >
                      <DatePicker style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item
                      name="last_plan_filing_date"
                      label="上次备案日期"
                      initialValue={fieldInit("last_plan_filing_date")}
                    >
                      <DatePicker style={{ width: "100%" }} />
                    </Form.Item>
                    <Form.Item
                      name="last_plan_filing_authority"
                      label="上次备案部门"
                      initialValue={fieldInit("last_plan_filing_authority")}
                    >
                      <Input />
                    </Form.Item>
                  </>
                ),
              },
              {
                key: "production",
                label: "生产与物料",
                children: (
                  <>
                    <Form.Item
                      name="main_products"
                      label="主要产品"
                      initialValue={fieldInit("main_products")}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="annual_capacity"
                      label="年生产能力"
                      initialValue={fieldInit("annual_capacity")}
                    >
                      <Input.TextArea rows={2} />
                    </Form.Item>
                    <Form.Item
                      name="hazardous_chemicals"
                      label="危险化学品"
                      initialValue={fieldInit("hazardous_chemicals")}
                    >
                      <Input.TextArea rows={2} />
                    </Form.Item>
                    <Form.Item
                      name="special_equipment"
                      label="特种设备"
                      initialValue={fieldInit("special_equipment")}
                    >
                      <Input />
                    </Form.Item>
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
              const payload: Record<string, unknown> = { ...values };
              for (const field of DATE_FIELDS) {
                if (payload[field]) {
                  payload[field] = dayjs(payload[field] as dayjs.Dayjs | string).format("YYYY-MM-DD");
                }
              }
              if (onCreate) await onCreate(payload);
              else if (onSaved) await onSaved(payload);
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
