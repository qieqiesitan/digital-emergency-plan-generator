import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Form, Input, Button, Alert, Card } from "antd";
import { MailOutlined, LockOutlined, UserOutlined } from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";
import { validatePassword } from "@/utils/validators";
import { resolveRedirectTarget } from "@/routing/loginRedirect";

export default function RegisterPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTarget = resolveRedirectTarget(searchParams.get("redirect"));

  // 注册成功即自动登录 → 回到来源页；来源页刷新也不丢失（redirect 在 URL 上）
  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirectTarget || "/dashboard", { replace: true });
    }
  }, [isAuthenticated, redirectTarget, navigate]);

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
    } catch (err: unknown) {
      // 优先取后端返回的友好 detail（如「该邮箱已被注册」），否则回退到通用文案
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      const msg = detail || (err instanceof Error && err.message ? err.message : "注册失败，请稍后重试");
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="注册" style={{ width: "100%" }}>
      {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} closable onClose={() => setError(null)} />}
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
