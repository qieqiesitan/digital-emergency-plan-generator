import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  RollbackOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createEnterpriseDict,
  deleteEnterpriseDict,
  listEnterpriseDicts,
  updateEnterpriseDict,
} from "@/services/dataDictService";
import type { DataDictItem, DataDictPayload } from "@/types/dataDict";
import { PageHeader } from "@/components/common/PageHeader";

const { TextArea } = Input;
const { Text } = Typography;

function formatValue(value: Record<string, unknown> | null | undefined): string {
  try {
    return JSON.stringify(value ?? {});
  } catch {
    return "{}";
  }
}

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return "未知错误";
}

interface DrawerState {
  open: boolean;
  mode: "create" | "edit";
  source: DataDictItem;
}

/** 企业风险与隐患配置页：系统+企业合并视图，企业条目可覆盖系统默认。 */
export default function EnterpriseDictConfigPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message, modal } = AntApp.useApp();
  const [activeType, setActiveType] = useState<string>("全部");
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [form] = Form.useForm();

  const { data = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["enterprise-data-dicts", enterpriseId],
    queryFn: () => listEnterpriseDicts(enterpriseId),
    enabled: !!enterpriseId,
  });

  const rows = useMemo(
    () =>
      activeType === "全部"
        ? data
        : data.filter(d => d.dict_type === activeType),
    [data, activeType],
  );

  const dictTypes = useMemo(
    () =>
      Array.from(new Set(data.map(d => d.dict_type))).sort((a, b) =>
        a.localeCompare(b, "zh"),
      ),
    [data],
  );

  const refetchAll = () => {
    refetch();
    queryClient.invalidateQueries({ queryKey: ["enterprise-data-dicts"] });
  };

  const createMut = useMutation({
    mutationFn: (payload: DataDictPayload) =>
      createEnterpriseDict(enterpriseId, payload),
    onSuccess: () => {
      message.success("已创建企业覆盖，可继续编辑");
      refetchAll();
      setDrawer(null);
    },
    onError: (e: unknown) => message.error(`覆盖失败：${errMsg(e)}`),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<DataDictPayload> }) =>
      updateEnterpriseDict(enterpriseId, id, patch),
    onSuccess: () => {
      message.success("保存成功");
      refetchAll();
      setDrawer(null);
    },
    onError: (e: unknown) => message.error(`保存失败：${errMsg(e)}`),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteEnterpriseDict(enterpriseId, id),
    onSuccess: () => {
      message.success("已删除企业条目，恢复系统默认");
      refetchAll();
    },
    onError: (e: unknown) => message.error(`删除失败：${errMsg(e)}`),
  });

  const openOverride = (record: DataDictItem) => {
    form.resetFields();
    form.setFieldsValue({
      ...record,
      value_json: formatValue(record.value),
    });
    setDrawer({ open: true, mode: "create", source: record });
  };

  const openEdit = (record: DataDictItem) => {
    form.resetFields();
    form.setFieldsValue({
      ...record,
      value_json: formatValue(record.value),
    });
    setDrawer({ open: true, mode: "edit", source: record });
  };

  const confirmDelete = (record: DataDictItem) => {
    modal.confirm({
      title: `确认删除企业覆盖「${record.label}」？`,
      content: "删除后该条目恢复为系统默认配置。",
      okText: "删除",
      okButtonProps: { danger: true },
      onOk: () => deleteMut.mutateAsync(record.id),
    });
  };

  const handleSubmit = async () => {
    if (!drawer) return;
    const values = await form.validateFields();
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(values.value_json || "{}") as Record<string, unknown>;
    } catch {
      message.error("value 不是合法 JSON，请检查格式（提交将返回 422）");
      return;
    }
    const payload: DataDictPayload = {
      dict_type: String(values.dict_type ?? "").trim(),
      code: String(values.code ?? "").trim(),
      label: String(values.label ?? "").trim(),
      value: parsed,
      sort_order: values.sort_order ?? 0,
      enabled: values.enabled ?? true,
      description: values.description || null,
    };
    if (drawer.mode === "create") {
      createMut.mutate(payload);
    } else {
      updateMut.mutate({ id: drawer.source.id, patch: payload });
    }
  };

  const columns: TableColumnsType<DataDictItem> = [
    { title: "编码", dataIndex: "code", width: 130 },
    { title: "名称", dataIndex: "label", width: 150 },
    {
      title: "值",
      dataIndex: "value",
      render: (value: Record<string, unknown>) => (
        <Text code style={{ fontSize: 12 }}>{formatValue(value)}</Text>
      ),
    },
    {
      title: "来源",
      dataIndex: "scope",
      width: 100,
      render: (scope: string) =>
        scope === "system" ? (
          <Tag color="blue">系统默认</Tag>
        ) : (
          <Tag color="orange">企业覆盖</Tag>
        ),
    },
    {
      title: "启用",
      dataIndex: "enabled",
      width: 70,
      render: (enabled: boolean) =>
        enabled ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    { title: "排序", dataIndex: "sort_order", width: 70 },
    {
      title: "说明",
      dataIndex: "description",
      ellipsis: true,
      render: (desc?: string | null) => desc || "—",
    },
    {
      title: "操作",
      key: "actions",
      width: 190,
      render: (_: unknown, record) =>
        record.scope === "system" ? (
          <Tooltip title="复制系统条目为企业条目，之后可编辑">
            <Button
              type="link"
              size="small"
              onClick={() => openOverride(record)}
            >
              覆盖
            </Button>
          </Tooltip>
        ) : (
          <Space size={0}>
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            >
              编辑
            </Button>
            <Tooltip title="删除企业覆盖，恢复系统默认">
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => confirmDelete(record)}
              >
                删除
              </Button>
            </Tooltip>
          </Space>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="风险与隐患配置"
        subtitle="查看系统默认字典并配置本企业覆盖（评估因子、管控层级映射、危害类型等）"
        onBack={() => navigate(-1)}
        extra={
          <Button icon={<RollbackOutlined />} onClick={() => void refetch()}>
            刷新
          </Button>
        }
      />

      <div style={{ display: "flex", gap: 16 }}>
        <div
          style={{
            width: 180,
            flexShrink: 0,
            background: "#fff",
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            padding: 8,
            maxHeight: 520,
            overflow: "auto",
          }}
        >
          <Button
            block
            type={activeType === "全部" ? "primary" : "text"}
            style={{ marginBottom: 4, textAlign: "left" }}
            onClick={() => setActiveType("全部")}
          >
            全部类型
          </Button>
          {dictTypes.map(type => (
            <Button
              key={type}
              block
              type={activeType === type ? "primary" : "text"}
              style={{ marginBottom: 4, textAlign: "left", overflow: "hidden" }}
              onClick={() => setActiveType(type)}
            >
              {type}
            </Button>
          ))}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <Table<DataDictItem>
            rowKey="id"
            loading={isLoading}
            dataSource={rows}
            columns={columns}
            scroll={{ x: 860 }}
            pagination={{ pageSize: 20, showTotal: total => `共 ${total} 条` }}
            locale={{
              emptyText: isError
                ? "加载失败，请稍后重试"
                : <Empty description="暂无字典数据" />,
            }}
          />
        </div>
      </div>

      <Drawer
        title={drawer?.mode === "create" ? "覆盖系统默认" : "编辑企业条目"}
        width={480}
        open={!!drawer}
        onClose={() => setDrawer(null)}
        extra={
          <Space>
            <Button onClick={() => setDrawer(null)}>取消</Button>
            <Button
              type="primary"
              loading={createMut.isPending || updateMut.isPending}
              onClick={() => void handleSubmit()}
            >
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="dict_type"
            label="字典类型"
            rules={[{ required: true, message: "请输入字典类型" }]}
          >
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="code"
            label="编码"
            rules={[{ required: true, message: "请输入编码" }]}
          >
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="label"
            label="名称"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="value_json"
            label="值（JSON）"
            rules={[{ required: true, message: "请输入 JSON 值" }]}
            extra="提交前会做 JSON 校验，非法格式提示 422"
          >
            <TextArea
              rows={5}
              placeholder={'{"weight": 3}'}
              style={{ fontFamily: "monospace" }}
            />
          </Form.Item>
          <Form.Item name="sort_order" label="排序">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
