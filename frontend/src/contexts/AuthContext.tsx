import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { User, LoginRequest, RegisterRequest } from "@/types/auth";
import * as authService from "@/services/authService";
import * as userService from "@/services/authService";
import { fetchMyMenus } from "@/services/roleService";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  menuPermissions: string[];
  menuLoadFailed: boolean;
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  updateProfile: (name: string) => Promise<void>;
  changePassword: (oldPwd: string, newPwd: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    menuPermissions: [],
    menuLoadFailed: false,
  });

  const loadMenuPermissions = useCallback(async () => {
    try {
      const menus = await fetchMyMenus();
      setState((prev) => ({ ...prev, menuPermissions: menus, menuLoadFailed: false }));
    } catch {
      // 菜单权限加载失败：降级为核心菜单（工作台/企业/预案/个人资料），并标记提示
      console.warn("菜单权限加载失败，已降级为核心菜单");
      setState((prev) => ({
        ...prev,
        menuPermissions: ["menu:dashboard", "menu:enterprises", "menu:plans", "menu:profile"],
        menuLoadFailed: true,
      }));
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      userService.getProfile()
        .then((user) => {
          setState((prev) => ({ ...prev, user, isAuthenticated: true, isLoading: false }));
          return loadMenuPermissions();
        })
        .catch(() => {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          setState((prev) => ({ ...prev, user: null, isAuthenticated: false, isLoading: false }));
        });
    } else {
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, [loadMenuPermissions]);

  useEffect(() => {
    const handler = () => {
      setState({ user: null, isAuthenticated: false, isLoading: false, menuPermissions: [], menuLoadFailed: false });
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
    setState({ user, isAuthenticated: true, isLoading: false, menuPermissions: [], menuLoadFailed: false });
    await loadMenuPermissions();
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    await authService.register(data);
    const tokenResp = await authService.login({ email: data.email, password: data.password });
    localStorage.setItem("access_token", tokenResp.access_token);
    localStorage.setItem("refresh_token", tokenResp.refresh_token);
    const user = await userService.getProfile();
    setState({ user, isAuthenticated: true, isLoading: false, menuPermissions: [], menuLoadFailed: false });
    await loadMenuPermissions();
  }, []);

  const logout = useCallback(() => {
    const refreshToken = localStorage.getItem("refresh_token");
    authService.logout(refreshToken ?? undefined).catch(() => {});
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setState({ user: null, isAuthenticated: false, isLoading: false, menuPermissions: [], menuLoadFailed: false });
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

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
