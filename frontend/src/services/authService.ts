import api from "./api";
import type { ApiResponse } from "@/types/common";
import type {
  LoginRequest, RegisterRequest, TokenResponse, User,
  UpdateProfileRequest, ChangePasswordRequest,
} from "@/types/auth";

export async function register(data: RegisterRequest): Promise<User> {
  // 注册/登录页自带内联错误提示，跳过全局 toast 避免双提示
  const res = await api.post<ApiResponse<User>>("/auth/register", data, { skipGlobalError: true });
  return res.data.data;
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  // 登录页自带内联错误提示，跳过全局 toast 避免双提示
  const res = await api.post<ApiResponse<TokenResponse>>("/auth/login", data, { skipGlobalError: true });
  return res.data.data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const res = await api.post<ApiResponse<TokenResponse>>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return res.data.data;
}

export async function logout(refreshToken?: string): Promise<void> {
  // 登出为主动清理动作，调用方已 .catch(() => {}) 静默处理，失败不打扰用户
  await api.post("/auth/logout", refreshToken ? { refresh_token: refreshToken } : {}, { skipGlobalError: true });
}

// ponytail: merged from userService.ts
export async function getProfile(): Promise<User> {
  const res = await api.get<ApiResponse<User>>("/users/me");
  return res.data.data;
}

export async function updateProfile(data: UpdateProfileRequest): Promise<User> {
  // 个人资料页（桌面/移动端）已自行 message.error，跳过全局 toast
  const res = await api.put<ApiResponse<User>>("/users/me", data, { skipGlobalError: true });
  return res.data.data;
}

export async function changePassword(data: ChangePasswordRequest): Promise<void> {
  // 修改密码页（桌面/移动端）已自行提示，跳过全局 toast
  await api.put("/users/me/password", data, { skipGlobalError: true });
}
