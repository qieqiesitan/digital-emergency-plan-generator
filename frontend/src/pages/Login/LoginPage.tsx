import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Form, Input, Button, Alert, Card, Checkbox, message } from "antd";
import { MailOutlined, LockOutlined } from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; password: string; remember: boolean }) => {
    setLoading(true);
    setError(null);
    try {
      await login({ email: values.email, password: values.password });
      if (values.remember) {
        localStorage.setItem("rememberedEmail", values.email);
      } else {
        localStorage.removeItem("rememberedEmail");
      }
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      // 优先取后端返回的友好 detail（如「邮箱或密码错误」），否则回退到通用文案
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      const msg = detail || (err instanceof Error && err.message ? err.message : "登录失败，请检查邮箱和密码");
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="登录" style={{ width: "100%" }}>
      {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} closable onClose={() => setError(null)} />}
      <Form
        name="login"
        onFinish={onFinish}
        layout="vertical"
        size="large"
        initialValues={{ email: localStorage.getItem("rememberedEmail") || "", remember: true }}
      >
        <Form.Item name="email" rules={[{ required: true, type: "email", message: "请输入有效的邮箱地址" }]}>
          <Input prefix={<MailOutlined />} placeholder="邮箱" />
        </Form.Item>
        <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="密码" />
        </Form.Item>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 24,
          }}
        >
          <Form.Item name="remember" valuePropName="checked" noStyle>
            <Checkbox>记住邮箱</Checkbox>
          </Form.Item>
          <Button
            type="link"
            style={{ padding: 0, height: "auto" }}
            onClick={() => message.info("忘记密码？请联系管理员重置")}
          >
            忘记密码？
          </Button>
        </div>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form.Item>
      </Form>
      <div style={{ textAlign: "center" }}>
        没有账号？<Link to="/register">立即注册</Link>
      </div>
    </Card>
  );
}
