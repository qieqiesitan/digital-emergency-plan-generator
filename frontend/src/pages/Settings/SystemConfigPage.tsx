import { useState } from "react";
import {
  Table, Modal, Form, Input, Select, Button, message, Space, Popconfirm,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchConfigs,
  setConfig,
  deleteConfig,
} from "@/services/configService";
import type { SystemConfig } from "@/services/configService";
import { PageHeader } from "@/components/common/PageHeader";

export default function SystemConfigPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<SystemConfig | null>(null);
  const [form] = Form.useForm();

  const { data: configs = [], isLoading } = useQuery({
    queryKey: ["systemConfigs"],
    queryFn: fetchConfigs,
  });

  const saveMut = useMutation({
    mutationFn: ({ key, value, type, description }: { key: string; value: string; type?: string; description?: string }) =>
      setConfig(key, value, type, description),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["systemConfigs"] });
      setModalOpen(false);
    },
    onError: () => message.error("保存失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (key: string) => deleteConfig(key),
    onSuccess: () => {
      message.success("删除成功");
      queryClient.invalidateQueries({ queryKey: ["systemConfigs"] });
    },
    onError: () => message.error("删除失败"),
  });

  const handleAdd = () => {
    setEditingConfig(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: SystemConfig) => {
    setEditingConfig(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    saveMut.mutate({
      key: values.config_key,
      value: values.config_value,
      type: values.config_type,
      description: values.description,
    });
  };

  const columns = [
    { title: "配置键", dataIndex: "config_key", key: "config_key", width: 240 },
    {
      title: "配置值", dataIndex: "config_value", key: "config_value", width: 320,
      ellipsis: true,
    },
    { title: "类型", dataIndex: "config_type", key: "config_type", width: 100 },
    {
      title: "描述", dataIndex: "description", key: "description",
      ellipsis: true,
    },
    {
      title: "操作", key: "actions", width: 160,
      render: (_: unknown, record: SystemConfig) => (
        <Space>
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm
            title="确定删除此配置项？"
            onConfirm={() => deleteMut.mutate(record.config_key)}
          >
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="系统配置" extra={<Button type="primary" onClick={handleAdd}>新增配置</Button>} />

      <Table
        columns={columns}
        dataSource={configs}
        rowKey="config_key"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={editingConfig ? "编辑配置" : "新增配置"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saveMut.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="config_key"
            label="配置键"
            rules={[{ required: true, message: "请输入配置键" }]}
          >
            <Input disabled={!!editingConfig} placeholder="例如: app.max_upload_size" />
          </Form.Item>
          <Form.Item
            name="config_value"
            label="配置值"
            rules={[{ required: true, message: "请输入配置值" }]}
          >
            <Input.TextArea rows={3} placeholder="配置值" />
          </Form.Item>
          <Form.Item name="config_type" label="类型">
            <Select
              placeholder="选择类型"
              options={[
                { value: "string", label: "字符串" },
                { value: "number", label: "数字" },
                { value: "boolean", label: "布尔" },
                { value: "json", label: "JSON" },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="配置项说明" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
