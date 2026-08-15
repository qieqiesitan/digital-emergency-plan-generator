import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Upload,
} from "antd";
import type { TableColumnsType, UploadProps } from "antd";
import {
  CheckSquareOutlined,
  DashboardOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileTextOutlined,
  PlusOutlined,
  ScheduleOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  aiRecordAssist,
  createRecord,
  exportHazardLedger,
  getHazardDashboard,
  listRecords,
} from "@/services/hazardService";
import { uploadFile } from "@/services/enterpriseService";
import type { HazardRecordListItem, HazardSourceType } from "@/types/hazard";

interface Props {
  enterpriseId: string;
}

const SOURCE_TYPE_LABELS: Record<HazardSourceType, string> = {
  inspection: "排查",
  report: "上报",
  regulatory: "监管检查",
  accident: "事故",
  manual: "手工",
};

const SOURCE_TYPE_OPTIONS = (Object.keys(SOURCE_TYPE_LABELS) as HazardSourceType[]).map(code => ({
  value: code,
  label: SOURCE_TYPE_LABELS[code],
}));

const STATUS_OPTIONS = [
  { value: "registered", label: "已登记" },
  { value: "grading", label: "待分级" },
  { value: "pending_approval", label: "待审批" },
  { value: "rectifying", label: "整改中" },
  { value: "reviewing", label: "复查中" },
  { value: "second_review", label: "二次复核" },
  { value: "closed", label: "已销号" },
];

const LEVEL_OPTIONS = [
  { value: "major", label: "重大" },
  { value: "general", label: "一般" },
];

// 与数据字典 hazard_type 系统种子码值一致（db_migration_data_dicts.sql）
const HAZARD_TYPE_LABELS: Record<string, string> = {
  equipment: "设备设施",
  fire: "消防",
  behavior: "作业行为",
  management: "管理缺陷",
  environment: "环境",
  other: "其他",
};

const STATUS_TAG_COLORS: Record<string, string> = {
  registered: "default",
  grading: "orange",
  pending_approval: "gold",
  rectifying: "blue",
  reviewing: "cyan",
  second_review: "purple",
  closed: "green",
};

interface ListFilters {
  status?: string;
  level?: string;
  source_type?: string;
  scope?: string;
  q?: string;
}

export default function HazardInspectionTab({ enterpriseId }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [filters, setFilters] = useState<ListFilters>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [photoUrls, setPhotoUrls] = useState<string[]>([]);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["hazard-records", enterpriseId, filters],
    queryFn: () => listRecords(enterpriseId, filters),
    enabled: !!enterpriseId,
  });
  const { data: dashboard } = useQuery({
    queryKey: ["hazard-dashboard", enterpriseId],
    queryFn: () => getHazardDashboard(enterpriseId),
    enabled: !!enterpriseId,
  });

  const metrics = dashboard?.metrics;
  const items = data?.items ?? [];

  const patchFilters = (patch: Partial<ListFilters>) => {
    setFilters(f => ({ ...f, ...patch }));
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const res = await exportHazardLedger(enterpriseId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "hazard_ledger.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success("台账导出成功");
    } catch {
      message.error("导出失败，请稍后重试");
    } finally {
      setExporting(false);
    }
  };

  const handleAiFill = async () => {
    const description = (form.getFieldValue("description") || "").toString().trim();
    if (!description) {
      message.warning("请先填写隐患描述");
      return;
    }
    setAiLoading(true);
    try {
      const result = await aiRecordAssist(enterpriseId, { description });
      if (result.available && result.title) {
        form.setFieldsValue({
          title: result.title,
          hazard_type: result.hazard_type || undefined,
        });
        message.success(`AI 已预填标题与分类（建议等级：${result.suggested_level || "—"}），请核对后保存`);
      } else {
        message.warning(result.note || "AI 暂不可用，请手动填写");
      }
    } catch (e) {
      message.error("AI 填写失败: " + (e instanceof Error ? e.message : "未知错误"));
    } finally {
      setAiLoading(false);
    }
  };

  const uploadProps: UploadProps = {
    multiple: true,
    customRequest: ({ file, onSuccess, onError }) => {
      void uploadFile(file as File)
        .then(url => {
          setPhotoUrls(prev => [...prev, url]);
          onSuccess?.(url);
        })
        .catch(e => onError?.(e as Error));
    },
    onRemove: file => {
      setPhotoUrls(prev => prev.filter(u => u !== file.uid));
      return true;
    },
    fileList: photoUrls.map(url => ({
      uid: url,
      name: decodeURIComponent(url.split("/").pop() || "photo"),
      status: "done" as const,
      url,
    })),
  };

  const handleCreate = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    try {
      await createRecord(enterpriseId, {
        source_type: values.source_type as HazardSourceType,
        title: String(values.title || "").trim(),
        description: String(values.description || "").trim(),
        hazard_type: (values.hazard_type as string | undefined) || null,
        location: (values.location as string | undefined)?.trim() || null,
        photo_urls: photoUrls.length ? photoUrls : undefined,
      });
      message.success("隐患登记成功");
      setCreateOpen(false);
      form.resetFields();
      setPhotoUrls([]);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["hazard-dashboard", enterpriseId] });
    } catch (e) {
      message.error("登记失败: " + (e instanceof Error ? e.message : "未知错误"));
    } finally {
      setSubmitting(false);
    }
  };

  const statCards: Array<{ title: string; value: number | string }> = [
    { title: "未闭环隐患", value: metrics?.open_hazards ?? "—" },
    { title: "重大隐患", value: metrics?.major_count ?? "—" },
    { title: "超期未整改", value: metrics?.overdue_count ?? "—" },
    { title: "扫码待确认", value: metrics?.scan_pending ?? "—" },
  ];

  const columns: TableColumnsType<HazardRecordListItem> = [
    { title: "编号", dataIndex: "code", width: 100 },
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (title: string, row) => (
        <a onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/records/${row.id}`)}>{title}</a>
      ),
    },
    {
      title: "类型",
      dataIndex: "hazard_type",
      width: 110,
      render: (v: string | null) => (v ? HAZARD_TYPE_LABELS[v] || v : "—"),
    },
    {
      title: "等级",
      dataIndex: "level",
      width: 90,
      render: (v: string | null, row) => (
        v ? <Tag color={v === "major" ? "red" : "blue"}>{row.level_label}</Tag> : <span>—</span>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: string, row) => <Tag color={STATUS_TAG_COLORS[v] || "default"}>{row.status_label}</Tag>,
    },
    {
      title: "来源",
      dataIndex: "source_type",
      width: 100,
      render: (_v: string, row) => row.source_type_label,
    },
    { title: "整改期限", dataIndex: "deadline", width: 110, render: (v: string | null) => v || "—" },
    { title: "创建时间", dataIndex: "created_at", width: 160, render: (v: string) => v?.slice(0, 16) || "—" },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_v, row) => (
        <Button type="link" size="small" onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/records/${row.id}`)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space wrap style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建隐患
        </Button>
        <Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>
          导出台账
        </Button>
        <Button icon={<ScheduleOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/plans`)}>
          排查计划
        </Button>
        <Button icon={<CheckSquareOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/tasks`)}>
          排查任务
        </Button>
        <Button icon={<FileTextOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/templates`)}>
          检查表模板
        </Button>
        <Button icon={<DashboardOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/dashboard`)}>
          驾驶舱
        </Button>
        <Button icon={<EyeOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/publicity`)}>
          隐患公示
        </Button>
      </Space>

      <Space size={12} wrap style={{ marginBottom: 16 }}>
        {statCards.map(s => (
          <Card key={s.title} size="small" style={{ minWidth: 140, textAlign: "center" }}>
            <Statistic title={s.title} value={s.value} />
          </Card>
        ))}
      </Space>

      <Space wrap style={{ marginBottom: 12 }}>
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 130 }}
          options={STATUS_OPTIONS}
          value={filters.status}
          onChange={v => patchFilters({ status: v })}
        />
        <Select
          placeholder="等级"
          allowClear
          style={{ width: 110 }}
          options={LEVEL_OPTIONS}
          value={filters.level}
          onChange={v => patchFilters({ level: v })}
        />
        <Select
          placeholder="来源"
          allowClear
          style={{ width: 130 }}
          options={SOURCE_TYPE_OPTIONS}
          value={filters.source_type}
          onChange={v => patchFilters({ source_type: v })}
        />
        <Select
          placeholder="超期"
          allowClear
          style={{ width: 110 }}
          options={[{ value: "overdue", label: "整改超期" }]}
          value={filters.scope}
          onChange={v => patchFilters({ scope: v })}
        />
        <Input.Search
          placeholder="编号 / 标题 / 描述关键词"
          allowClear
          style={{ width: 260 }}
          onSearch={v => patchFilters({ q: v || undefined })}
        />
        <Button onClick={() => setFilters({})}>重置</Button>
      </Space>

      <Table
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={items}
        loading={isLoading}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
      />

      <Modal
        title="新建隐患"
        open={createOpen}
        confirmLoading={submitting}
        okText="提交登记"
        onOk={() => form.submit()}
        onCancel={() => {
          setCreateOpen(false);
          form.resetFields();
          setPhotoUrls([]);
        }}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate} style={{ marginTop: 12 }}>
          <Form.Item
            name="source_type"
            label="来源渠道"
            rules={[{ required: true, message: "请选择来源渠道" }]}
          >
            <Select options={SOURCE_TYPE_OPTIONS} placeholder="请选择来源渠道" />
          </Form.Item>
          <Form.Item name="description" label="隐患描述" rules={[{ required: true, message: "请填写隐患描述" }]}>
            <Input.TextArea rows={3} placeholder="描述隐患情况（用于 AI 预填标题与分类）" />
          </Form.Item>
          <Form.Item>
            <Button type="dashed" icon={<ThunderboltOutlined />} loading={aiLoading} onClick={handleAiFill} block>
              AI 智能填写
            </Button>
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: "请填写标题" }]}>
            <Input maxLength={255} placeholder="隐患标题" />
          </Form.Item>
          <Form.Item name="hazard_type" label="隐患类型">
            <Select
              allowClear
              placeholder="选择隐患类型"
              options={Object.entries(HAZARD_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="location" label="位置">
            <Input maxLength={500} placeholder="隐患位置（可选）" />
          </Form.Item>
          <Form.Item label="现场照片">
            <Upload {...uploadProps} accept="image/*">
              <Button icon={<PlusOutlined />}>上传照片</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
