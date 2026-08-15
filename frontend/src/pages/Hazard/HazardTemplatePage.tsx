import { useState } from "react";
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
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  aiChecklistTemplate,
  copyHazardTemplate,
  createHazardTemplate,
  deleteHazardTemplate,
  listHazardTemplates,
  updateHazardTemplate,
} from "@/services/hazardService";
import type { HazardChecklistTemplate, HazardChecklistTemplateItem } from "@/types/hazard";
import { PageHeader } from "@/components/common/PageHeader";

const { Text } = Typography;

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

const CATEGORY_OPTIONS = (Object.keys(CATEGORY_LABELS) as string[]).map(code => ({
  value: code,
  label: CATEGORY_LABELS[code],
}));

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

interface TemplateFormValues {
  name: string;
  category: string;
  items: HazardChecklistTemplateItem[];
}

/** 检查表模板管理页（§7）：系统+企业合并列表、企业 CRUD、复制系统模板、AI 生成。 */
export default function HazardTemplatePage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm<TemplateFormValues>();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<HazardChecklistTemplate | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiIndustry, setAiIndustry] = useState("");
  const [aiRiskPoints, setAiRiskPoints] = useState("");

  const { data: templates = [], isLoading, refetch } = useQuery({
    queryKey: ["hazard-templates", enterpriseId],
    queryFn: () => listHazardTemplates(enterpriseId),
    enabled: !!enterpriseId,
  });

  const openCreate = () => {
    setEditing(null);
    setAiIndustry("");
    setAiRiskPoints("");
    form.setFieldsValue({
      name: "",
      category: undefined,
      items: [{ content: "", expected_note: "" }],
    });
    setModalOpen(true);
  };

  const openEdit = (tpl: HazardChecklistTemplate) => {
    setEditing(tpl);
    setAiIndustry("");
    setAiRiskPoints("");
    form.setFieldsValue({
      name: tpl.name,
      category: tpl.category,
      items: (tpl.items || []).map(i => ({
        content: i.content,
        expected_note: i.expected_note ?? "",
      })),
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const handleAiGenerate = async () => {
    const industry = aiIndustry.trim();
    if (!industry) {
      message.warning("请先填写行业");
      return;
    }
    setAiLoading(true);
    try {
      const result = await aiChecklistTemplate(enterpriseId, {
        industry,
        risk_points: aiRiskPoints.trim(),
      });
      if (result.available && result.items.length) {
        form.setFieldValue(
          "items",
          result.items.map(i => ({ content: i.content, expected_note: i.expected_note ?? "" })),
        );
        message.success(`AI 已生成 ${result.items.length} 个核对项，请核对后保存`);
      } else {
        message.warning(result.note || "AI 暂不可用，请手动填写核对项");
      }
    } catch (e) {
      // AI 失败降级不阻塞（§16）：仅提示，保留用户已填内容
      message.error("AI 生成失败: " + extractDetail(e));
    } finally {
      setAiLoading(false);
    }
  };

  const handleSave = async (values: TemplateFormValues) => {
    if (!values.items?.length) {
      message.warning("请至少添加一个核对项");
      return;
    }
    const payload = {
      name: values.name.trim(),
      category: values.category,
      items: values.items.map(i => ({
        content: i.content.trim(),
        expected_note: i.expected_note?.trim() || null,
      })),
    };
    setSubmitting(true);
    try {
      if (editing) {
        await updateHazardTemplate(enterpriseId, editing.id, payload);
        message.success("模板已更新");
      } else {
        await createHazardTemplate(enterpriseId, payload);
        message.success("模板已创建");
      }
      setModalOpen(false);
      setEditing(null);
      form.resetFields();
      void queryClient.invalidateQueries({ queryKey: ["hazard-templates"] });
    } catch (e) {
      message.error(extractDetail(e) || "保存失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async (tpl: HazardChecklistTemplate) => {
    try {
      await copyHazardTemplate(enterpriseId, tpl.id);
      message.success(`已复制为「${tpl.name}」企业模板，可继续编辑`);
      void refetch();
    } catch (e) {
      message.error(extractDetail(e) || "复制失败");
    }
  };

  const handleDelete = async (tpl: HazardChecklistTemplate) => {
    try {
      await deleteHazardTemplate(enterpriseId, tpl.id);
      message.success("模板已删除");
      void refetch();
    } catch (e) {
      message.error(extractDetail(e) || "删除失败");
    }
  };

  const columns: TableColumnsType<HazardChecklistTemplate> = [
    { title: "模板名称", dataIndex: "name", ellipsis: true },
    {
      title: "类别",
      dataIndex: "category",
      width: 100,
      render: (v: string) => (
        <Tag color={CATEGORY_COLORS[v] || "default"}>{CATEGORY_LABELS[v] || v}</Tag>
      ),
    },
    {
      title: "核对项数",
      width: 90,
      render: (_, row) => row.items?.length ?? 0,
    },
    {
      title: "来源",
      width: 110,
      render: (_, row) =>
        row.source === "system" ? <Tag>系统模板</Tag> : <Tag color="green">企业模板</Tag>,
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 110,
      render: (v: string) => (v ? v.slice(0, 10) : "—"),
    },
    {
      title: "操作",
      width: 190,
      render: (_, row) => (
        <Space size={4}>
          {row.source === "enterprise" ? (
            <>
              <Button
                type="link"
                size="small"
                icon={<EditOutlined />}
                onClick={() => openEdit(row)}
              >
                编辑
              </Button>
              <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => void handleCopy(row)}>
                复制
              </Button>
              <Popconfirm
                title="确认删除该模板？"
                description="删除后不可恢复，已关联计划的引用不受影响。"
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
                onConfirm={() => void handleDelete(row)}
              >
                <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            </>
          ) : (
            <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => void handleCopy(row)}>
              复制为可编辑
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="检查表模板"
        subtitle="系统模板与企业模板合并展示（企业同名模板优先）；系统模板需复制后编辑"
        onBack={() => navigate(-1)}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建模板
          </Button>
        }
      />

      <Table<HazardChecklistTemplate>
        rowKey="id"
        dataSource={templates}
        columns={columns}
        size="middle"
        loading={isLoading}
        pagination={{ pageSize: 10, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: "暂无模板，可新建或复制系统模板" }}
        scroll={{ x: 760 }}
      />

      <Modal
        title={editing ? "编辑模板" : "新建模板"}
        open={modalOpen}
        onOk={() => form.submit()}
        onCancel={closeModal}
        confirmLoading={submitting}
        okText="保存"
        cancelText="取消"
        width={720}
      >
        <Form<TemplateFormValues>
          form={form}
          layout="vertical"
          onFinish={values => void handleSave(values)}
          style={{ marginTop: 8 }}
        >
          <Space.Compact style={{ width: "100%", marginBottom: 16 }}>
            <Input
              placeholder="行业（如：机械制造、危化品储运）"
              value={aiIndustry}
              onChange={e => setAiIndustry(e.target.value)}
            />
            <Input
              placeholder="风险点/措施（可选）"
              value={aiRiskPoints}
              onChange={e => setAiRiskPoints(e.target.value)}
            />
            <Button icon={<RobotOutlined />} loading={aiLoading} onClick={() => void handleAiGenerate()}>
              AI 生成核对项
            </Button>
          </Space.Compact>

          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="AI 生成结果会预填下方核对项，可继续手动增删改；AI 不可用时不影响手动填写。"
          />

          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: "请输入模板名称" }]}>
            <Input placeholder="如：日常检查表" maxLength={255} showCount />
          </Form.Item>
          <Form.Item name="category" label="模板类别" rules={[{ required: true, message: "请选择模板类别" }]}>
            <Select options={CATEGORY_OPTIONS} placeholder="请选择类别" />
          </Form.Item>

          <Form.List name="items">
            {(fields, { add, remove }) => (
              <>
                <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                  核对项（内容必填，达标标准可选）
                </Text>
                {fields.map(({ key, name }) => (
                  <div key={key} style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 8 }}>
                    <Form.Item
                      name={[name, "content"]}
                      rules={[{ required: true, message: "请填写核对项内容" }]}
                      style={{ flex: 1, marginBottom: 0 }}
                    >
                      <Input placeholder="核对项内容（如：检查配电箱门是否完好）" maxLength={1000} />
                    </Form.Item>
                    <Form.Item name={[name, "expected_note"]} style={{ flex: 1, marginBottom: 0 }}>
                      <Input placeholder="达标标准（可选）" maxLength={1000} />
                    </Form.Item>
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => remove(name)}
                      disabled={fields.length === 1}
                    />
                  </div>
                ))}
                <Button
                  type="dashed"
                  block
                  icon={<PlusOutlined />}
                  onClick={() => add({ content: "", expected_note: "" })}
                >
                  添加核对项
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
}
