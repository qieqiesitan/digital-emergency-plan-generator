import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import NavBar from "@/mobile/components/ui/NavBar";
import Input from "@/mobile/components/ui/Input";
import Button from "@/mobile/components/ui/Button";
import Chip from "@/mobile/components/ui/Chip";
import SafeArea from "@/mobile/components/ui/SafeArea";
import { useToast } from "@/mobile/components/ui/Toast";
import { Lock } from "lucide-react";

export default function ChangePasswordScreen() {
  const navigate = useNavigate();
  const { changePassword } = useAuth();
  const { showToast } = useToast();

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const checks = {
    minLength: newPassword.length >= 8,
    hasLetterAndNumber:
      /[a-zA-Z]/.test(newPassword) && /\d/.test(newPassword),
    passwordsMatch:
      confirmPassword.length > 0 && newPassword === confirmPassword,
  };

  const canSubmit =
    oldPassword.length > 0 &&
    checks.minLength &&
    checks.hasLetterAndNumber &&
    checks.passwordsMatch;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    try {
      await changePassword(oldPassword, newPassword);
      showToast({ type: "success", message: "密码已修改，请重新登录" });
      navigate("/m/login", { replace: true });
    } catch (err: any) {
      showToast({
        type: "error",
        message: err?.response?.data?.message || "修改密码失败",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SafeArea edge="top">
      <div className="flex flex-col min-h-dvh bg-neutral-50">
        <NavBar title="修改密码" showBack onBack={() => navigate(-1)} />

        <div className="px-md pt-lg flex flex-col gap-md">
          <Input
            type="password"
            placeholder="请输入原密码"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            prefixIcon={<Lock size={20} />}
            showPasswordToggle
            fullWidth
          />

          <Input
            type="password"
            placeholder="请输入新密码"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            prefixIcon={<Lock size={20} />}
            showPasswordToggle
            fullWidth
          />

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
            placeholder="请确认新密码"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            prefixIcon={<Lock size={20} />}
            showPasswordToggle
            fullWidth
          />

          <div className="mt-lg">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              loading={isSubmitting}
              disabled={!canSubmit}
              onClick={handleSubmit}
            >
              修改密码
            </Button>
          </div>
        </div>
      </div>
    </SafeArea>
  );
}
