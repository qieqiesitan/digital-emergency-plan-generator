export interface Permission {
  id: string;
  code: string;
  name: string;
  resource: string;
  action: string;
  category: string;
}

export interface Role {
  id: string;
  name: string;
  code: string;
  description?: string;
  is_system: boolean;
  permissions: Permission[];
}

export interface RoleCreateRequest {
  name: string;
  code: string;
  description?: string;
  permission_ids: string[];
}

export interface RoleUpdateRequest {
  name?: string;
  description?: string;
  permission_ids?: string[];
}

export interface AdminUserItem {
  id: string;
  email: string;
  name: string;
  role: string;
  created_at?: string;
}

export interface AdminUserListResponse {
  items: AdminUserItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserCreateRequest {
  email: string;
  name: string;
  password: string;
  role: string;
}

export interface AdminUserUpdateRequest {
  name?: string;
  role?: string;
}

export interface AdminResetPasswordRequest {
  new_password: string;
}
