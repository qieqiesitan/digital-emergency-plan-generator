import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { ApiResponse } from "@/types/common";
import type { DataDictItem, DataDictPayload } from "@/types/dataDict";

/** 系统级字典（需管理员）。 */
export const listSystemDicts = (dictType?: string) =>
  api
    .get<ApiResponse<DataDictItem[]>>("/settings/data-dicts", {
      params: { dict_type: dictType },
    })
    .then(r => r.data.data);

export const createSystemDict = (payload: DataDictPayload) =>
  api
    // DataDictManagePage 创建 mutation 自带 message.error，跳过全局 toast 防双弹
    .post<ApiResponse<DataDictItem>>("/settings/data-dicts", payload, { skipGlobalError: true })
    .then(r => r.data.data);

export const updateSystemDict = (id: string, patch: Partial<DataDictPayload>) =>
  api
    // DataDictManagePage 更新 mutation 自带 message.error，跳过全局 toast 防双弹
    .put<ApiResponse<DataDictItem>>(`/settings/data-dicts/${id}`, patch, { skipGlobalError: true })
    .then(r => r.data.data);

/** 企业级字典（GET 返回系统+企业合并视图）。 */
export const listEnterpriseDicts = (enterpriseId: string, dictType?: string) =>
  api
    .get<ApiResponse<DataDictItem[]>>(`/enterprises/${enterpriseId}/data-dicts`, {
      params: { dict_type: dictType },
    })
    .then(r => r.data.data);

export const createEnterpriseDict = (
  enterpriseId: string,
  payload: DataDictPayload,
  config?: AxiosRequestConfig,
) => {
  const req = config
    ? api.post<ApiResponse<DataDictItem>>(`/enterprises/${enterpriseId}/data-dicts`, payload, config)
    : api.post<ApiResponse<DataDictItem>>(`/enterprises/${enterpriseId}/data-dicts`, payload);
  return req.then(r => r.data.data);
};

export const updateEnterpriseDict = (
  enterpriseId: string,
  id: string,
  patch: Partial<DataDictPayload>,
  config?: AxiosRequestConfig,
) => {
  const req = config
    ? api.put<ApiResponse<DataDictItem>>(`/enterprises/${enterpriseId}/data-dicts/${id}`, patch, config)
    : api.put<ApiResponse<DataDictItem>>(`/enterprises/${enterpriseId}/data-dicts/${id}`, patch);
  return req.then(r => r.data.data);
};

export const deleteEnterpriseDict = (enterpriseId: string, id: string, config?: AxiosRequestConfig) => {
  const req = config
    ? api.delete<ApiResponse<DataDictItem>>(`/enterprises/${enterpriseId}/data-dicts/${id}`, config)
    : api.delete<ApiResponse<DataDictItem>>(`/enterprises/${enterpriseId}/data-dicts/${id}`);
  return req.then(r => r.data.data);
};
