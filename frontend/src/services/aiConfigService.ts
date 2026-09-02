import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { AIConfig, AIConfigCreate, AIConfigUpdate, AITestRequest, AITestResult } from "@/types/aiConfig";

export async function getAIConfig(): Promise<AIConfig | null> {
  try {
    const res = await api.get<ApiResponse<AIConfig>>("/settings/ai-config");
    return res.data.data;
  } catch {
    return null;
  }
}

export async function updateAIConfig(data: AIConfigCreate | AIConfigUpdate): Promise<AIConfig> {
  // AIConfigPage 保存 mutation 自带 message.error，跳过全局 toast 防双弹
  const res = await api.put<ApiResponse<AIConfig>>("/settings/ai-config", data, { skipGlobalError: true });
  return res.data.data;
}

export async function deleteAIConfig(): Promise<void> {
  await api.delete("/settings/ai-config");
}

export async function testAIConnection(data: AITestRequest): Promise<AITestResult> {
  // AIConfigPage 测试连接失败展示本地 Alert 状态，跳过全局 toast 防双弹
  const res = await api.post<ApiResponse<AITestResult>>("/settings/ai-config/test", data, { skipGlobalError: true });
  return res.data.data;
}
