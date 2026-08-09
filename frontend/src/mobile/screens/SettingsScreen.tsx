// @ts-nocheck
import React from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, User, Key, Bot, Info, LogOut } from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Avatar from "@/mobile/components/ui/Avatar";
import { useToast } from "@/mobile/components/ui/Toast";

const MENU_ITEMS = [
  {
    key: "profile",
    icon: <User size={20} />,
    label: "个人资料",
    path: "/m/profile",
  },
  {
    key: "password",
    icon: <Key size={20} />,
    label: "修改密码",
    path: "/m/change-password",
  },
  {
    key: "ai-assistant",
    icon: <Bot size={20} />,
    label: "AI 助手",
    path: "/m/chat",
  },
];

export default function SettingsScreen() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const handleLogout = () => {
    if (window.confirm("确定退出登录？")) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      showToast?.("已退出登录", "info");
      navigate("/m/login");
    }
  };

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="设置" largeTitle />

      <div className="px-md space-y-md mt-md">
        {/* 账户信息 */}
        <motion.div whileTap={{ scale: 0.99 }}>
          <button
            className="w-full bg-white rounded-md shadow-card p-md flex items-center gap-md"
            onClick={() => navigate("/m/profile")}
          >
            <Avatar name="用户" size="md" />
            <div className="flex-1 text-left">
              <p className="text-body font-semibold text-neutral-900">账户信息</p>
              <p className="text-caption text-neutral-400">user@example.com</p>
            </div>
            <ChevronRight size={16} className="text-neutral-400" />
          </button>
        </motion.div>

        {/* 菜单项 */}
        <div className="bg-white rounded-md shadow-card overflow-hidden">
          {MENU_ITEMS.map((item) => (
            <motion.button
              key={item.key}
              whileTap={{ scale: 0.99 }}
              className="w-full flex items-center gap-md px-md h-14 border-b border-neutral-50 last:border-0"
              onClick={() => navigate(item.path)}
            >
              <span className="text-neutral-600">{item.icon}</span>
              <span className="flex-1 text-left text-body text-neutral-900">{item.label}</span>
              {item.sub && (
                <span className="text-caption text-neutral-400 mr-sm">{item.sub}</span>
              )}
              <ChevronRight size={16} className="text-neutral-400" />
            </motion.button>
          ))}
        </div>

        {/* 关于 */}
        <div className="bg-white rounded-md shadow-card p-md">
          <div className="flex items-center gap-md">
            <Info size={20} className="text-neutral-600" />
            <div>
              <p className="text-body text-neutral-900">关于</p>
              <p className="text-caption text-neutral-400">版本 1.0.0 · GB/T 29639-2020 标准合规</p>
            </div>
          </div>
        </div>

        {/* 退出登录 */}
        <div className="text-center pt-md">
          <button
            className="text-red-500 text-body font-medium py-2"
            onClick={handleLogout}
          >
            <span className="flex items-center justify-center gap-sm">
              <LogOut size={18} /> 退出登录
            </span>
          </button>
        </div>
      </div>
    </SafeArea>
  );
}
