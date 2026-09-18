import { useState } from "react";
import { Button, DatePicker, Form, Input, Space, Table, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { GasTestPayload } from "@/types/workTicket";

const { Text } = Typography;

interface GasTestFormValues {
  sampled_at: dayjs.Dayjs;
  location?: string;
  gas_type?: string;
  result?: string;
  tester?: string;
  conclusion?: string;
}

interface GasTestTableProps {
  records: GasTestPayload[];
  onChange: (next: GasTestPayload[]) => void;
  disabled?: boolean;
}

/**
 * 气体检测记录表（动火/受限空间提交前必填）。
 *
 * 只维护本地列表，真正入库在向导最后一步"创建票据 → 逐条写检测 → 提交"时完成；
 * 这样用户中途放弃不会在库里留下半张票。
 *
 * 取样时间的 30 分钟红线由后端 `validate_before_submit` 判定——前端的提示只是提示，
 * 不是门禁（门禁不能放在前端，否则绕过去就等于绕过审批）。
 */
export default function GasTestTable({ records, onChange, disabled }: GasTestTableProps) {
  const [form] = Form.useForm<GasTestFormValues>();
  const [adding, setAdding] = useState(false);

  const handleAdd = async () => {
    const values = await form.validateFields();
    onChange([
      ...records,
      {
        sampled_at: (values.sampled_at as dayjs.Dayjs).toISOString(),
        location: values.location ?? null,
        gas_type: values.gas_type ?? null,
        result: values.result ?? null,
        tester: values.tester ?? null,
        conclusion: values.conclusion ?? null,
      },
    ]);
    form.resetFields();
    setAdding(false);
  };

  const columns: TableColumnsType<GasTestPayload & { key: number }> = [
    {
      title: "取样时间",
      dataIndex: "sampled_at",
      width: 170,
      render: (value: string) => (value ? dayjs(value).format("YYYY-MM-DD HH:mm") : "—"),
    },
    { title: "取样地点", dataIndex: "location", render: (v?: string | null) => v || "—" },
    { title: "检测气体", dataIndex: "gas_type", width: 120, render: (v?: string | null) => v || "—" },
    { title: "检测结果", dataIndex: "result", width: 120, render: (v?: string | null) => v || "—" },
    { title: "分析人", dataIndex: "tester", width: 100, render: (v?: string | null) => v || "—" },
    { title: "结论", dataIndex: "conclusion", width: 90, render: (v?: string | null) => v || "—" },
    {
      title: "操作",
      width: 70,
      render: (_, __, index) => (
        <Button
          type="link"
          danger
          size="small"
          icon={<DeleteOutlined />}
          disabled={disabled}
          onClick={() => onChange(records.filter((_, i) => i !== index))}
        >
          删除
        </Button>
      ),
    },
  ];

  return (
    <Space orientation="vertical" style={{ width: "100%" }} size={8}>
      <Text type="secondary">
        动火与受限空间作业必须至少录入一次气体检测；取样时间超过 30 分钟会被拒绝提交。
      </Text>
      {records.length > 0 && (
        <Table
          size="small"
          rowKey={(r) => String(r.key)}
          columns={columns}
          dataSource={records.map((r, i) => ({ ...r, key: i }))}
          pagination={false}
        />
      )}
      {adding ? (
        <Form form={form} layout="inline" style={{ rowGap: 8 }} initialValues={{ sampled_at: dayjs() }}>
          <Form.Item name="sampled_at" rules={[{ required: true, message: "请选择取样时间" }]}>
            <DatePicker showTime format="YYYY-MM-DD HH:mm" placeholder="取样时间" />
          </Form.Item>
          <Form.Item name="location">
            <Input placeholder="取样地点" style={{ width: 160 }} />
          </Form.Item>
          <Form.Item name="gas_type">
            <Input placeholder="检测气体" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="result">
            <Input placeholder="检测结果" style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="tester">
            <Input placeholder="分析人" style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="conclusion">
            <Input placeholder="结论" style={{ width: 90 }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" onClick={handleAdd}>
                保存
              </Button>
              <Button
                onClick={() => {
                  form.resetFields();
                  setAdding(false);
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      ) : (
        <Button
          icon={<PlusOutlined />}
          disabled={disabled}
          onClick={() => setAdding(true)}
        >
          添加检测记录
        </Button>
      )}
    </Space>
  );
}
