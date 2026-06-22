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
    try { await updateProfile(values.name); message.success("done"); setEditingName(false); }
    catch { message.error("failed"); }
    finally { setSavingName(false); }
  };

  const handleChangePwd = async (values: { old_password: string; new_password: string }) => {
    setSavingPwd(true);
    try { await changePassword(values.old_password, values.new_password); message.success("password changed, please login again"); }
    catch { message.error("failed"); }
    finally { setSavingPwd(false); }
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <Card title="profile" style={{ marginBottom: 24 }}>
        <Avatar size={64} icon={<UserOutlined />} style={{ backgroundColor: "#1677ff", marginBottom: 16 }}>
          {user?.name?.charAt(0)}
        </Avatar>
        <Descriptions column={1}>
          <Descriptions.Item label="name">
            {editingName ? (
              <Form initialValues={{ name: user?.name }} onFinish={handleSaveName} layout="inline">
                <Form.Item name="name" rules={[{ required: true }]} style={{ marginBottom: 0 }}>
                  <Input />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={savingName} size="small">save</Button>
                <Button onClick={() => setEditingName(false)} size="small" style={{ marginLeft: 8 }}>cancel</Button>
              </Form>
            ) : (
              <span>{user?.name} <Button type="link" size="small" onClick={() => setEditingName(true)}>edit</Button></span>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="email">{user?.email}</Descriptions.Item>
          <Descriptions.Item label="registered">{user ? formatDate(user.created_at) : "-"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="change password">
        <Form layout="vertical" onFinish={handleChangePwd} style={{ maxWidth: 400 }}>
          <Form.Item name="old_password" label="current password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="new_password" label="new password" rules={[{ required: true, min: 8 }]} extra="at least 8 chars, include letters and numbers">
            <Input.Password />
          </Form.Item>
          <Form.Item name="confirm_password" label="confirm" dependencies={["new_password"]}
            rules={[{ required: true }, ({ getFieldValue }) => ({
              validator(_, value) { return !value || getFieldValue("new_password") === value ? Promise.resolve() : Promise.reject("passwords mismatch"); },
            })]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={savingPwd}>change password</Button>
        </Form>
      </Card>
    </div>
  );
}
