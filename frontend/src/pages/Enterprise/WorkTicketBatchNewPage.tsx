import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Checkbox,
  DatePicker,
  Divider,
  Form,
  Input,
  Select,
  Space,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { PageHeader } from "@/components/common/PageHeader";
import { addBatchTickets, createBatch, errorDetail, listLocations, listTemplates } from "@/services/workTicketService";
import type { BatchTicketSpec } from "@/types/workTicket";
import { ALL_TICKET_TYPES } from "@/types/workTicket";

const { Text } = Typography;

interface SharedFormValues {
  title: string;
  applicant_unit?: string;
  work_unit?: string;
  work_leader?: string;
  content_base?: string;
  risk_basis?: string;
}

/**
 * 新建作业包：一次检修（同地点 + 同一时段）的共享信息只填一遍，
 * 下面的票种多选决定要批量生成哪几张票。
 */
export default function WorkTicketBatchNewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm<SharedFormValues>();
  const [locationId, setLocationId] = useState<string | null>(null);
  const [period, setPeriod] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [levels, setLevels] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const { data: locations } = useQuery({
    queryKey: ["work-ticket-locations", id],
    queryFn: () => listLocations(id as string),
    enabled: Boolean(id),
  });
  const { data: templates } = useQuery({
    queryKey: ["work-ticket-templates"],
    queryFn: listTemplates,
  });

  const enabledTypes = useMemo(() => {
    const codes = new Set((templates ?? []).map((t) => t.code));
    return ALL_TICKET_TYPES.filter((t) => codes.has(t.code));
  }, [templates]);

  const levelsFor = (code: string) =>
    Array.from(
      new Set(
        (templates ?? [])
          .filter((t) => t.code === code && t.level)
          .map((t) => t.level as string),
      ),
    );

  const templateFor = (code: string, level?: string) => {
    const candidates = (templates ?? []).filter((t) => t.code === code);
    if (levelsFor(code).length > 0) {
      return candidates.find((t) => (t.level ?? null) === (level ?? levelsFor(code)[0]));
    }
    return candidates.find((t) => !t.level) ?? candidates[0];
  };

  const selectedLocation = useMemo(() => {
    if (!locationId || !locations) return null;
    return (
      locations.objects.find((o) => o.id === locationId) ??
      locations.zones.find((z) => z.id === locationId) ??
      null
    );
  }, [locationId, locations]);

  const handleSubmit = async () => {
    if (!id) return;
    const values = await form.validateFields();
    if (selectedTypes.length === 0) {
      message.warning("请至少勾选一种作业票");
      return;
    }
    const specs: BatchTicketSpec[] = [];
    for (const code of selectedTypes) {
      const level = levelsFor(code).length > 0 ? (levels[code] ?? levelsFor(code)[0]) : null;
      const template = templateFor(code, level ?? undefined);
      if (!template) {
        message.error(`未找到 ${code} 的模板，请检查模板种子数据`);
        return;
      }
      specs.push({ ticket_type: code, level, template_id: template.id });
    }
    setSubmitting(true);
    try {
      const isZone = Boolean(locationId && locations?.zones.some((z) => z.id === locationId));
      const batch = await createBatch({
        enterprise_id: id,
        title: values.title,
        zone_id: isZone ? locationId : null,
        risk_object_id: isZone ? null : locationId,
        location_text: selectedLocation?.name ?? null,
        work_period_start: period ? period[0].toISOString() : null,
        work_period_end: period ? period[1].toISOString() : null,
        shared_values: {
          applicant_unit: values.applicant_unit ?? null,
          work_unit: values.work_unit ?? null,
          work_leader: values.work_leader ?? null,
        },
        content_base: values.content_base ?? null,
        risk_basis: values.risk_basis ?? null,
      });
      await addBatchTickets(batch.id, specs);
      message.success(`已生成 ${specs.length} 张草稿票，请逐张补齐专有字段`);
      navigate(`/enterprises/${id}/work-ticket/batches/${batch.id}`);
    } catch (err) {
      message.error(errorDetail(err, "建包失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="新建作业包"
        subtitle="同一次检修的共享信息只填一遍，系统批量生成多张草稿票并互相登记票号"
        onBack={() => navigate(`/enterprises/${id}/work-ticket`)}
      />
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="适用场景：同一作业地点、同一时间段连开多张票（如动火 + 受限空间 + 吊装）"
        description="作业包只减少重复填写，不改变每张票各自的审批流程与提交门禁。"
      />
      <Form form={form} layout="vertical" style={{ maxWidth: 720 }}>
        <Form.Item name="title" label="检修任务名称" rules={[{ required: true, message: "请输入任务名称" }]}>
          <Input placeholder="如：3# 罐区阀门更换" maxLength={200} />
        </Form.Item>
        <Form.Item label="作业地点">
          <Select
            allowClear
            showSearch
            value={locationId}
            onChange={(value) => setLocationId(value ?? null)}
            placeholder="从风险区域/对象中选择（可留空，票面手填）"
            optionFilterProp="label"
            options={[
              ...(locations?.objects ?? []).map((o) => ({
                value: o.id,
                label: `对象：${o.name}${o.location ? `（${o.location}）` : ""}`,
              })),
              ...(locations?.zones ?? []).map((z) => ({ value: z.id, label: `区域：${z.name}` })),
            ]}
          />
        </Form.Item>
        <Form.Item label="作业时段">
          <DatePicker.RangePicker
            showTime
            format="YYYY-MM-DD HH:mm"
            value={period}
            onChange={(value) => setPeriod(value as [dayjs.Dayjs, dayjs.Dayjs] | null)}
          />
        </Form.Item>

        <Divider titlePlacement="left">共享信息（这些内容会写入包内每一张票）</Divider>
        <Form.Item name="applicant_unit" label="作业申请单位">
          <Input placeholder="如：某某化工有限公司" />
        </Form.Item>
        <Form.Item name="work_unit" label="作业单位">
          <Input placeholder="如：维保一队" />
        </Form.Item>
        <Form.Item name="work_leader" label="作业负责人">
          <Input placeholder="如：张三" />
        </Form.Item>
        <Form.Item name="content_base" label="作业任务描述">
          <Input.TextArea rows={2} placeholder="如：更换 3# 罐底阀门" />
        </Form.Item>
        <Form.Item name="risk_basis" label="风险辨识基础">
          <Input.TextArea rows={2} placeholder="如：罐内残留易燃液体，须清洗置换合格" />
        </Form.Item>

        <Divider titlePlacement="left">本次需要办理的作业票</Divider>
        <Checkbox.Group
          value={selectedTypes}
          onChange={(checked) => setSelectedTypes(checked as string[])}
          options={enabledTypes.map((t) => ({ value: t.code, label: t.label }))}
        />
        {selectedTypes.length > 0 && (
          <Space orientation="vertical" size={6} style={{ marginTop: 12, width: "100%" }}>
            {selectedTypes.map((code) => {
              const options = levelsFor(code);
              if (options.length === 0) return null;
              return (
                <Space key={code}>
                  <Text>{ALL_TICKET_TYPES.find((t) => t.code === code)?.label}级别</Text>
                  <Select
                    size="small"
                    style={{ width: 140 }}
                    value={levels[code] ?? options[0]}
                    onChange={(value) => setLevels((prev) => ({ ...prev, [code]: value }))}
                    options={options.map((l) => ({ value: l, label: l }))}
                  />
                </Space>
              );
            })}
          </Space>
        )}

        <div style={{ marginTop: 24 }}>
          <Space>
            <Button onClick={() => navigate(`/enterprises/${id}/work-ticket`)}>取消</Button>
            <Button type="primary" loading={submitting} onClick={handleSubmit}>
              生成草稿票
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  );
}
