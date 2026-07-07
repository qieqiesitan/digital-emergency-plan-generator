import { useState } from "react";
import {
  Table, Modal, Form, Input, Select, Button, message, Space, Popconfirm,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchUsers,
  createUser,
  updateUser,
  deleteUser,
} from "@/services/userManageService";
import { fetchRoles } from "@/services/roleService";
import type { AdminUserItem } from "@/types/role";
import { useAuth } from "@/contexts/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";

export default function UserManagePage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUserItem | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [form] = Form.useForm();

  const { data: listData, isLoading } = useQuery({
    queryKey: ["adminUsers", { page, pageSize, search }],
    queryFn: () => fetchUsers({ page, page_size: pageSize, search: search || undefined }),
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["rolesForSelect"],
    queryFn: fetchRoles,
  });

  const saveMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      if (editingUser) {
        return updateUser(editingUser.id, {
          name: values.name as string,
          role: values.role as string,
        });
      }
      return createUser({
        email: values.email as string,
        name: values.name as string,
        password: values.password as string,
        role: values.role as string,
      });
    },
    onSuccess: () => {
      message.success(editingUser ? "更新成功" : "创建成功");
      queryClient.invalidateQueries({ queryKey: ["adminUsers"] });
      setModalOpen(false);
    },
    onError: () => message.error(editingUser ? "更新失败" : "创建失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (userId: string) => deleteUser(userId),
    onSuccess: () => {
      message.success("删除成功");
      queryClient.invalidateQueries({ queryKey: ["adminUsers"] });
    },
    onError: () => message.error("删除失败"),
  });

  const handleAdd = () => {
    setEditingUser(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: AdminUserItem) => {
    setEditingUser(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    saveMut.mutate(values);
  };

  const columns = [
    { title: "邮箱", dataIndex: "email", key: "email", width: 220 },
    { title: "姓名", dataIndex: "name", key: "name", width: 140 },
    {
      title: "角色", dataIndex: "role", key: "role", width: 120,
      render: (role: string) => {
        const roleName = roles.find(r => r.code === role)?.name || role;
        return <span>{roleName}</span>;
      },
    },
    {
      title: "创建时间", dataIndex: "created_at", key: "created_at", width: 180,
      render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "-",
    },
    {
      title: "操作", key: "actions", width: 160,
      render: (_: unknown, record: AdminUserItem) => (
        <Space>
          <Button type="link" onClick={() => handleEdit(record)}>编辑</Button>
          {record.id !== currentUser?.id && (
            <Popconfirm
              title="确定删除此用户？"
              onConfirm={() => deleteMut.mutate(record.id)}
            >
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
        title="用户管理"
        extra={<Button type="primary" onClick={handleAdd}>新增用户</Button>}
      />

      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索邮箱或姓名"
          allowClear
          onSearch={(v) => { setSearch(v); setPage(1); }}
          style={{ width: 280 }}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={listData?.items ?? []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: listData?.total ?? 0,
          showSizeChanger: true,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
      />

      <Modal
        title={editingUser ? "编辑用户" : "新增用户"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saveMut.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          {!editingUser && (
            <>
              <Form.Item
                name="email"
                label="邮箱"
                rules={[
                  { required: true, message: "请输入邮箱" },
                  { type: "email", message: "请输入有效邮箱" },
                ]}
              >
                <Input placeholder="user@example.com" />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: "请输入密码" }, { min: 6, message: "密码至少6位" }]}
              >
                <Input.Password placeholder="至少6位" />
              </Form.Item>
            </>
          )}
          <Form.Item
            name="name"
            label="姓名"
            rules={[{ required: true, message: "请输入姓名" }]}
          >
            <Input placeholder="姓名" />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: "请选择角色" }]}
          >
            <Select
              placeholder="选择角色"
              options={roles.map(r => ({ value: r.code, label: r.name }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
