import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Form, Input, Button, Alert, Card } from "antd";
import { MailOutlined, LockOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";
import { validatePassword } from "@/utils/validators";

export default function RegisterPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register } = useAuth();
  const navigate = useNavigate();

  const onFinish = async (values: { name: string; email: string; password: string }) => {
    setLoading(true);
    setError(null);
    try {
      await register({
        name: values.name,
        email: values.email,
        password: values.password,
        password_confirm: values.password,
      });
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "注册失败，请稍后重试";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="注册" style={{ width: "100%" }}>
      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} closable onClose={() => setError(null)} />}
      <Form name="register" onFinish={onFinish} layout="vertical" size="large">
        <Form.Item name="name" rules={[{ required: true, message: "请输入姓名" }]}>
          <Input prefix={<UserOutlined />} placeholder="姓名" />
        </Form.Item>
        <Form.Item name="email" rules={[{ required: true, type: "email", message: "请输入有效的邮箱地址" }]}>
          <Input prefix={<MailOutlined />} placeholder="邮箱" />
        </Form.Item>
        <Form.Item
          name="password"
          rules={[
            { required: true, message: "请输入密码" },
            {
              validator: (_, value) => {
                if (!value) return Promise.resolve();
                const result = validatePassword(value);
                return result.valid ? Promise.resolve() : Promise.reject(result.message);
              },
            },
          ]}
          extra="至少 8 位，包含字母和数字"
        >
          <Input.Password prefix={<LockOutlined />} placeholder="密码" />
        </Form.Item>
        <Form.Item
          name="password_confirm"
          dependencies={["password"]}
          rules={[
            { required: true, message: "请确认密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("password") === value) return Promise.resolve();
                return Promise.reject(new Error("两次密码不一致"));
              },
            }),
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            注册
          </Button>
        </Form.Item>
      </Form>
      <div style={{ textAlign: "center" }}>
        已有账号？<Link to="/login">去登录</Link>
      </div>
    </Card>
  );
}
