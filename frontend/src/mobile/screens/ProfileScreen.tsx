// @ts-nocheck
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import NavBar from "@/mobile/components/ui/NavBar";
import Input from "@/mobile/components/ui/Input";
import Button from "@/mobile/components/ui/Button";
import Avatar from "@/mobile/components/ui/Avatar";
import Card from "@/mobile/components/ui/Card";
import SafeArea from "@/mobile/components/ui/SafeArea";
import { useToast } from "@/mobile/components/ui/Toast";
import { ChevronRight, Lock, LogOut } from "lucide-react";

export default function ProfileScreen() {
  const navigate = useNavigate();
  const { user, updateProfile, logout } = useAuth();
  const { showToast } = useToast();
  const [name, setName] = useState(user?.name ?? "");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await updateProfile(name.trim());
      setEditing(false);
      showToast({ type: "success", message: "姓名已更新" });
    } catch (err: any) {
      showToast({
        type: "error",
        message: err?.response?.data?.message || "更新失败",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/m/login", { replace: true });
  };

  return (
    <SafeArea edge="top">
      <div className="flex flex-col min-h-dvh bg-neutral-50">
        <NavBar title="个人资料" showBack onBack={() => navigate(-1)} />

        <div className="flex flex-col items-center py-xl">
          <Avatar name={user?.name} size="lg" colorSeed={user?.email} />
        </div>

        <div className="px-md flex flex-col gap-md">
          <Card>
            <div className="flex items-center justify-between h-11">
              <span className="text-body-sm text-neutral-600 w-16">姓名</span>
              {editing ? (
                <div className="flex-1 flex items-center gap-sm">
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="flex-1"
                  />
                  <Button size="sm" onClick={handleSave} loading={saving}>
                    保存
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setName(user?.name ?? "");
                      setEditing(false);
                    }}
                  >
                    取消
                  </Button>
                </div>
              ) : (
                <div
                  className="flex-1 flex items-center justify-between cursor-pointer"
                  onClick={() => setEditing(true)}
                >
                  <span className="text-body text-neutral-900">{name}</span>
                  <span className="text-caption text-primary-500">编辑</span>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between h-11">
              <span className="text-body-sm text-neutral-600">邮箱</span>
              <div className="flex items-center gap-sm">
                <span className="text-body text-neutral-400">
                  {user?.email}
                </span>
                <Lock size={14} className="text-neutral-400" />
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between h-11">
              <span className="text-body-sm text-neutral-600">注册时间</span>
              <span className="text-body text-neutral-400">
                {user?.created_at
                  ? new Date(user.created_at).toLocaleDateString("zh-CN")
                  : "-"}
              </span>
            </div>
          </Card>

          <Card
            pressable
            onClick={() => navigate("/m/settings/password")}
          >
            <div className="flex items-center justify-between h-11">
              <span className="text-body text-neutral-900">修改密码</span>
              <ChevronRight size={20} className="text-neutral-400" />
            </div>
          </Card>

          <div className="mt-md">
            <Button variant="danger" fullWidth onClick={handleLogout}>
              退出登录
            </Button>
          </div>
        </div>
      </div>
    </SafeArea>
  );
}
