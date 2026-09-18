import { createContext, useContext } from "react";
import type { LoginRequest, RegisterRequest, User } from "@/types/auth";

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  menuPermissions: string[];
  menuLoading: boolean;
  menuLoadFailed: boolean;
}

export interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  updateProfile: (name: string) => Promise<void>;
  changePassword: (oldPwd: string, newPwd: string) => Promise<void>;
}

/** 认证上下文对象：AuthProvider 提供，useAuth 消费 */
export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
