import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
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
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSystemDict,
  listSystemDicts,
  updateSystemDict,
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
  editing: DataDictItem | null;
}

/** 系统数据字典管理页（管理员）：按 dict_type 分组维护系统级字典条目。 */
export default function DataDictManagePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [activeType, setActiveType] = useState<string>("全部");
  const [drawer, setDrawer] = useState<DrawerState>({ open: false, editing: null });
  const [form] = Form.useForm();

  const { data = [], isLoading, isError } = useQuery({
    queryKey: ["system-data-dicts", activeType],
    queryFn: () =>
      listSystemDicts(activeType === "全部" ? undefined : activeType),
  });

  const dictTypes = useMemo(
    () =>
      Array.from(new Set(data.map(d => d.dict_type))).sort((a, b) =>
        a.localeCompare(b, "zh"),
      ),
    [data],
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["system-data-dicts"] });
  };

  const createMut = useMutation({
    mutationFn: (payload: DataDictPayload) => createSystemDict(payload),
    onSuccess: () => {
      message.success("创建成功");
      invalidate();
      setDrawer({ open: false, editing: null });
    },
    onError: (e: unknown) => message.error(`创建失败：${errMsg(e)}`),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<DataDictPayload> }) =>
      updateSystemDict(id, patch),
    onSuccess: () => {
      message.success("保存成功");
      invalidate();
      setDrawer({ open: false, editing: null });
    },
    onError: (e: unknown) => message.error(`保存失败：${errMsg(e)}`),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({
      dict_type: activeType === "全部" ? undefined : activeType,
      enabled: true,
      sort_order: 0,
      value_json: "{}",
    });
    setDrawer({ open: true, editing: null });
  };

  const openEdit = (record: DataDictItem) => {
    form.resetFields();
    form.setFieldsValue({
      ...record,
      value_json: formatValue(record.value),
    });
    setDrawer({ open: true, editing: record });
  };

  const handleSubmit = async () => {
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
    if (drawer.editing) {
      // 编辑只提交可更新字段，避免把 dict_type/code 一起发回
      const patch: Partial<DataDictPayload> = {
        label: payload.label,
        value: payload.value,
        sort_order: payload.sort_order,
        enabled: payload.enabled,
        description: payload.description,
      };
      updateMut.mutate({ id: drawer.editing.id, patch });
    } else {
      createMut.mutate(payload);
    }
  };

  const columns: TableColumnsType<DataDictItem> = [
    { title: "编码", dataIndex: "code", width: 140 },
    { title: "名称", dataIndex: "label", width: 160 },
    {
      title: "值",
      dataIndex: "value",
      render: (value: Record<string, unknown>) => (
        <Text code style={{ fontSize: 12 }}>{formatValue(value)}</Text>
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
      width: 150,
      render: (_: unknown, record) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Tooltip title="系统条目不支持删除，可通过禁用停用">
            <Button
              type="link"
              size="small"
              danger
              disabled
              icon={<DeleteOutlined />}
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
        title="数据字典管理"
        subtitle="维护系统级字典（评估因子、管控层级映射、危害类型等），企业可在此基础上覆盖"
        onBack={() => navigate(-1)}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增条目
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
            dataSource={data}
            columns={columns}
            scroll={{ x: 820 }}
            pagination={{ pageSize: 20, showTotal: total => `共 ${total} 条` }}
            locale={{
              emptyText: isError
                ? "加载失败，请稍后重试"
                : <Empty description="暂无字典条目" />,
            }}
          />
        </div>
      </div>

      <Drawer
        title={drawer.editing ? "编辑字典条目" : "新增字典条目"}
        width={480}
        open={drawer.open}
        onClose={() => setDrawer({ open: false, editing: null })}
        extra={
          <Space>
            <Button onClick={() => setDrawer({ open: false, editing: null })}>
              取消
            </Button>
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
            <Input
              placeholder="如 measure_factors / control_level_map / hazard_type"
              disabled={!!drawer.editing}
            />
          </Form.Item>
          <Form.Item
            name="code"
            label="编码"
            rules={[{ required: true, message: "请输入编码" }]}
          >
            <Input placeholder="同类型下唯一，如 fire" disabled={!!drawer.editing} />
          </Form.Item>
          <Form.Item
            name="label"
            label="名称"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input placeholder="如 火灾" />
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
