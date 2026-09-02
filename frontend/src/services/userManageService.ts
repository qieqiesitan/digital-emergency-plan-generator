import api from "./api";
import type { AdminUserListResponse, AdminUserItem, AdminUserCreateRequest, AdminUserUpdateRequest, AdminResetPasswordRequest } from "@/types/role";

export function fetchUsers(params: { page?: number; page_size?: number; search?: string }): Promise<AdminUserListResponse> {
  return api.get("/admin/users", { params }).then(r => r.data.data);
}

export function fetchUser(userId: string): Promise<AdminUserItem> {
  return api.get(`/admin/users/${userId}`).then(r => r.data.data);
}

export function createUser(data: AdminUserCreateRequest): Promise<AdminUserItem> {
  // UserManagePage 创建 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.post("/admin/users", data, { skipGlobalError: true }).then(r => r.data.data);
}

export function updateUser(userId: string, data: AdminUserUpdateRequest): Promise<AdminUserItem> {
  // UserManagePage 更新 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.put(`/admin/users/${userId}`, data, { skipGlobalError: true }).then(r => r.data.data);
}

export function deleteUser(userId: string): Promise<void> {
  // UserManagePage 删除 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.delete(`/admin/users/${userId}`, { skipGlobalError: true });
}

export function resetUserPassword(userId: string, data: AdminResetPasswordRequest): Promise<AdminUserItem> {
  // UserManagePage 重置密码 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.post(`/admin/users/${userId}/reset-password`, data, { skipGlobalError: true }).then(r => r.data.data);
}

