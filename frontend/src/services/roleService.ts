import api from "./api";
import type { Role, Permission, RoleCreateRequest, RoleUpdateRequest } from "@/types/role";

export function fetchRoles(): Promise<Role[]> {
  return api.get("/roles").then(r => r.data.data);
}

export function fetchRole(roleId: string): Promise<Role> {
  return api.get(`/roles/${roleId}`).then(r => r.data.data);
}

export function createRole(data: RoleCreateRequest): Promise<Role> {
  // RoleManagePage 创建 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.post("/roles", data, { skipGlobalError: true }).then(r => r.data.data);
}

export function updateRole(roleId: string, data: RoleUpdateRequest): Promise<Role> {
  // RoleManagePage 更新 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.put(`/roles/${roleId}`, data, { skipGlobalError: true }).then(r => r.data.data);
}

export function deleteRole(roleId: string): Promise<void> {
  // RoleManagePage 删除 mutation 自带 message.error，跳过全局 toast 防双弹
  return api.delete(`/roles/${roleId}`, { skipGlobalError: true });
}

export function fetchPermissions(): Promise<Permission[]> {
  return api.get("/roles/permissions/list").then(r => r.data.data);
}

export function fetchMyMenus(): Promise<string[]> {
  return api.get("/roles/my-menus").then(r => r.data.data);
}

