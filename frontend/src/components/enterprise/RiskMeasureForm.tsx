import { useState } from "react";
import {
  Drawer, Form, Input, Select, Button, DatePicker, Space, Divider, message,
} from "antd";
import { PlusOutlined, DeleteOutlined, RobotOutlined } from "@ant-design/icons";
import { MEASURE_CATEGORY_LABELS } from "@/utils/riskMethodEngine";
import { aiSuggestMeasures } from "@/services/riskManagementService";
import type { MeasureCategory } from "@/types/riskManagement";

interface CheckItem {
  name: string;
  standard: string;
  frequency: string;
}

interface RiskMeasureFormValues {
  measure_category: MeasureCategory;
  measure_type?: string;
  description: string;
  responsible_person?: string;
  deadline?: string;
  check_items?: CheckItem[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: RiskMeasureFormValues) => void;
  initialValues?: RiskMeasureFormValues;
  eventId?: string;
  enterpriseId: string;
}

export default function RiskMeasureForm({
  open, onClose, onSubmit, initialValues, eventId, enterpriseId,
}: Props) {
  const [form] = Form.useForm<RiskMeasureFormValues>();
  const [aiLoading, setAiLoading] = useState(false);

  const categoryOptions = Object.entries(MEASURE_CATEGORY_LABELS).map(
    ([value, label]) => ({ value, label }),
  );

  const handleAISuggest = async () => {
    const base = form.getFieldsValue();
    setAiLoading(true);
    try {
      const results = await aiSuggestMeasures(enterpriseId, {
        context: {
          measure_category: base.measure_category,
          description: base.description,
          event_id: eventId,
        },
      });
      if (results && results.length > 0) {
        const first = results[0] as Record<string, unknown>;
        form.setFieldsValue({
          measure_category: (first.measure_category as MeasureCategory) ?? base.measure_category,
          measure_type: (first.measure_type as string) ?? base.measure_type,
          description: (first.description as string) ?? base.description,
          responsible_person: (first.responsible_person as string) ?? base.responsible_person,
          deadline: (first.deadline as string) ?? base.deadline,
          check_items: (first.check_items as CheckItem[]) ?? base.check_items,
        });
        message.success("AI 建议已自动填入");
      } else {
        message.info("AI 未返回建议");
      }
    } catch {
      message.error("AI 分析失败");
    } finally {
      setAiLoading(false);
    }
  };

  const handleFinish = (values: RiskMeasureFormValues) => {
    onSubmit(values);
  };

  return (
    <Drawer
      title={initialValues ? "编辑管控措施" : "新增管控措施"}
      open={open}
      onClose={onClose}
      width={520}
      styles={{ body: { paddingBottom: 80 } }}
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
        <Divider titlePlacement="left" plain style={{ fontSize: 13 }}>措施信息</Divider>

        <Form.Item
          name="measure_category"
          label="措施类别"
          rules={[{ required: true, message: "请选择措施类别" }]}
        >
          <Select
            placeholder="选择措施类别"
            options={categoryOptions}
          />
        </Form.Item>

        <Form.Item name="measure_type" label="措施类型">
          <Input placeholder="如：加装防护罩、制定操作规程" />
        </Form.Item>

        <Form.Item
          name="description"
          label="措施描述"
          rules={[{ required: true, message: "请输入措施描述" }]}
        >
          <Input.TextArea
            rows={3}
            placeholder="详细描述管控措施的内容与要求"
          />
        </Form.Item>

        <Form.Item name="responsible_person" label="责任人">
          <Input placeholder="如：张三" />
        </Form.Item>

        <Form.Item
          name="deadline"
          label="完成期限"
          getValueFromEvent={(date: unknown) => {
            if (date && typeof date === "object" && "toISOString" in (date as Record<string, unknown>)) {
              return (date as { toISOString: () => string }).toISOString();
            }
            return date;
          }}
          getValueProps={(value: string | undefined) => ({
            value: value ? (value.length === 10 ? value : undefined) : undefined,
          })}
        >
          <DatePicker
            style={{ width: "100%" }}
            placeholder="选择完成期限"
          />
        </Form.Item>

        <Button
          icon={<RobotOutlined />}
          onClick={handleAISuggest}
          loading={aiLoading}
          style={{ marginBottom: 16 }}
          block
        >
          ✨ AI 建议措施
        </Button>

        <Divider titlePlacement="left" plain style={{ fontSize: 13 }}>检查项目</Divider>

        <Form.List name="check_items">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }, _index) => (
                <div
                  key={key}
                  style={{
                    marginBottom: 12,
                    padding: 12,
                    border: "1px solid #f0f0f0",
                    borderRadius: 6,
                    position: "relative",
                  }}
                >
                  <Space orientation="vertical" style={{ width: "100%" }} size={8}>
                    <Form.Item
                      {...restField}
                      name={[name, "name"]}
                      label="检查项名称"
                      rules={[{ required: true, message: "请输入检查项名称" }]}
                      style={{ marginBottom: 0 }}
                    >
                      <Input placeholder="如：防护罩完好性" />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, "standard"]}
                      label="检查标准"
                      style={{ marginBottom: 0 }}
                    >
                      <Input placeholder="如：无破损、固定牢靠" />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, "frequency"]}
                      label="检查频次"
                      style={{ marginBottom: 0 }}
                    >
                      <Input placeholder="如：每日一次" />
                    </Form.Item>
                  </Space>
                  <Button
                    type="link"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => remove(name)}
                    style={{ position: "absolute", top: 4, right: 4 }}
                  />
                </div>
              ))}
              <Button
                type="dashed"
                onClick={() => add({ name: "", standard: "", frequency: "" })}
                block
                icon={<PlusOutlined />}
              >
                添加检查项
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Drawer>
  );
}
