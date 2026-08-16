import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
} from "antd";
import type { TableColumnsType } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import AppIcon from "@/components/common/AppIcon";
import {
  aiScheduleSuggestion,
  createHazardPlan,
  deleteHazardPlan,
  listHazardPlans,
  listHazardTemplates,
  updateHazardPlan,
} from "@/services/hazardService";
import { listMembers } from "@/services/enterpriseOrgService";
import { listZones } from "@/services/riskManagementService";
import type { HazardInspectionPlan, HazardScheduleSuggestionResult } from "@/types/hazard";
import { PageHeader } from "@/components/common/PageHeader";

const CATEGORY_LABELS: Record<string, string> = {
  daily: "日常",
  comprehensive: "综合",
  special: "专项",
  holiday: "节假日",
};

const CATEGORY_COLORS: Record<string, string> = {
  daily: "blue",
  comprehensive: "purple",
  special: "orange",
  holiday: "gold",
};

const FREQUENCY_LABELS: Record<string, string> = {
  daily: "每日",
  weekly: "每周",
  monthly: "每月",
  custom: "自定义",
};

const WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

interface PlanFormValues {
  name: string;
  category: string;
  frequency: string;
  weekdays?: number[];
  zone_ids: string[];
  responsible_user_id?: string;
  template_id?: string;
  enabled: boolean;
}

function formatFrequency(plan: HazardInspectionPlan): string {
  const base = FREQUENCY_LABELS[plan.frequency] || plan.frequency;
  if ((plan.frequency === "weekly" || plan.frequency === "custom") && plan.weekdays?.length) {
    const days = plan.weekdays
      .map(d => WEEKDAY_LABELS[d - 1])
      .filter(Boolean)
      .join("、");
    return days ? `${base}（${days}）` : base;
  }
  return base;
}

/** 构造计划表单草稿文本，作为 /ai/schedule-suggestion 的 plan_draft 输入。 */
function buildPlanDraft(
  values: PlanFormValues,
  zoneNameMap: Record<string, string>,
  memberNameMap: Record<string, string>,
): string {
  const zoneNames = (values.zone_ids || [])
    .map(id => zoneNameMap[id])
    .filter(Boolean)
    .join("、");
  const parts = [
    `计划名称：${values.name || "（未填）"}`,
    `计划类别：${CATEGORY_LABELS[values.category] || values.category || "（未选）"}`,
    `排查频次：${FREQUENCY_LABELS[values.frequency] || values.frequency || "（未选）"}`,
    `覆盖分区：${zoneNames || "（未选）"}`,
  ];
  if (values.responsible_user_id) {
    parts.push(`默认责任人：${memberNameMap[values.responsible_user_id] || ""}`);
  }
  return parts.join("；");
}

/** 排查计划配置页（§6）：计划 CRUD + 启用开关 + AI 排程建议卡。 */
export default function HazardPlanPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm<PlanFormValues>();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<HazardInspectionPlan | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<HazardScheduleSuggestionResult | null>(null);

  const frequency = Form.useWatch("frequency", form);

  const { data: plans = [], isLoading, refetch } = useQuery({
    queryKey: ["hazard-plans", enterpriseId],
    queryFn: () => listHazardPlans(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: zones = [] } = useQuery({
    queryKey: ["risk-zones", enterpriseId],
    queryFn: () => listZones(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: members = [] } = useQuery({
    queryKey: ["enterprise-members", enterpriseId],
    queryFn: () => listMembers(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: templates = [] } = useQuery({
    queryKey: ["hazard-templates", enterpriseId],
    queryFn: () => listHazardTemplates(enterpriseId),
    enabled: !!enterpriseId,
  });

  const enabledMembers = useMemo(() => members.filter(m => m.enabled), [members]);
  const zoneNameMap = useMemo(
    () => Object.fromEntries(zones.map(z => [z.id, z.name])),
    [zones],
  );
  const memberNameMap = useMemo(
    () => Object.fromEntries(members.map(m => [m.user_id, m.name || m.email || m.user_id])),
    [members],
  );

  const zoneOptions = useMemo(
    () => zones.map(z => ({ label: z.name, value: z.id })),
    [zones],
  );
  const memberOptions = useMemo(
    () =>
      enabledMembers.map(m => ({
        value: m.user_id,
        label: m.name || m.email || m.user_id,
      })),
    [enabledMembers],
  );
  const templateOptions = useMemo(
    () =>
      templates.map(t => ({
        value: t.id,
        label: `${t.name}（${CATEGORY_LABELS[t.category] || t.category}${t.source === "system" ? "·系统" : ""}）`,
      })),
    [templates],
  );

  const openCreate = () => {
    setEditingPlan(null);
    setSuggestion(null);
    form.setFieldsValue({
      name: "",
      category: undefined,
      frequency: undefined,
      weekdays: undefined,
      zone_ids: [],
      responsible_user_id: undefined,
      template_id: undefined,
      enabled: true,
    });
    setModalOpen(true);
  };

  const openEdit = (plan: HazardInspectionPlan) => {
    setEditingPlan(plan);
    setSuggestion(null);
    form.setFieldsValue({
      name: plan.name,
      category: plan.category,
      frequency: plan.frequency,
      weekdays: plan.weekdays ?? undefined,
      zone_ids: plan.zone_ids,
      responsible_user_id: plan.responsible_user_id ?? undefined,
      template_id: plan.template_id ?? undefined,
      enabled: plan.enabled,
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingPlan(null);
    setSuggestion(null);
    form.resetFields();
  };

  const handleAiSuggest = async () => {
    const values = form.getFieldsValue() as PlanFormValues;
    if (!values.name?.trim() || !values.category || !values.frequency || !values.zone_ids?.length) {
      message.warning("请先填写计划名称、类别、频次并选择覆盖分区");
      return;
    }
    setAiLoading(true);
    try {
      const result = await aiScheduleSuggestion(enterpriseId, {
        plan_draft: buildPlanDraft(values, zoneNameMap, memberNameMap),
      });
      setSuggestion(result);
      if (!result.available) {
        message.warning(result.note || "AI 暂不可用，请手动配置计划");
      }
    } catch (e) {
      message.error("获取 AI 建议失败: " + extractDetail(e));
    } finally {
      setAiLoading(false);
    }
  };

  const handleAdoptSuggestion = () => {
    if (!suggestion?.available) return;
    const patch: Partial<PlanFormValues> = {};
    if (suggestion.suggested_frequency) {
      patch.frequency = suggestion.suggested_frequency;
      if (suggestion.suggested_frequency !== "weekly" && suggestion.suggested_frequency !== "custom") {
        patch.weekdays = undefined;
      }
    }
    if (suggestion.suggested_responsible_user_id) {
      patch.responsible_user_id = suggestion.suggested_responsible_user_id;
    }
    form.setFieldsValue(patch);
    message.success("已采纳 AI 建议，请核对后保存");
  };

  const handleSave = async (values: PlanFormValues) => {
    setSubmitting(true);
    try {
      const isWeeklyOrCustom = values.frequency === "weekly" || values.frequency === "custom";
      const payload = {
        name: values.name.trim(),
        category: values.category,
        frequency: values.frequency,
        weekdays: isWeeklyOrCustom ? values.weekdays : undefined,
        zone_ids: values.zone_ids,
        responsible_user_id: values.responsible_user_id || null,
        template_id: values.template_id || null,
        enabled: values.enabled,
      };
      if (editingPlan) {
        await updateHazardPlan(enterpriseId, editingPlan.id, payload);
        message.success("计划已更新");
      } else {
        await createHazardPlan(enterpriseId, payload);
        message.success("计划已创建");
      }
      closeModal();
      refetch();
      queryClient.invalidateQueries({ queryKey: ["hazard-plans", enterpriseId] });
    } catch (e) {
      message.error(extractDetail(e) || "保存失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleEnabled = async (plan: HazardInspectionPlan, enabled: boolean) => {
    try {
      await updateHazardPlan(enterpriseId, plan.id, { enabled });
      message.success(enabled ? "计划已启用" : "计划已停用");
      refetch();
    } catch (e) {
      message.error(extractDetail(e) || "切换失败，请稍后重试");
      refetch();
    }
  };

  const handleDelete = async (plan: HazardInspectionPlan) => {
    try {
      await deleteHazardPlan(enterpriseId, plan.id);
      message.success("计划已删除");
      refetch();
    } catch (e) {
      message.error(extractDetail(e) || "删除失败，请稍后重试");
    }
  };

  const columns: TableColumnsType<HazardInspectionPlan> = [
    { title: "计划名称", dataIndex: "name", ellipsis: true },
    {
      title: "类别",
      dataIndex: "category",
      width: 90,
      render: (v: string) => (
        <Tag color={CATEGORY_COLORS[v] || "default"}>{CATEGORY_LABELS[v] || v}</Tag>
      ),
    },
    {
      title: "频次",
      dataIndex: "frequency",
      width: 150,
      render: (_v: string, row) => formatFrequency(row),
    },
    {
      title: "责任人",
      dataIndex: "responsible_user_id",
      width: 110,
      ellipsis: true,
      render: (v: string | null) => (v ? memberNameMap[v] || "—" : "—"),
    },
    {
      title: "覆盖分区",
      dataIndex: "zone_ids",
      width: 110,
      render: (ids: string[]) => {
        const names = ids.map(id => zoneNameMap[id]).filter(Boolean);
        return (
          <Tooltip title={names.length ? names.join("、") : "—"}>
            <span>{ids.length} 个</span>
          </Tooltip>
        );
      },
    },
    {
      title: "启用",
      dataIndex: "enabled",
      width: 80,
      render: (enabled: boolean, row) => (
        <Switch size="small" checked={enabled} onChange={checked => void handleToggleEnabled(row, checked)} />
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_v, row) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => openEdit(row)}>
            编辑
          </Button>
          <Popconfirm
            title="删除计划"
            description="删除后计划将停用，历史任务与隐患记录保留"
            okText="删除"
            cancelText="取消"
            onConfirm={() => void handleDelete(row)}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const needWeekdays = frequency === "weekly" || frequency === "custom";
  const suggestionMemberName = suggestion?.suggested_responsible_user_id
    ? memberNameMap[suggestion.suggested_responsible_user_id]
    : null;

  return (
    <div>
      <PageHeader
        title="排查计划"
        subtitle="配置排查计划、覆盖分区与责任人；AI 排程建议仅供参考，需人工确认后保存"
        onBack={() => navigate(-1)}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建计划
          </Button>
        }
      />

      <Table
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={plans}
        loading={isLoading}
        locale={{ emptyText: "暂无排查计划" }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
      />

      <Modal
        title={editingPlan ? "编辑计划" : "新建计划"}
        open={modalOpen}
        confirmLoading={submitting}
        okText="保存"
        width={560}
        onOk={() => form.submit()}
        onCancel={closeModal}
      >
        <Form form={form} layout="vertical" onFinish={values => void handleSave(values)} style={{ marginTop: 12 }}>
          <Space direction="vertical" style={{ width: "100%", marginBottom: 4 }}>
            <Button icon={<AppIcon name="ai" size={14} />} loading={aiLoading} onClick={() => void handleAiSuggest()} block>
              获取 AI 排程建议
            </Button>
            {suggestion &&
              (suggestion.available ? (
                <Alert
                  type="success"
                  showIcon
                  message="AI 排程建议"
                  description={
                    <div>
                      <div>
                        建议频次：
                        {FREQUENCY_LABELS[suggestion.suggested_frequency || ""] ||
                          suggestion.suggested_frequency ||
                          "—"}
                      </div>
                      <div>
                        建议责任人：
                        {suggestion.suggested_responsible_user_id
                          ? suggestionMemberName || "（成员已停用或不存在）"
                          : "—"}
                      </div>
                      <div>理由：{suggestion.reason || "—"}</div>
                    </div>
                  }
                  action={
                    <Button size="small" type="primary" onClick={handleAdoptSuggestion}>
                      采纳
                    </Button>
                  }
                />
              ) : (
                <Alert type="warning" showIcon message="AI 暂不可用" description={suggestion.note || "请手动配置计划"} />
              ))}
          </Space>

          <Form.Item name="name" label="计划名称" rules={[{ required: true, message: "请填写计划名称" }]}>
            <Input maxLength={255} placeholder="如：生产车间日排查" />
          </Form.Item>
          <Form.Item name="category" label="计划类别" rules={[{ required: true, message: "请选择计划类别" }]}>
            <Select
              placeholder="请选择计划类别"
              options={Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="frequency" label="排查频次" rules={[{ required: true, message: "请选择排查频次" }]}>
            <Select
              placeholder="请选择排查频次"
              options={Object.entries(FREQUENCY_LABELS).map(([value, label]) => ({ value, label }))}
              onChange={v => {
                if (v !== "weekly" && v !== "custom") {
                  form.setFieldValue("weekdays", undefined);
                }
              }}
            />
          </Form.Item>
          {needWeekdays && (
            <Form.Item
              name="weekdays"
              label="执行星期"
              rules={[{ required: true, message: "请选择执行星期" }]}
            >
              <Select
                mode="multiple"
                placeholder="选择每周执行的星期"
                options={WEEKDAY_LABELS.map((label, idx) => ({ value: idx + 1, label }))}
              />
            </Form.Item>
          )}
          <Form.Item name="zone_ids" label="覆盖分区" rules={[{ required: true, message: "请选择覆盖分区" }]}>
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              placeholder="选择风险分区（多选）"
              options={zoneOptions}
            />
          </Form.Item>
          <Form.Item name="responsible_user_id" label="默认责任人">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="选择企业启用成员（可选）"
              options={memberOptions}
            />
          </Form.Item>
          <Form.Item name="template_id" label="关联检查表模板">
            <Select allowClear placeholder="选择检查表模板（可选）" options={templateOptions} />
          </Form.Item>
          <Form.Item name="enabled" label="启用计划" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
