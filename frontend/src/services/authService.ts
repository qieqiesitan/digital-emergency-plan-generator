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

// ponytail: merged from userService.ts
import type { User, UpdateProfileRequest, ChangePasswordRequest } from "@/types/auth";
import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { User, UpdateProfileRequest, ChangePasswordRequest } from "@/types/auth";

export async function getProfile(): Promise<User> {
  const res = await api.get<ApiResponse<User>>("/users/me");
  return res.data.data;
}

export async function updateProfile(data: UpdateProfileRequest): Promise<User> {
  const res = await api.put<ApiResponse<User>>("/users/me", data);
  return res.data.data;
}

export async function changePassword(data: ChangePasswordRequest): Promise<void> {
  await api.put("/users/me/password", data);
}