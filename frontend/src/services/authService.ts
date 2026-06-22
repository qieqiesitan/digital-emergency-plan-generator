import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { LoginRequest, RegisterRequest, TokenResponse, User } from "@/types/auth";

export async function register(data: RegisterRequest): Promise<User> {
  const res = await api.post<ApiResponse<User>>("/auth/register", data);
  return res.data.data;
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const res = await api.post<ApiResponse<TokenResponse>>("/auth/login", data);
  return res.data.data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const res = await api.post<ApiResponse<TokenResponse>>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return res.data.data;
}

export async function logout(refreshToken?: string): Promise<void> {
  await api.post("/auth/logout", refreshToken ? { refresh_token: refreshToken } : {});
}
