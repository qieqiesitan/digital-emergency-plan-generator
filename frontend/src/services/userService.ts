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
