import api from "./api";
import type { AdminUserListResponse, AdminUserItem, AdminUserCreateRequest, AdminUserUpdateRequest, AdminResetPasswordRequest } from "@/types/role";

export function fetchUsers(params: { page?: number; page_size?: number; search?: string }): Promise<AdminUserListResponse> {
  return api.get("/admin/users", { params }).then(r => r.data.data);
}

export function fetchUser(userId: string): Promise<AdminUserItem> {
  return api.get(`/admin/users/${userId}`).then(r => r.data.data);
}

export function createUser(data: AdminUserCreateRequest): Promise<AdminUserItem> {
  return api.post("/admin/users", data).then(r => r.data.data);
}

export function updateUser(userId: string, data: AdminUserUpdateRequest): Promise<AdminUserItem> {
  return api.put(`/admin/users/${userId}`, data).then(r => r.data.data);
}

export function deleteUser(userId: string): Promise<void> {
  return api.delete(`/admin/users/${userId}`);
}

export function resetUserPassword(userId: string, data: AdminResetPasswordRequest): Promise<AdminUserItem> {
  return api.post(`/admin/users/${userId}/reset-password`, data).then(r => r.data.data);
}

