export type AIProvider = "openai" | "qwen" | "wenxin" | "deepseek";

export interface AIConfig {
  id: string;
  provider: AIProvider;
  model_name: string;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
  top_p: number;
  is_active: boolean;
  last_test_at: string | null;
}

export interface AIConfigCreate {
  provider: AIProvider;
  api_key: string;
  model_name: string;
  base_url?: string | null;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export interface AIConfigUpdate {
  provider?: AIProvider;
  api_key?: string;
  model_name?: string;
  base_url?: string | null;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export interface AITestRequest {
  provider: AIProvider;
  api_key: string;
  model_name: string;
  base_url?: string | null;
}

export interface AITestResult {
  ok: boolean;
  detail: string;
}
