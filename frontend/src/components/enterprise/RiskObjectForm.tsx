import { useState } from "react";
import { Drawer, Form, Input, Select, Button, Switch, Upload, InputNumber, Space, message } from "antd";
import { UploadOutlined, EnvironmentOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd/es/upload/interface";
import FloorPlanPicker from "./FloorPlanPicker";

const OBJECT_CATEGORIES = [
  "生产车间", "仓库", "罐区", "配电室", "办公楼", "装卸区", "锅炉房",
];

interface RiskObjectFormValues {
  zone_id?: string;
  name: string;
  category?: string;
  location?: string;
  is_risk_point?: boolean;
  location_x?: number | null;
  location_y?: number | null;
  description?: string;
  image_url?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: RiskObjectFormValues) => void;
  initialValues?: RiskObjectFormValues;
  zones: { id: string; name: string }[];
  floorPlanUrl?: string | null;
}

export default function RiskObjectForm({ open, onClose, onSubmit, initialValues, zones, floorPlanUrl }: Props) {
  const [form] = Form.useForm<RiskObjectFormValues>();
  const [isRiskPoint, setIsRiskPoint] = useState(initialValues?.is_risk_point ?? false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [floorPlanOpen, setFloorPlanOpen] = useState(false);
  const [customCategory, setCustomCategory] = useState(false);

  const handleFinish = (values: RiskObjectFormValues) => {
    const data = { ...values };
    if (fileList.length > 0 && fileList[0].response) {
      data.image_url = fileList[0].response?.url ?? fileList[0].response?.data?.url ?? "";
    }
    onSubmit(data);
  };

  const existingCoord = form.getFieldValue("location_x") != null || form.getFieldValue("location_y") != null;

  return (
    <>
      <Drawer
        title={initialValues ? "编辑风险对象" : "新增风险对象"}
        open={open}
        onClose={onClose}
        width={520}
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
          <Form.Item name="zone_id" label="所属分区">
            <Select
              allowClear
              placeholder="选择所属分区（可选）"
              options={zones.map((z) => ({ value: z.id, label: z.name }))}
            />
          </Form.Item>

          <Form.Item
            name="name"
            label="对象名称"
            rules={[{ required: true, message: "请输入对象名称" }]}
          >
            <Input placeholder="如：1号反应釜" />
          </Form.Item>

          <Form.Item name="category" label="对象类别">
            {customCategory ? (
              <Input
                placeholder="输入自定义类别"
                onChange={(e) => form.setFieldsValue({ category: e.target.value })}
              />
            ) : (
              <Select
                allowClear
                placeholder="选择对象类别"
                options={OBJECT_CATEGORIES.map((c) => ({ value: c, label: c }))}
                dropdownRender={(menu) => (
                  <>
                    {menu}
                    <div style={{ borderTop: "1px solid #f0f0f0", padding: "8px 12px" }}>
                      <Button
                        type="link"
                        size="small"
                        onClick={() => {
                          setCustomCategory(true);
                          form.setFieldsValue({ category: undefined });
                        }}
                      >
                        输入自定义类别
                      </Button>
                    </div>
                  </>
                )}
                onChange={() => setCustomCategory(false)}
              />
            )}
          </Form.Item>

          <Form.Item name="location" label="位置描述">
            <Input.TextArea rows={2} placeholder="如：3号车间东北角" />
          </Form.Item>

          <Form.Item name="is_risk_point" label="是否为重大风险点" valuePropName="checked">
            <Switch onChange={(v) => setIsRiskPoint(v)} />
          </Form.Item>

          {isRiskPoint && (
            <>
              <Form.Item label="风险点照片">
                <Upload
                  listType="picture-card"
                  fileList={fileList}
                  maxCount={1}
                  beforeUpload={(file) => {
                    const isImage = file.type.startsWith("image/");
                    if (!isImage) {
                      message.error("只能上传图片文件");
                      return Upload.LIST_IGNORE;
                    }
                    return true;
                  }}
                  onChange={({ fileList: fl }) => setFileList(fl)}
                >
                  {fileList.length < 1 && (
                    <div>
                      <UploadOutlined />
                      <div style={{ marginTop: 8 }}>上传</div>
                    </div>
                  )}
                </Upload>
              </Form.Item>

              <Form.Item label="平面图坐标">
                <div style={{ display: "flex", gap: 8 }}>
                  <Button
                    icon={<EnvironmentOutlined />}
                    onClick={() => setFloorPlanOpen(true)}
                    disabled={!floorPlanUrl}
                  >
                    {floorPlanUrl ? "在平面图上点选" : "未上传平面图"}
                  </Button>
                  {existingCoord && (
                    <span style={{ color: "#52c41a", lineHeight: "32px" }}>
                      已标记
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                  <Form.Item name="location_x" noStyle>
                    <InputNumber
                      placeholder="X坐标(%)"
                      min={0}
                      max={100}
                      precision={2}
                      style={{ width: "50%" }}
                    />
                  </Form.Item>
                  <Form.Item name="location_y" noStyle>
                    <InputNumber
                      placeholder="Y坐标(%)"
                      min={0}
                      max={100}
                      precision={2}
                      style={{ width: "50%" }}
                    />
                  </Form.Item>
                </div>
              </Form.Item>
            </>
          )}

          <Form.Item name="description" label="描述说明">
            <Input.TextArea rows={3} placeholder="其他补充说明" />
          </Form.Item>
        </Form>
      </Drawer>

      <FloorPlanPicker
        imageUrl={floorPlanUrl ?? null}
        visible={floorPlanOpen}
        value={{
          x: form.getFieldValue("location_x") ?? null,
          y: form.getFieldValue("location_y") ?? null,
          description: form.getFieldValue("location") ?? "",
        }}
        onChange={(val) => {
          form.setFieldsValue({
            location_x: val.x,
            location_y: val.y,
            location: val.description || form.getFieldValue("location"),
          });
        }}
        onClose={() => setFloorPlanOpen(false)}
      />
    </>
  );
}
