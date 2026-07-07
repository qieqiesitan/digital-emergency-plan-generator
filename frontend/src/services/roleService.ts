import api from "./api";
import type { Role, Permission, RoleCreateRequest, RoleUpdateRequest } from "@/types/role";

export function fetchRoles(): Promise<Role[]> {
  return api.get("/roles").then(r => r.data.data);
}

export function fetchRole(roleId: string): Promise<Role> {
  return api.get(`/roles/${roleId}`).then(r => r.data.data);
}

export function createRole(data: RoleCreateRequest): Promise<Role> {
  return api.post("/roles", data).then(r => r.data.data);
}

export function updateRole(roleId: string, data: RoleUpdateRequest): Promise<Role> {
  return api.put(`/roles/${roleId}`, data).then(r => r.data.data);
}

export function deleteRole(roleId: string): Promise<void> {
  return api.delete(`/roles/${roleId}`);
}

export function fetchPermissions(): Promise<Permission[]> {
  return api.get("/roles/permissions/list").then(r => r.data.data);
}

export function fetchMyMenus(): Promise<string[]> {
  return api.get("/roles/my-menus").then(r => r.data.data);
}

