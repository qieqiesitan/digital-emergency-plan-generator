import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { User, LoginRequest, RegisterRequest } from "@/types/auth";
import * as authService from "@/services/authService";
import * as userService from "@/services/userService";
import { isYwtMode, getToken, getUsername } from "@/utils/platform";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
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
  });

  // 初始化：中台模式用注入 token 调 /users/me；独立模式用 localStorage token
  useEffect(() => {
    if (isYwtMode()) {
      // 中台 qiankun 模式：用注入的 token 获取用户信息
      const token = getToken();
      if (token) {
        userService.getProfile()
          .then((user) => {
            setState({ user, isAuthenticated: true, isLoading: false });
          })
          .catch(() => {
            // token 无效，标记未认证（中台会重新注入）
            setState({ user: null, isAuthenticated: false, isLoading: false });
          });
      } else {
        setState({ user: null, isAuthenticated: false, isLoading: false });
      }
    } else {
      // 独立模式：检查 localStorage 中是否有 token
      const token = localStorage.getItem("access_token");
      if (token) {
        userService.getProfile()
          .then((user) => {
            setState({ user, isAuthenticated: true, isLoading: false });
          })
          .catch(() => {
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            setState({ user: null, isAuthenticated: false, isLoading: false });
          });
      } else {
        setState({ user: null, isAuthenticated: false, isLoading: false });
      }
    }
  }, []);

  // 监听 API 拦截器发出的 auth:logout 事件
  useEffect(() => {
    const handler = () => {
      setState({ user: null, isAuthenticated: false, isLoading: false });
      if (!isYwtMode()) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
    };
    window.addEventListener("auth:logout", handler);
    return () => window.removeEventListener("auth:logout", handler);
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    if (isYwtMode()) return; // 中台模式：用户由中台管理
    const tokenResp = await authService.login(data);
    localStorage.setItem("access_token", tokenResp.access_token);
    localStorage.setItem("refresh_token", tokenResp.refresh_token);
    const user = await userService.getProfile();
    setState({ user, isAuthenticated: true, isLoading: false });
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    if (isYwtMode()) return; // 中台模式：用户由中台管理
    await authService.register(data);
    const tokenResp = await authService.login({ email: data.email, password: data.password });
    localStorage.setItem("access_token", tokenResp.access_token);
    localStorage.setItem("refresh_token", tokenResp.refresh_token);
    const user = await userService.getProfile();
    setState({ user, isAuthenticated: true, isLoading: false });
  }, []);

  const logout = useCallback(() => {
    if (isYwtMode()) {
      // 中台模式：只清本地状态，登出由中台处理
      setState({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }
    const refreshToken = localStorage.getItem("refresh_token");
    authService.logout(refreshToken ?? undefined).catch(() => {});
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setState({ user: null, isAuthenticated: false, isLoading: false });
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
