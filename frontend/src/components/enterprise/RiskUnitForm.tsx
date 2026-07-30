import { Drawer, Form, Input, Select, Button, Space } from "antd";

const UNIT_TYPES = [
  "设备", "物料", "工艺", "电气", "特种设备", "管道", "阀门", "仪表", "其他",
];

interface RiskUnitFormValues {
  name: string;
  unit_type?: string;
  location?: string;
  description?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: RiskUnitFormValues) => void;
  initialValues?: RiskUnitFormValues;
  objectName?: string;
}

export default function RiskUnitForm({ open, onClose, onSubmit, initialValues, objectName }: Props) {
  const [form] = Form.useForm<RiskUnitFormValues>();

  const handleFinish = (values: RiskUnitFormValues) => {
    onSubmit(values);
  };

  return (
    <Drawer
      title={initialValues ? "编辑风险单元" : "新增风险单元"}
      open={open}
      onClose={onClose}
      width={480}
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={() => form.submit()}>
            保存
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues}
        onFinish={handleFinish}
      >
        {objectName && (
          <div
            style={{
              marginBottom: 16,
              padding: "8px 12px",
              background: "#fafafa",
              borderRadius: 4,
              fontSize: 13,
              color: "#666",
            }}
          >
            所属对象：<strong style={{ color: "#333" }}>{objectName}</strong>
          </div>
        )}

        <Form.Item
          name="name"
          label="单元名称"
          rules={[{ required: true, message: "请输入单元名称" }]}
        >
          <Input placeholder="如：储罐1号" />
        </Form.Item>

        <Form.Item name="unit_type" label="单元类型">
          <Select
            allowClear
            placeholder="选择单元类型"
            options={UNIT_TYPES.map((t) => ({ value: t, label: t }))}
          />
        </Form.Item>

        <Form.Item name="location" label="位置">
          <Input placeholder="如：车间西北角" />
        </Form.Item>

        <Form.Item name="description" label="描述说明">
          <Input.TextArea rows={3} placeholder="其他补充说明" />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
