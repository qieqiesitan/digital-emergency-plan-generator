import { useState } from "react";
import { Card, Descriptions, Button, Input, Form, Avatar, message } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";
import { formatDate } from "@/utils/formatters";

export default function ProfilePage() {
  const { user, updateProfile, changePassword } = useAuth();
  const [editingName, setEditingName] = useState(false);
  const [savingName, setSavingName] = useState(false);
  const [savingPwd, setSavingPwd] = useState(false);

  const handleSaveName = async (values: { name: string }) => {
    setSavingName(true);
    try { await updateProfile(values.name); message.success("已保存"); setEditingName(false); }
    catch { message.error("操作失败"); }
    finally { setSavingName(false); }
  };

  const handleChangePwd = async (values: { old_password: string; new_password: string }) => {
    setSavingPwd(true);
    try { await changePassword(values.old_password, values.new_password); message.success("密码已修改，请重新登录"); }
    catch { message.error("操作失败"); }
    finally { setSavingPwd(false); }
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <Card title="个人资料" style={{ marginBottom: 24 }}>
        <Avatar size={64} icon={<UserOutlined />} style={{ backgroundColor: "#1677ff", marginBottom: 16 }}>
          {user?.name?.charAt(0)}
        </Avatar>
        <Descriptions column={1}>
          <Descriptions.Item label="姓名">
            {editingName ? (
              <Form initialValues={{ name: user?.name }} onFinish={handleSaveName} layout="inline">
                <Form.Item name="name" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                  <Input />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={savingName} size="small">保存</Button>
                <Button onClick={() => setEditingName(false)} size="small" style={{ marginLeft: 8 }}>取消</Button>
              </Form>
            ) : (
              <span>{user?.name} <Button type="link" size="small" onClick={() => setEditingName(true)}>编辑</Button></span>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="邮箱">{user?.email}</Descriptions.Item>
          <Descriptions.Item label="注册时间">{user ? formatDate(user.created_at) : "-"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="修改密码">
        <Form layout="vertical" onFinish={handleChangePwd} style={{ maxWidth: 400 }}>
          <Form.Item name="old_password" label="当前密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[{ required: true, min: 8 }]} extra="至少 8 个字符，包含字母和数字">
            <Input.Password />
          </Form.Item>
          <Form.Item name="confirm_password" label="确认新密码" dependencies={["new_password"]}
            rules={[{ required: true }, ({ getFieldValue }) => ({
              validator(_, value) { return !value || getFieldValue("new_password") === value ? Promise.resolve() : Promise.reject("两次输入的密码不一致"); },
            })]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={savingPwd}>修改密码</Button>
        </Form>
      </Card>
    </div>
  );
}
