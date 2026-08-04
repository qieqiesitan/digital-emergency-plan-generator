import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Select, AutoComplete, InputNumber, Button, Card, message, Upload, Space, DatePicker, Collapse } from "antd";
import { UploadOutlined, EnvironmentOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createEnterprise, autofillEnterprise } from "@/services/enterpriseService";
import { uploadFile } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import { PRESET_INDUSTRIES } from "@/utils/constants";
import { ECONOMIC_TYPE_OPTIONS } from "@/utils/constants";
import GisMapPicker from "@/components/enterprise/GisMapPicker";
import dayjs from "dayjs";

const STANDARDIZATION_LEVELS = ["一级", "二级", "三级", "未评定"];

export default function EnterpriseCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();

  const [gisModalOpen, setGisModalOpen] = useState(false);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const [autofillLoading, setAutofillLoading] = useState(false);
  const [autofillCooldown, setAutofillCooldown] = useState(false);

  const mutation = useMutation({
    mutationFn: createEnterprise,
    onSuccess: (data) => {
      message.success("企业创建成功");
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      navigate(`/enterprises/${data.id}`);
    },
    onError: (err: any) => { const detail = err?.response?.data?.detail || err?.message || "创建失败"; message.error(`创建失败: ${detail}`); },
  });

  const handleUpload = async (file: File) => {
    try { const url = await uploadFile(file); setFloorPlanUrl(url); message.success("平面图上传成功"); }
    catch { message.error("上传失败"); }
  };

  const handleAutofill = async () => {
    const name = form.getFieldValue("name");
    if (!name || name.trim().length < 2) {
      message.warning("请先输入完整企业名称");
      return;
    }
    setAutofillLoading(true);
    setAutofillCooldown(true);
    try {
      const result = await autofillEnterprise(name.trim());
      if (result.error) {
        const msgs: Record<string, string> = {
          rate_limited: "操作过于频繁，请3秒后再试",
          credits_exhausted: "今日免费额度已用完，请手动填写企业信息",
          not_found: "未找到该企业信息，请检查企业名称是否正确",
          network_error: "查询服务暂时不可用，请手动填写企业信息",
          not_configured: "未配置企查查 API，请联系管理员",
        };
        message.warning(msgs[result.error] || "查询失败，请手动填写");
        return;
      }
      const fields = result.fields || {};
      const formValues: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(fields)) {
        if (value != null && value !== "") {
          if (key === "established_date") {
            formValues[key] = dayjs(value as string);
          } else {
            formValues[key] = value;
          }
        }
      }
      if (Object.keys(formValues).length > 0) {
        form.setFieldsValue(formValues);
        message.success(`已自动填充 ${Object.keys(formValues).length} 个字段，请逐项核对后提交`);
      } else {
        message.info("未获取到可填充的字段，请手动填写");
      }
    } catch {
      message.error("查询失败，请手动填写企业信息");
    } finally {
      setAutofillLoading(false);
      setTimeout(() => setAutofillCooldown(false), 5000);
    }
  };

  const collapseItems = [
    {
      key: "basic",
      label: "法定基本资料",
      children: (
        <>
          <Form.Item name="name" label="企业名称" rules={[{ required: true, message: "请输入企业名称" }]}>
            <div style={{ display: "flex", gap: 8 }}>
              <Input placeholder="请输入企业全称" style={{ flex: 1 }} />
              <Button type="primary" loading={autofillLoading} disabled={autofillCooldown} onClick={handleAutofill}>
                {autofillLoading ? "搜索中..." : "AI 自动填充"}
              </Button>
            </div>
          </Form.Item>
          <Form.Item name="credit_code" label="统一社会信用代码">
            <Input placeholder="18位统一社会信用代码" maxLength={18} />
          </Form.Item>
          <Form.Item name="legal_representative" label="法定代表人">
            <Input placeholder="法定代表人姓名" />
          </Form.Item>
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
          <Form.Item name="established_date" label="成立日期" getValueFromEvent={(d: dayjs.Dayjs | null) => d?.format("YYYY-MM-DD")}>
            <DatePicker style={{ width: "100%" }} placeholder="选择成立日期" />
          </Form.Item>
          <Form.Item name="registered_capital" label="注册资本（万元）">
            <InputNumber min={0} placeholder="注册资本" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="business_scope" label="经营范围">
            <Input.TextArea rows={2} placeholder="经营范围" />
          </Form.Item>
        </>
      ),
    },
    {
      key: "contact",
      label: "联系与场地信息",
      children: (
        <>
          <Form.Item name="address" label="地址">
            <Input.TextArea rows={2} placeholder="企业地址" />
          </Form.Item>
          <Form.Item name="phone" label="联系电话">
            <Input placeholder="企业联系电话" />
          </Form.Item>
          <Form.Item name="fax" label="传真">
            <Input placeholder="传真号码" />
          </Form.Item>
          <Form.Item name="postal_code" label="邮政编码">
            <Input placeholder="邮政编码" maxLength={6} />
          </Form.Item>
          <Form.Item name="land_area" label="占地面积（㎡）">
            <InputNumber min={0} placeholder="占地面积" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="building_area" label="建筑面积（㎡）">
            <InputNumber min={0} placeholder="建筑面积" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="employee_count" label="员工人数">
            <InputNumber min={1} placeholder="员工人数" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="building_overview" label="建筑/厂区概况">
            <Input.TextArea rows={3} placeholder="描述厂区面积、建筑物分布等" />
          </Form.Item>
        </>
      ),
    },
    {
      key: "safety",
      label: "安全管理与合规",
      children: (
        <>
          <Form.Item name="safety_officer" label="安全负责人">
            <Input placeholder="安全负责人姓名" />
          </Form.Item>
          <Form.Item name="safety_officer_phone" label="安全负责人电话">
            <Input placeholder="安全负责人联系电话" />
          </Form.Item>
          <Form.Item name="safety_staff_count" label="安全管理人员数">
            <InputNumber min={0} placeholder="安全管理人员数量" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="safety_standardization" label="安全标准化等级">
            <Select placeholder="选择标准化等级" options={STANDARDIZATION_LEVELS.map(s => ({ value: s, label: s }))} />
          </Form.Item>
          <Form.Item name="fire_approval" label="消防验收文号">
            <Input placeholder="消防验收批准文号" />
          </Form.Item>
          <Form.Item name="fire_approval_date" label="消防验收日期" getValueFromEvent={(d: dayjs.Dayjs | null) => d?.format("YYYY-MM-DD")}>
            <DatePicker style={{ width: "100%" }} placeholder="选择消防验收日期" />
          </Form.Item>
          <Form.Item name="last_plan_filing_date" label="上次应急预案备案日期" getValueFromEvent={(d: dayjs.Dayjs | null) => d?.format("YYYY-MM-DD")}>
            <DatePicker style={{ width: "100%" }} placeholder="选择上次备案日期" />
          </Form.Item>
          <Form.Item name="last_plan_filing_authority" label="上次备案部门">
            <Input placeholder="上次应急预案备案的应急管理部门" />
          </Form.Item>
        </>
      ),
    },
    {
      key: "production",
      label: "生产与物料信息",
      children: (
        <>
          <Form.Item name="industry" label="行业">
            <Select placeholder="选择或输入行业" showSearch options={[...PRESET_INDUSTRIES].map(i => ({ value: i, label: i }))} />
          </Form.Item>
          <Form.Item name="main_products" label="主要产品">
            <Input.TextArea rows={2} placeholder="企业主要产品及生产规模" />
          </Form.Item>
          <Form.Item name="annual_capacity" label="年生产能力">
            <Input.TextArea rows={2} placeholder="年生产能力描述，如：年产水泥 50 万吨" />
          </Form.Item>
          <Form.Item name="hazardous_chemicals" label="危险化学品信息">
            <Input.TextArea rows={3} placeholder="涉及的危险化学品名称、最大贮存量、所在位置" />
          </Form.Item>
          <Form.Item name="special_equipment" label="特种设备">
            <Input.TextArea rows={2} placeholder="特种设备类型及数量，如：锅炉2台、压力容器5台" />
          </Form.Item>
        </>
      ),
    },
  ];

  const onFinish = (values: Record<string, unknown>) => {
    const payload: Record<string, unknown> = { ...values, floor_plan_url: floorPlanUrl ?? null };
    mutation.mutate(payload as any);
  };

  return (
    <div style={{ maxWidth: 800 }}>
      <PageHeader title="新建企业" onBack={() => navigate("/enterprises")} />
      <div style={{ background: "#fff3cd", padding: "8px 16px", marginBottom: 16, borderRadius: 6, fontSize: 13 }}>
        💡 输入企业全称后，点击右侧「AI 自动填充」按钮，系统将自动查询企查查工商数据并填入对应字段。填写完成后请逐项核对。
      </div>
      <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ economic_type: "民营" }}>
        <Collapse defaultActiveKey={["basic", "contact"]} items={collapseItems} style={{ marginBottom: 16 }} />
        <Card title="GIS 定位与平面图" size="small" style={{ marginBottom: 16 }}>
          <Space orientation="vertical" style={{ width: "100%" }}>
            <Form.Item label="厂区平面图" style={{ marginBottom: 8 }}>
              <input ref={uploadRef} type="file" accept="image/*" style={{ display: "none" }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }} />
              <Button icon={<UploadOutlined />} onClick={() => uploadRef.current?.click()}>上传厂区平面图</Button>
              {floorPlanUrl && (
                <div style={{ position: "relative", display: "inline-block", marginLeft: 12 }}>
                  <img src={floorPlanUrl} alt="预览" style={{ maxWidth: 300, maxHeight: 150, border: "1px solid #d9d9d9", borderRadius: 4 }} />
                  <Button type="text" danger size="small" icon={<DeleteOutlined />}
                    style={{ position: "absolute", top: 0, right: 0 }} onClick={() => setFloorPlanUrl(null)} />
                </div>
              )}
            </Form.Item>
            <Form.Item label="GIS 坐标" style={{ marginBottom: 0 }}>
              <Space>
                <Button icon={<EnvironmentOutlined />} onClick={() => setGisModalOpen(true)}>在地图上选择厂区位置</Button>
                {form.getFieldValue("gis_lat") != null && form.getFieldValue("gis_lng") != null && (
                  <span style={{ color: "#666", fontSize: 13 }}>
                    已选：{Number(form.getFieldValue("gis_lat")).toFixed(6)}, {Number(form.getFieldValue("gis_lng")).toFixed(6)}
                  </span>
                )}
              </Space>
            </Form.Item>
            <Form.Item name="gis_lat" hidden><Input /></Form.Item>
            <Form.Item name="gis_lng" hidden><Input /></Form.Item>
          </Space>
        </Card>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending} style={{ marginRight: 8 }}>保存</Button>
          <Button onClick={() => navigate("/enterprises")}>取消</Button>
        </Form.Item>
      </Form>
      <GisMapPicker visible={gisModalOpen} value={null}
        onChange={(pos) => { if (pos) { form.setFieldsValue({ gis_lat: pos.lat, gis_lng: pos.lng }); } else { form.setFieldsValue({ gis_lat: null, gis_lng: null }); } }}
        onClose={() => setGisModalOpen(false)} />
    </div>
  );
}
