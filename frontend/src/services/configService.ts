import api from "./api";
import type { ApiResponse } from "@/types/common";

export interface SystemConfig {
  id: number;
  config_key: string;
  config_value: string;
  config_type: string;
  description: string;
}

export interface ConfigSetRequest {
  value: string;
  type?: string;
  description?: string;
}

export async function fetchConfigs(): Promise<SystemConfig[]> {
  const res = await api.get<ApiResponse<SystemConfig[]>>("/configs");
  return res.data.data;
}

export async function getConfig(key: string): Promise<SystemConfig> {
  const res = await api.get<ApiResponse<SystemConfig>>(`/configs/${key}`);
  return res.data.data;
}

export async function setConfig(
  key: string,
  value: string,
  type?: string,
  description?: string
): Promise<SystemConfig> {
  const res = await api.put<ApiResponse<SystemConfig>>(`/configs/${key}`, {
    value,
    type,
    description,
  });
  return res.data.data;
}

export async function deleteConfig(key: string): Promise<void> {
  await api.delete(`/configs/${key}`);
}
