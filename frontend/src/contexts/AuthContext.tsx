import { useState, useEffect, useCallback, type ReactNode } from "react";
import { message } from "antd";
import type { LoginRequest, RegisterRequest } from "@/types/auth";
import * as authService from "@/services/authService";
import * as userService from "@/services/authService";
import { fetchMyMenus } from "@/services/roleService";
import { AuthContext, type AuthState } from "@/contexts/useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  // 初始态直接由「本地是否有 token」决定：无 token 时不需要在 effect 里再 setState 收尾
  const [state, setState] = useState<AuthState>(() => ({
    user: null,
    isAuthenticated: false,
    isLoading: !!localStorage.getItem("access_token"),
    menuPermissions: [],
    menuLoading: false,
    menuLoadFailed: false,
  }));

  const loadMenuPermissions = useCallback(async () => {
    setState((prev) => ({ ...prev, menuLoading: true }));
    try {
      const menus = await fetchMyMenus();
      setState((prev) => ({ ...prev, menuPermissions: menus, menuLoading: false, menuLoadFailed: false }));
    } catch {
      // 菜单权限加载失败：降级为核心菜单（工作台/企业/预案/个人资料），并标记提示
      console.warn("菜单权限加载失败，已降级为核心菜单");
      setState((prev) => ({
        ...prev,
        menuPermissions: ["menu:dashboard", "menu:enterprises", "menu:plans", "menu:profile"],
        menuLoading: false,
        menuLoadFailed: true,
      }));
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      userService.getProfile()
        .then((user) => {
          setState((prev) => ({ ...prev, user, isAuthenticated: true, isLoading: false, menuLoading: true }));
          return loadMenuPermissions();
        })
        .catch(() => {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          setState((prev) => ({ ...prev, user: null, isAuthenticated: false, isLoading: false, menuLoading: false }));
        });
    }
  }, [loadMenuPermissions]);

  useEffect(() => {
    const handler = () => {
      // 登录过期（refresh 失败）时给出一次性友好提示，避免用户不明原因被登出
      message.warning("登录已过期，请重新登录");
      setState({ user: null, isAuthenticated: false, isLoading: false, menuPermissions: [], menuLoading: false, menuLoadFailed: false });
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    };
    window.addEventListener("auth:logout", handler);
    return () => window.removeEventListener("auth:logout", handler);
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    const tokenResp = await authService.login(data);
    localStorage.setItem("access_token", tokenResp.access_token);
    localStorage.setItem("refresh_token", tokenResp.refresh_token);
    const user = await userService.getProfile();
    setState({ user, isAuthenticated: true, isLoading: false, menuPermissions: [], menuLoading: true, menuLoadFailed: false });
    await loadMenuPermissions();
  }, [loadMenuPermissions]);

  const register = useCallback(async (data: RegisterRequest) => {
    await authService.register(data);
    const tokenResp = await authService.login({ email: data.email, password: data.password });
    localStorage.setItem("access_token", tokenResp.access_token);
    localStorage.setItem("refresh_token", tokenResp.refresh_token);
    const user = await userService.getProfile();
    setState({ user, isAuthenticated: true, isLoading: false, menuPermissions: [], menuLoading: true, menuLoadFailed: false });
    await loadMenuPermissions();
  }, [loadMenuPermissions]);

  const logout = useCallback(() => {
    const refreshToken = localStorage.getItem("refresh_token");
    authService.logout(refreshToken ?? undefined).catch(() => {});
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setState({ user: null, isAuthenticated: false, isLoading: false, menuPermissions: [], menuLoading: false, menuLoadFailed: false });
  }, []);

  const updateProfile = useCallback(async (name: string) => {
    const user = await userService.updateProfile({ name });
    setState((prev) => ({ ...prev, user }));
  }, []);

  const changePassword = useCallback(async (oldPwd: string, newPwd: string) => {
    await userService.changePassword({
      old_password: oldPwd,
      new_password: newPwd,
      new_password_confirm: newPwd,
    });
    logout();
  }, [logout]);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, updateProfile, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

