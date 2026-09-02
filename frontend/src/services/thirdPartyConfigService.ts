import api from "./api";
import type { ApiResponse } from "@/types/common";

/** GET /system/third-party-config 返回的配置项（secret 只含掩码，不含明文） */
export interface ThirdPartyConfigItem {
  key: string;
  label: string;
  configured: boolean;
  masked_value: string;
  type: string;
  description: string;
}

/** PUT /system/third-party-config 批量更新的单条载荷 */
export interface ThirdPartyConfigUpdateItem {
  key: string;
  value: string;
}

/** 获取全部第三方接口配置（走 api 实例自动带 token） */
export async function getThirdPartyConfig(): Promise<ThirdPartyConfigItem[]> {
  const res = await api.get<ApiResponse<ThirdPartyConfigItem[]>>(
    "/system/third-party-config",
  );
  return res.data.data;
}

/** 批量更新第三方接口配置，返回已更新的 key 列表 */
export async function updateThirdPartyConfig(
  items: ThirdPartyConfigUpdateItem[],
): Promise<string[]> {
  // ThirdPartyConfigPage 保存 mutation 自带 message.error，跳过全局 toast 防双弹
  const res = await api.put<ApiResponse<string[]>>(
    "/system/third-party-config",
    items,
    { skipGlobalError: true },
  );
  return res.data.data;
}
