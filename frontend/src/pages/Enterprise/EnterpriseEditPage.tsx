import { useState, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Form, Input, Select, AutoComplete, InputNumber, Button, Card, Spin, message, Upload, Space, DatePicker, Collapse } from "antd";
import { UploadOutlined, EnvironmentOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateEnterprise } from "@/services/enterpriseService";
import { uploadFile } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import { PRESET_INDUSTRIES } from "@/utils/constants";
import { ECONOMIC_TYPE_OPTIONS } from "@/utils/constants";
import GisMapPicker from "@/components/enterprise/GisMapPicker";
import type { EnterpriseUpdate } from "@/types/enterprise";
import dayjs from "dayjs";

const STANDARDIZATION_LEVELS = ["一级", "二级", "三级", "未评定"];

export default function EnterpriseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [gisModalOpen, setGisModalOpen] = useState(false);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => updateEnterprise(id!, values as EnterpriseUpdate),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["enterprise", id] });
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      navigate(`/enterprises/${id}`);
    },
    onError: (err: any) => { const detail = err?.response?.data?.detail || err?.message || "保存失败"; message.error(`保存失败: ${detail}`); },
  });

  if (isLoading) return <Spin size="large" />;

  const handleUpload = async (file: File) => {
    try { const url = await uploadFile(file); setFloorPlanUrl(url); message.success("平面图上传成功"); }
    catch { message.error("上传失败"); }
  };

  const gisValue = enterprise?.gis_lat != null && enterprise?.gis_lng != null
    ? { lat: enterprise.gis_lat, lng: enterprise.gis_lng } : null;

  const collapseItems = [
    {
      key: "basic",
      label: "法定基本资料",
      children: (
        <>
          <Form.Item name="name" label="企业名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="credit_code" label="统一社会信用代码"><Input maxLength={18} /></Form.Item>
          <Form.Item name="legal_representative" label="法定代表人"><Input /></Form.Item>
          <Form.Item name="economic_type" label="经济类型">
            <AutoComplete
            placeholder="?????????"
            options={ECONOMIC_TYPE_OPTIONS.map(t => ({ value: t, label: t }))}
            filterOption={(inputValue, option) =>
              option!.value.toUpperCase().indexOf(inputValue.toUpperCase()) !== -1
            }
            allowClear
          />
          </Form.Item>
          <Form.Item name="established_date" label="成立日期" getValueFromEvent={(d: dayjs.Dayjs | null) => d?.format("YYYY-MM-DD")}
            getValueProps={(v: string) => ({ value: v ? dayjs(v) : null })}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="registered_capital" label="注册资本（万元）"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="business_scope" label="经营范围"><Input.TextArea rows={2} /></Form.Item>
        </>
      ),
    },
    {
      key: "contact",
      label: "联系与场地信息",
      children: (
        <>
          <Form.Item name="address" label="地址"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="phone" label="联系电话"><Input /></Form.Item>
          <Form.Item name="fax" label="传真"><Input /></Form.Item>
          <Form.Item name="postal_code" label="邮政编码"><Input maxLength={6} /></Form.Item>
          <Form.Item name="land_area" label="占地面积（㎡）"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="building_area" label="建筑面积（㎡）"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="employee_count" label="员工人数"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="building_overview" label="建筑/厂区概况"><Input.TextArea rows={3} /></Form.Item>
        </>
      ),
    },
    {
      key: "safety",
      label: "安全管理与合规",
      children: (
        <>
          <Form.Item name="safety_officer" label="安全负责人"><Input /></Form.Item>
          <Form.Item name="safety_officer_phone" label="安全负责人电话"><Input /></Form.Item>
          <Form.Item name="safety_staff_count" label="安全管理人员数量"><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item name="safety_standardization" label="安全标准化等级">
            <Select options={STANDARDIZATION_LEVELS.map(l => ({ value: l, label: l }))} />
          </Form.Item>
          <Form.Item name="fire_approval" label="消防验收情况">
            <Select options={[{ value: "已验收", label: "已验收" }, { value: "未验收", label: "未验收" }, { value: "不适用", label: "不适用" }]} />
          </Form.Item>
          <Form.Item name="fire_approval_date" label="消防验收日期" getValueFromEvent={(d: dayjs.Dayjs | null) => d?.format("YYYY-MM-DD")}
            getValueProps={(v: string) => ({ value: v ? dayjs(v) : null })}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="last_plan_filing_date" label="上次备案日期" getValueFromEvent={(d: dayjs.Dayjs | null) => d?.format("YYYY-MM-DD")}
            getValueProps={(v: string) => ({ value: v ? dayjs(v) : null })}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="last_plan_filing_authority" label="上次备案部门"><Input /></Form.Item>
        </>
      ),
    },
    {
      key: "production",
      label: "生产与物料信息",
      children: (
        <>
          <Form.Item name="industry" label="行业">
            <Select showSearch options={[...PRESET_INDUSTRIES].map(i => ({ value: i, label: i }))} />
          </Form.Item>
          <Form.Item name="main_products" label="主要产品"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="annual_capacity" label="年生产能力"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="hazardous_chemicals" label="危险化学品信息"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="special_equipment" label="特种设备"><Input.TextArea rows={2} /></Form.Item>
        </>
      ),
    },
  ];

  const onFinish = (values: Record<string, unknown>) => {
    const payload: Record<string, unknown> = { ...values, floor_plan_url: floorPlanUrl ?? enterprise?.floor_plan_url ?? null };
    mutation.mutate(payload);
  };

  return (
    <div style={{ maxWidth: 800 }}>
      <PageHeader title="编辑企业" onBack={() => navigate(`/enterprises/${id}`)} />
      <Form form={form} layout="vertical" onFinish={onFinish}
        initialValues={enterprise ? { ...enterprise } : {}}>
        <Collapse defaultActiveKey={["basic", "contact"]} items={collapseItems} style={{ marginBottom: 16 }} />

        <Card title="GIS 定位与平面图" size="small" style={{ marginBottom: 16 }}>
          <Space orientation="vertical" style={{ width: "100%" }}>
            <Form.Item label="厂区平面图" style={{ marginBottom: 8 }}>
              <input ref={uploadRef} type="file" accept="image/*" style={{ display: "none" }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }} />
              <Button icon={<UploadOutlined />} onClick={() => uploadRef.current?.click()}>上传厂区平面图</Button>
              {(floorPlanUrl || enterprise?.floor_plan_url) && (
                <div style={{ position: "relative", display: "inline-block", marginLeft: 12 }}>
                  <img src={floorPlanUrl || enterprise?.floor_plan_url!} alt="预览"
                    style={{ maxWidth: 300, maxHeight: 150, border: "1px solid #d9d9d9", borderRadius: 4 }} />
                  <Button type="text" danger size="small" icon={<DeleteOutlined />}
                    style={{ position: "absolute", top: 0, right: 0 }} onClick={() => setFloorPlanUrl(null)} />
                </div>
              )}
            </Form.Item>
            <Form.Item label="GIS 坐标" style={{ marginBottom: 0 }}>
              <Space>
                <Button icon={<EnvironmentOutlined />} onClick={() => setGisModalOpen(true)}>
                  {gisValue ? "重新选择厂区位置" : "在地图上选择厂区位置"}
                </Button>
                {gisValue && <span style={{ color: "#666", fontSize: 13 }}>已选：{gisValue.lat.toFixed(6)}, {gisValue.lng.toFixed(6)}</span>}
              </Space>
            </Form.Item>
            <Form.Item name="gis_lat" hidden><Input /></Form.Item>
            <Form.Item name="gis_lng" hidden><Input /></Form.Item>
          </Space>
        </Card>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending} style={{ marginRight: 8 }}>保存</Button>
          <Button onClick={() => navigate(`/enterprises/${id}`)}>取消</Button>
        </Form.Item>
      </Form>

      <GisMapPicker visible={gisModalOpen} value={gisValue}
        onChange={(pos) => { if (pos) { form.setFieldsValue({ gis_lat: pos.lat, gis_lng: pos.lng }); } else { form.setFieldsValue({ gis_lat: null, gis_lng: null }); } }}
        onClose={() => setGisModalOpen(false)} />
    </div>
  );
}
