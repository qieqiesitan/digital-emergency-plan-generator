import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Descriptions,
  Form,
  Image,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Upload,
} from "antd";
import type { TableColumnsType, UploadProps } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  getHazardTask,
  listHazardTasks,
  submitHazardTask,
  taskToRecord,
} from "@/services/hazardService";
import { listMembers } from "@/services/enterpriseOrgService";
import { uploadFile } from "@/services/enterpriseService";
import type {
  HazardInspectionItem,
  HazardInspectionTask,
  HazardTaskStatus,
} from "@/types/hazard";
import { PageHeader } from "@/components/common/PageHeader";

const TASK_STATUS_LABELS: Record<HazardTaskStatus, string> = {
  pending: "待执行",
  processing: "进行中",
  done: "已完成",
  overdue: "已超期",
};

const TASK_STATUS_COLORS: Record<HazardTaskStatus, string> = {
  pending: "default",
  processing: "blue",
  done: "green",
  overdue: "red",
};

const ITEM_RESULT_LABELS: Record<string, string> = {
  pending: "未核对",
  normal: "正常",
  abnormal: "异常",
  na: "不适用",
};

const ITEM_RESULT_OPTIONS = (Object.keys(ITEM_RESULT_LABELS) as string[]).map(value => ({
  value,
  label: ITEM_RESULT_LABELS[value],
}));

const STATUS_OPTIONS = (Object.keys(TASK_STATUS_LABELS) as HazardTaskStatus[]).map(value => ({
  value,
  label: TASK_STATUS_LABELS[value],
}));

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

/** 超期口径与后端一致：status=overdue，或未完成（pending/processing）且 due_at 已过。 */
function isTaskOverdue(task: HazardInspectionTask, now: number): boolean {
  if (task.status === "overdue") return true;
  if (task.status === "pending" || task.status === "processing") {
    return new Date(task.due_at).getTime() < now;
  }
  return false;
}

/** 异常项照片上传（复用登记页 Upload + uploadFile 惯例）。 */
function ItemPhotoUpload({
  value = [],
  onChange,
  disabled,
}: {
  value?: string[];
  onChange?: (urls: string[]) => void;
  disabled?: boolean;
}) {
  const uploadProps: UploadProps = {
    multiple: true,
    disabled,
    customRequest: ({ file, onSuccess, onError }) => {
      void uploadFile(file as File)
        .then(url => {
          onChange?.([...value, url]);
          onSuccess?.(url);
        })
        .catch(e => onError?.(e as Error));
    },
    onRemove: file => {
      onChange?.(value.filter(u => u !== file.uid));
      return true;
    },
    fileList: value.map(url => ({
      uid: url,
      name: decodeURIComponent(url.split("/").pop() || "photo"),
      status: "done" as const,
      url,
    })),
  };
  return (
    <Upload {...uploadProps} accept="image/*">
      <Button size="small" icon={<PlusOutlined />} disabled={disabled}>
        上传照片
      </Button>
    </Upload>
  );
}

type ListFilters = Record<string, unknown>;

/** 任务执行页（§6）：任务列表筛选 + 清单逐项核对 + 一键转隐患。 */
export default function HazardTaskPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [filters, setFilters] = useState<ListFilters>({});
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailTaskId, setDetailTaskId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, { result?: string; remark?: string; photo_urls?: string[] }>>({});
  const [submitting, setSubmitting] = useState(false);
  const [toRecordOpen, setToRecordOpen] = useState(false);
  const [toRecordItem, setToRecordItem] = useState<HazardInspectionItem | null>(null);
  const [toRecordSubmitting, setToRecordSubmitting] = useState(false);
  const [toRecordForm] = Form.useForm<{ title: string; description: string }>();

  const { data: tasks = [], isLoading, refetch } = useQuery({
    queryKey: ["hazard-tasks", enterpriseId, filters],
    queryFn: () => listHazardTasks(enterpriseId, filters),
    enabled: !!enterpriseId,
  });
  const { data: members = [] } = useQuery({
    queryKey: ["enterprise-members", enterpriseId],
    queryFn: () => listMembers(enterpriseId),
    enabled: !!enterpriseId,
  });
  const {
    data: detail,
    isLoading: detailLoading,
    refetch: refetchDetail,
  } = useQuery({
    queryKey: ["hazard-task-detail", enterpriseId, detailTaskId],
    queryFn: () => getHazardTask(enterpriseId, detailTaskId as string),
    enabled: detailOpen && !!detailTaskId,
  });

  // 超期判断的当前时间：惰性初始化 + 定时刷新（render 保持纯函数），每分钟重算一次
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  const memberNameMap = useMemo(
    () => Object.fromEntries(members.map(m => [m.user_id, m.name || m.email || m.user_id])),
    [members],
  );
  const memberOptions = useMemo(
    () =>
      members
        .filter(m => m.enabled)
        .map(m => ({ value: m.user_id, label: m.name || m.email || m.user_id })),
    [members],
  );

  const openDetail = (task: HazardInspectionTask) => {
    setDetailTaskId(task.id);
    setEdits({});
    setDetailOpen(true);
  };

  const patchEdit = (itemId: string, patch: { result?: string; remark?: string; photo_urls?: string[] }) => {
    setEdits(prev => ({ ...prev, [itemId]: { ...prev[itemId], ...patch } }));
  };

  const handleSubmit = async () => {
    if (!detail) return;
    const items = detail.items.map(item => ({
      item_id: item.id,
      result: edits[item.id]?.result ?? item.result,
      remark: edits[item.id]?.remark ?? item.remark,
      photo_urls: edits[item.id]?.photo_urls ?? item.photo_urls,
    }));
    if (!items.some(x => x.result !== "pending")) {
      message.warning("请至少核对一项清单内容后再提交");
      return;
    }
    setSubmitting(true);
    try {
      await submitHazardTask(enterpriseId, detail.id, { items });
      message.success("核对结果已提交");
      refetchDetail();
      refetch();
    } catch (e) {
      message.error(extractDetail(e) || "提交失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const openToRecord = (item: HazardInspectionItem) => {
    const remark = edits[item.id]?.remark ?? item.remark;
    setToRecordItem(item);
    toRecordForm.setFieldsValue({
      title: (item.content || "").slice(0, 255) || "排查发现的隐患",
      description: [item.content, remark ? `备注：${remark}` : ""].filter(Boolean).join("；"),
    });
    setToRecordOpen(true);
  };

  const handleToRecord = async (values: { title: string; description: string }) => {
    if (!detail || !toRecordItem) return;
    setToRecordSubmitting(true);
    try {
      await taskToRecord(enterpriseId, detail.id, {
        item_id: toRecordItem.id,
        title: values.title.trim(),
        description: values.description.trim(),
      });
      message.success("已转为隐患登记，可在隐患台账中查看");
      setToRecordOpen(false);
      refetch();
      queryClient.invalidateQueries({ queryKey: ["hazard-records", enterpriseId] });
    } catch (e) {
      message.error(extractDetail(e) || "转隐患失败，请稍后重试");
    } finally {
      setToRecordSubmitting(false);
    }
  };

  const columns: TableColumnsType<HazardInspectionTask> = [
    {
      title: "任务",
      dataIndex: "title",
      ellipsis: true,
      render: (title: string | null, row) => (
        <a onClick={() => openDetail(row)}>{title || "未命名任务"}</a>
      ),
    },
    {
      title: "责任人",
      dataIndex: "responsible_user_id",
      width: 110,
      ellipsis: true,
      render: (v: string | null) => (v ? memberNameMap[v] || "—" : "—"),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: HazardTaskStatus, row) => {
        const overdue = isTaskOverdue(row, now);
        const status = overdue ? "overdue" : v;
        return <Tag color={TASK_STATUS_COLORS[status]}>{TASK_STATUS_LABELS[status]}</Tag>;
      },
    },
    {
      title: "到期时间",
      dataIndex: "due_at",
      width: 170,
      render: (v: string, row) => {
        const overdue = isTaskOverdue(row, now);
        return (
          <Space size={6}>
            <span style={overdue ? { color: "#cf1322", fontWeight: 500 } : undefined}>
              {formatDateTime(v)}
            </span>
            {overdue && <Tag color="red">已超期</Tag>}
          </Space>
        );
      },
    },
    {
      title: "完成时间",
      dataIndex: "completed_at",
      width: 170,
      render: (v: string | null) => formatDateTime(v),
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_v, row) => (
        <Button type="link" size="small" onClick={() => openDetail(row)}>
          {row.status === "done" ? "查看" : "执行"}
        </Button>
      ),
    },
  ];

  const itemColumns: TableColumnsType<HazardInspectionItem> = [
    {
      title: "核对内容",
      dataIndex: "content",
      ellipsis: true,
      render: (content: string, row) => (
        <div>
          <div>{content}</div>
          {row.expected_note && (
            <div style={{ color: "#999", fontSize: 12 }}>期望：{row.expected_note}</div>
          )}
        </div>
      ),
    },
    {
      title: "核对结果",
      dataIndex: "result",
      width: 120,
      render: (result: string, row) => (
        <Select
          size="small"
          style={{ width: 110 }}
          value={edits[row.id]?.result ?? result}
          options={ITEM_RESULT_OPTIONS}
          disabled={detail?.status === "done"}
          onChange={v => patchEdit(row.id, { result: v })}
        />
      ),
    },
    {
      title: "备注",
      dataIndex: "remark",
      width: 180,
      render: (remark: string | null, row) => (
        <Input
          size="small"
          placeholder="异常时填写说明"
          value={edits[row.id]?.remark ?? remark ?? ""}
          disabled={detail?.status === "done"}
          onChange={e => patchEdit(row.id, { remark: e.target.value })}
        />
      ),
    },
    {
      title: "照片",
      dataIndex: "photo_urls",
      width: 140,
      render: (photoUrls: string[] | null, row) => {
        const isAbnormal = (edits[row.id]?.result ?? row.result) === "abnormal";
        if (!isAbnormal) return <span style={{ color: "#999" }}>—</span>;
        return (
          <ItemPhotoUpload
            value={edits[row.id]?.photo_urls ?? photoUrls ?? []}
            disabled={detail?.status === "done"}
            onChange={urls => patchEdit(row.id, { photo_urls: urls })}
          />
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 90,
      render: (_v, row) => (
        <Tooltip title={row.result === "abnormal" ? "转为隐患登记" : "仅异常项可转隐患"}>
          <Button
            type="link"
            size="small"
            disabled={row.result !== "abnormal"}
            onClick={() => openToRecord(row)}
          >
            转隐患
          </Button>
        </Tooltip>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="排查任务"
        subtitle="按计划自动生成的排查任务，逐项核对后提交；异常项可一键转为隐患登记"
        onBack={() => navigate(-1)}
      />

      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="责任人"
          style={{ width: 160 }}
          value={filters.responsible_user_id}
          options={memberOptions}
          onChange={v => setFilters(f => ({ ...f, responsible_user_id: v }))}
        />
        <Select
          allowClear
          placeholder="状态"
          style={{ width: 120 }}
          value={filters.status}
          options={STATUS_OPTIONS}
          onChange={v => setFilters(f => ({ ...f, status: v }))}
        />
        <Select
          allowClear
          placeholder="超期"
          style={{ width: 120 }}
          value={filters.overdue ? "yes" : undefined}
          options={[{ value: "yes", label: "仅看超期" }]}
          onChange={v => setFilters(f => ({ ...f, overdue: v === "yes" ? true : undefined }))}
        />
        <Button onClick={() => setFilters({})}>重置</Button>
      </Space>

      <Table
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={tasks}
        loading={isLoading}
        locale={{ emptyText: "暂无排查任务" }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
      />

      <Modal
        title={detail?.status === "done" ? "任务详情" : "任务执行"}
        open={detailOpen}
        width={860}
        confirmLoading={submitting}
        okText="提交核对"
        okButtonProps={{ disabled: detail?.status === "done" }}
        onOk={() => void handleSubmit()}
        onCancel={() => setDetailOpen(false)}
        destroyOnClose
      >
        {detail && (
          <div>
            <Descriptions size="small" column={3} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="任务">{detail.title || "未命名任务"}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={TASK_STATUS_COLORS[detail.status]}>{TASK_STATUS_LABELS[detail.status]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="责任人">
                {detail.responsible_user_id ? memberNameMap[detail.responsible_user_id] || "—" : "—"}
              </Descriptions.Item>
              <Descriptions.Item label="到期时间">{formatDateTime(detail.due_at)}</Descriptions.Item>
              <Descriptions.Item label="完成时间">{formatDateTime(detail.completed_at)}</Descriptions.Item>
            </Descriptions>
            <Table
              rowKey="id"
              size="small"
              columns={itemColumns}
              dataSource={detail.items}
              loading={detailLoading}
              pagination={false}
              scroll={{ x: 760 }}
              locale={{ emptyText: "暂无清单项" }}
            />
          </div>
        )}
      </Modal>

      <Modal
        title="转隐患登记"
        open={toRecordOpen}
        confirmLoading={toRecordSubmitting}
        okText="确认登记"
        onOk={() => toRecordForm.submit()}
        onCancel={() => setToRecordOpen(false)}
        destroyOnClose
      >
        <Form form={toRecordForm} layout="vertical" onFinish={values => void handleToRecord(values)} style={{ marginTop: 12 }}>
          <Form.Item name="title" label="隐患标题" rules={[{ required: true, message: "请填写隐患标题" }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item name="description" label="隐患描述" rules={[{ required: true, message: "请填写隐患描述" }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          {toRecordItem?.photo_urls?.length ? (
            <Form.Item label="现场照片（将随登记一并带入）">
              <Image.PreviewGroup>
                <Space wrap>
                  {toRecordItem.photo_urls.map(url => (
                    <Image key={url} src={url} width={72} height={72} style={{ objectFit: "cover", borderRadius: 4 }} />
                  ))}
                </Space>
              </Image.PreviewGroup>
            </Form.Item>
          ) : null}
        </Form>
      </Modal>
    </div>
  );
}
