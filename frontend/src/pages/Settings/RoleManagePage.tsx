import { useState } from "react";
import {
  Table, Modal, Form, Input, Select, Button, message, Space, Popconfirm, Checkbox, Row, Col, Divider,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRoles,
  fetchPermissions,
  createRole,
  updateRole,
  deleteRole,
} from "@/services/roleService";
import type { Role, Permission } from "@/types/role";
import { PageHeader } from "@/components/common/PageHeader";

export default function RoleManagePage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [form] = Form.useForm();

  const { data: roles = [], isLoading } = useQuery({
    queryKey: ["roles"],
    queryFn: fetchRoles,
  });

  const { data: permissions = [] } = useQuery({
    queryKey: ["permissions"],
    queryFn: fetchPermissions,
  });

  const menuPermissions = permissions.filter((p: Permission) => p.category === "menu");
  const actionPermissions = permissions.filter((p: Permission) => p.category === "action");

  const groupedActions: Record<string, Permission[]> = {};
  for (const p of actionPermissions) {
    if (!groupedActions[p.resource]) groupedActions[p.resource] = [];
    groupedActions[p.resource].push(p);
  }

  const saveMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      const permIds = (values.permission_ids as string[]) || [];
      if (editingRole) {
        return updateRole(editingRole.id, {
          name: values.name as string,
          description: values.description as string,
          permission_ids: permIds,
        });
      }
      return createRole({
        name: values.name as string,
        code: values.code as string,
        description: values.description as string,
        permission_ids: permIds,
      });
    },
    onSuccess: () => {
      message.success(editingRole ? "更新成功" : "创建成功");
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setModalOpen(false);
    },
    onError: () => message.error(editingRole ? "更新失败" : "创建失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (roleId: string) => deleteRole(roleId),
    onSuccess: () => {
      message.success("删除成功");
      queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
    onError: () => message.error("删除失败"),
  });

  const handleAdd = () => {
    setEditingRole(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: Role) => {
    setEditingRole(record);
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      permission_ids: record.permissions?.map(p => p.id) ?? [],
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    saveMut.mutate(values);
  };

  const columns = [
    { title: "角色名称", dataIndex: "name", key: "name", width: 160 },
    { title: "标识码", dataIndex: "code", key: "code", width: 140 },
    { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
    { title: "系统内置", dataIndex: "is_system", key: "is_system", width: 100,
      render: (v: boolean) => v ? "是" : "否",
    },
    {
      title: "操作", key: "actions", width: 160,
      render: (_: unknown, record: Role) => (
        <Space>
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          {!record.is_system && (
            <Popconfirm title="确定删除此角色？" onConfirm={() => deleteMut.mutate(record.id)}>
              <Button type="link" danger>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="角色管理"
        extra={<Button type="primary" onClick={handleAdd}>新增角色</Button>}
      />

      <Table
        columns={columns}
        dataSource={roles}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={editingRole ? "编辑角色" : "新增角色"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saveMut.isPending}
        destroyOnClose
        width={680}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="角色名称" rules={[{ required: true, message: "请输入角色名称" }]}>
            <Input placeholder="例如: 编辑员" />
          </Form.Item>
          {!editingRole && (
            <Form.Item name="code" label="标识码" rules={[{ required: true, message: "请输入标识码" }]}>
              <Input placeholder="例如: editor" />
            </Form.Item>
          )}
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="角色说明" />
          </Form.Item>

          <Form.Item name="permission_ids" label="权限配置">
            <Checkbox.Group style={{ width: "100%" }}>
              <Divider orientation="left" plain style={{ fontSize: 13, margin: "4px 0" }}>菜单权限</Divider>
              <Row gutter={[16, 8]} style={{ marginBottom: 12 }}>
                {menuPermissions.map(p => (
                  <Col span={8} key={p.id}>
                    <Checkbox value={p.id}>{p.name}</Checkbox>
                  </Col>
                ))}
              </Row>
              <Divider orientation="left" plain style={{ fontSize: 13, margin: "4px 0" }}>操作权限</Divider>
              {Object.entries(groupedActions).map(([resource, perms]) => (
                <div key={resource} style={{ marginBottom: 10 }}>
                  <div style={{ fontWeight: 600, marginBottom: 3, fontSize: 12, color: "#999" }}>{resource}</div>
                  <Row gutter={[16, 6]}>
                    {perms.map(p => (
                      <Col span={12} key={p.id}>
                        <Checkbox value={p.id}>{p.name}</Checkbox>
                      </Col>
                    ))}
                  </Row>
                </div>
              ))}
            </Checkbox.Group>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
