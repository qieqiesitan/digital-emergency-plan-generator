import { useState, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { User, Mail, Lock } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import NavBar from "@/mobile/components/ui/NavBar";
import Input from "@/mobile/components/ui/Input";
import Button from "@/mobile/components/ui/Button";
import Chip from "@/mobile/components/ui/Chip";
import SafeArea from "@/mobile/components/ui/SafeArea";
import { useToast } from "@/mobile/components/ui/Toast";

export default function RegisterScreen() {
  const navigate = useNavigate();
  const { register, login } = useAuth();
  const { showToast } = useToast();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const checks = {
    minLength: password.length >= 8,
    hasLetterAndNumber: /[a-zA-Z]/.test(password) && /\d/.test(password),
    passwordsMatch:
      passwordConfirm.length > 0 && password === passwordConfirm,
  };

  const allValid = checks.minLength && checks.hasLetterAndNumber && checks.passwordsMatch && name.trim() !== "" && email.trim() !== "";

  const handleRegister = async () => {
    if (!allValid) return;
    setIsSubmitting(true);
    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
        password_confirm: passwordConfirm,
      });
      navigate("/m/dashboard", { replace: true });
    } catch (err: any) {
      const msg =
        err?.response?.data?.message || err?.message || "注册失败，请重试";
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
          <h1 className="text-display text-neutral-900 mb-sm">创建账号</h1>
          <p className="text-body text-neutral-600 mb-xl">开始管理您的应急预案</p>

          <div className="flex flex-col gap-md">
            <Input
              placeholder="请输入姓名"
              value={name}
              onChange={(e) => setName(e.target.value)}
              prefixIcon={<User size={20} />}
              fullWidth
            />

            <Input
              type="email"
              placeholder="请输入邮箱"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              prefixIcon={<Mail size={20} />}
              fullWidth
              autoComplete="email"
            />

            <Input
              type="password"
              placeholder="请输入密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              prefixIcon={<Lock size={20} />}
              showPasswordToggle
              fullWidth
              autoComplete="new-password"
            />

            {/* 密码校验指示器 */}
            <div className="flex flex-wrap gap-sm -mt-sm">
              <Chip
                variant={checks.minLength ? "selected" : "default"}
                label="≥8位"
              />
              <Chip
                variant={checks.hasLetterAndNumber ? "selected" : "default"}
                label="含字母和数字"
              />
              <Chip
                variant={checks.passwordsMatch ? "selected" : "default"}
                label="两次密码一致"
              />
            </div>

            <Input
              type="password"
              placeholder="请确认密码"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              prefixIcon={<Lock size={20} />}
              showPasswordToggle
              fullWidth
              autoComplete="new-password"
            />
          </div>

          <div className="mt-lg">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              loading={isSubmitting}
              disabled={!allValid}
              onClick={handleRegister}
            >
              注册
            </Button>
          </div>

          <div className="mt-lg text-center">
            <span className="text-body-sm">
              <span className="text-neutral-600">已有账号？</span>
              <Link to="/m/login" className="text-primary-500 font-medium">
                去登录
              </Link>
            </span>
          </div>
        </div>
      </div>
    </SafeArea>
  );
}
