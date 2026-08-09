// @ts-nocheck
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Mail, Lock } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import NavBar from "@/mobile/components/ui/NavBar";
import Input from "@/mobile/components/ui/Input";
import Button from "@/mobile/components/ui/Button";
import SafeArea from "@/mobile/components/ui/SafeArea";
import { useToast } from "@/mobile/components/ui/Toast";

export default function LoginScreen() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { showToast } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = email.trim() !== "" && password.length >= 8;

  const handleLogin = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    try {
      await login({ email, password });
      navigate("/m/dashboard", { replace: true });
    } catch (err: any) {
      const msg =
        err?.response?.data?.message || err?.message || "登录失败，请重试";
      showToast({ type: "error", message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SafeArea>
      <div className="flex flex-col min-h-dvh bg-white">
        <NavBar title="" border={false} />

        <div className="flex-1 flex flex-col px-md pt-lg">
          <h1 className="text-display text-neutral-900 mb-sm">登录</h1>
          <p className="text-body text-neutral-600 mb-xl">欢迎回到应急预案管理</p>

          <div className="flex flex-col gap-md">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱"
              prefixIcon={<Mail size={20} />}
              fullWidth
              autoComplete="email"
            />

            <Input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              prefixIcon={<Lock size={20} />}
              showPasswordToggle
              fullWidth
              autoComplete="current-password"
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
          </div>

          <div className="flex justify-end mt-sm">
            <span className="text-body-sm text-neutral-500">
              忘记密码？请联系管理员重置
            </span>
          </div>

          <div className="mt-lg">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              loading={isSubmitting}
              disabled={!canSubmit}
              onClick={handleLogin}
            >
              登录
            </Button>
          </div>

          <div className="mt-lg text-center">
            <span className="text-body-sm">
              <span className="text-neutral-600">没有账号？</span>
              <Link to="/m/register" className="text-primary-500 font-medium">
                立即注册
              </Link>
            </span>
          </div>
        </div>
      </div>
    </SafeArea>
  );
}
