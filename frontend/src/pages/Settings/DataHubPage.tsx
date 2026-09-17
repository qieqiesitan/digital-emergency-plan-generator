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
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { createSource, listJobs, listSources } from "@/services/ingestService";
import type { IngestJob, IngestSource } from "@/types/ingest";
import { SOURCE_TYPE_LABELS } from "@/utils/ingestPayload";

const { Text } = Typography;

const JOB_STATUS: Record<string, { color: string; label: string }> = {
  running: { color: "processing", label: "进行中" },
  succeeded: { color: "success", label: "已完成" },
  partial: { color: "warning", label: "部分失败" },
  failed: { color: "error", label: "失败" },
};

export default function DataHubPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const { data: sources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: ["ingest-sources"],
    queryFn: listSources,
  });
  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ["ingest-jobs"],
    queryFn: () => listJobs(),
  });

  const sourceName = (id?: string | null) => sources.find((s) => s.id === id)?.name ?? "—";

  const handleCreate = async (values: Partial<IngestSource>) => {
    setSaving(true);
    try {
      await createSource(values);
      message.success("数据源已创建");
      setCreateOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ["ingest-sources"] });
    } finally {
      setSaving(false);
    }
  };

  const sourceColumns: TableColumnsType<IngestSource> = [
    { title: "名称", dataIndex: "name" },
    {
      title: "类型",
      dataIndex: "source_type",
      width: 120,
      render: (v: string) => SOURCE_TYPE_LABELS[v] ?? v,
    },
    { title: "目标实体", dataIndex: "target_entity", width: 200, render: (v) => v || "—" },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 90,
      render: (v: boolean) => <Tag color={v ? "success" : "default"}>{v ? "启用" : "停用"}</Tag>,
    },
    { title: "创建时间", dataIndex: "created_at", width: 170, render: (v: string | null) => v?.slice(0, 16) ?? "—" },
  ];

  const jobColumns: TableColumnsType<IngestJob> = [
    { title: "来源", dataIndex: "source_id", width: 200, render: (v: string | null) => sourceName(v) },
    { title: "触发", dataIndex: "trigger", width: 100 },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (v: string) => {
        const meta = JOB_STATUS[v] ?? { color: "default", label: v };
        return <Tag color={meta.color}>{meta.label}</Tag>;
      },
    },
    { title: "总数", dataIndex: "total", width: 80 },
    {
      title: "待确认",
      dataIndex: "pending_review",
      width: 90,
      render: (v: number) => (v > 0 ? <Text strong>{v}</Text> : v),
    },
    { title: "已入库", dataIndex: "imported", width: 90 },
    { title: "跳过", dataIndex: "skipped", width: 80 },
    { title: "失败", dataIndex: "failed", width: 80 },
    { title: "创建时间", dataIndex: "created_at", width: 170, render: (v: string | null) => v?.slice(0, 16) ?? "—" },
    {
      title: "操作",
      key: "actions",
      width: 110,
      render: (_, row) => (
        <Button
          type="link"
          size="small"
          disabled={row.pending_review <= 0}
          onClick={() => navigate(`/settings/data-hub/${row.id}/review`)}
        >
          去确认
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="数据接入"
        subtitle="外部数据统一进料口：文件抽取 / 表格导入 / 系统对接；人工确认后才写入业务台账"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ["ingest-sources"] });
              queryClient.invalidateQueries({ queryKey: ["ingest-jobs"] });
            }}
          >
            刷新
          </Button>
        }
      />
      <Card>
        <Tabs
          items={[
            {
              key: "jobs",
              label: "导入任务",
              children: (
                <Table<IngestJob>
                  rowKey="id"
                  size="small"
                  loading={jobsLoading}
                  dataSource={jobs}
                  columns={jobColumns}
                  pagination={{ pageSize: 20, hideOnSinglePage: true }}
                />
              ),
            },
            {
              key: "sources",
              label: "数据源",
              children: (
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                    新建数据源
                  </Button>
                  <Table<IngestSource>
                    rowKey="id"
                    size="small"
                    loading={sourcesLoading}
                    dataSource={sources}
                    columns={sourceColumns}
                    pagination={false}
                  />
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="新建数据源"
        open={createOpen}
        confirmLoading={saving}
        okText="创建"
        onOk={() => form.submit()}
        onCancel={() => {
          setCreateOpen(false);
          form.resetFields();
        }}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate} style={{ marginTop: 12 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请填写名称" }]}>
            <Input maxLength={200} placeholder="如：安全评价报告导入" />
          </Form.Item>
          <Form.Item
            name="source_type"
            label="类型"
            rules={[{ required: true, message: "请选择类型" }]}
          >
            <Select
              options={Object.entries(SOURCE_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="target_entity" label="目标实体">
            <Input maxLength={60} placeholder="如：major_hazard_unit_chemical（可留空）" />
          </Form.Item>
          <Form.Item
            name="secret_ref"
            label="密钥引用"
            extra="只填 third_party_config 里的键名，不在此处录入明文密钥"
          >
            <Input maxLength={120} placeholder="如：third_party.xxx.token（可留空）" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
