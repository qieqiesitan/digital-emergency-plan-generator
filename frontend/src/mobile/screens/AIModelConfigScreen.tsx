import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Eye, EyeOff, Check, X } from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Input from "@/mobile/components/ui/Input";
import SegmentedControl from "@/mobile/components/ui/SegmentedControl";
import Switch from "@/mobile/components/ui/Switch";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { getAIConfig, updateAIConfig, testAIConnection } from "@/services/aiConfigService";

const PROVIDERS = [
  { key: "openai", label: "OpenAI" },
  { key: "tongyi", label: "通义" },
  { key: "wenxin", label: "文心" },
  { key: "deepseek", label: "DeepSeek" },
];

const PROVIDER_MODELS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
  tongyi: ["qwen-max", "qwen-plus", "qwen-turbo"],
  wenxin: ["ernie-4.0", "ernie-3.5", "ernie-speed"],
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
};

export default function AIModelConfigScreen() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [provider, setProvider] = useState("deepseek");
  const [apiKey, setApiKey] = useState("sk-••••••••");
  const [model, setModel] = useState("deepseek-chat");
  const [showKey, setShowKey] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [topP, setTopP] = useState(1.0);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const models = PROVIDER_MODELS[provider] ?? [];

  const testMutation = useMutation({
    mutationFn: () => testAIConnection(),
    onSuccess: () => {
      setTestResult({ ok: true, message: `✓ 连接成功 — 模型：${model}` });
    },
    onError: (err) => {
      setTestResult({ ok: false, message: `✗ 连接失败 — ${(err as Error).message ?? "未知错误"}` });
    },
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      updateAIConfig({
        provider,
        api_key: apiKey,
        model,
        temperature,
        max_tokens: maxTokens,
        top_p: topP,
      }),
    onSuccess: () => {
      showToast?.("AI 配置已保存", "success");
      navigate(-1);
    },
    onError: () => showToast?.("保存失败", "danger"),
  });

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="AI 模型配置" showBack onBack={() => navigate(-1)} />

      <div className="px-md py-md space-y-lg pb-24">

        {/* 选择提供商 */}
        <div>
          <p className="text-h2 mb-md">选择提供商</p>
          <SegmentedControl
            segments={PROVIDERS}
            activeKey={provider}
            onChange={(k) => {
              setProvider(k);
              setModel(PROVIDER_MODELS[k]?.[0] ?? "");
            }}
          />
        </div>

        {/* API Key */}
        <div>
          <p className="text-h2 mb-md">API Key</p>
          <Input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={setApiKey}
            placeholder="sk-..."
            suffix={
              <button onClick={() => setShowKey(!showKey)} className="text-neutral-400">
                {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            }
          />
        </div>

        {/* 模型选择 */}
        <div>
          <p className="text-h2 mb-md">模型</p>
          <select
            className="w-full h-11 px-3 rounded-md border border-neutral-200 bg-white text-body"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {models.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        {/* 高级参数 */}
        <div>
          <button
            className="flex items-center gap-sm text-body font-semibold text-neutral-700"
            onClick={() => setAdvancedOpen(!advancedOpen)}
          >
            高级参数
            <span className="text-caption text-primary-600">{advancedOpen ? "收起" : "展开"}</span>
          </button>
          {advancedOpen && (
            <div className="mt-md bg-white rounded-md shadow-card p-md space-y-md">
              <div>
                <div className="flex justify-between text-caption text-neutral-400 mb-1">
                  <span>Temperature</span>
                  <span>{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0" max="2" step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <Input
                label="Max Tokens"
                type="number"
                value={String(maxTokens)}
                onChange={(v) => setMaxTokens(parseInt(v, 10) || 4096)}
              />
              <div>
                <div className="flex justify-between text-caption text-neutral-400 mb-1">
                  <span>Top P</span>
                  <span>{topP}</span>
                </div>
                <input
                  type="range"
                  min="0" max="1" step="0.05"
                  value={topP}
                  onChange={(e) => setTopP(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </div>

        {/* 测试连接 */}
        <button
          className="w-full h-11 border border-primary-600 text-primary-600 rounded-md font-semibold text-body flex items-center justify-center gap-sm disabled:opacity-50"
          disabled={testMutation.isPending}
          onClick={() => testMutation.mutate()}
        >
          {testMutation.isPending ? "测试中…" : "测试连接"}
        </button>

        {/* 测试结果 */}
        {testResult && (
          <div className={`flex items-center gap-sm px-md py-3 rounded-md ${
            testResult.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          }`}>
            {testResult.ok ? <Check size={18} /> : <X size={18} />}
            <span className="text-body-sm">{testResult.message}</span>
          </div>
        )}

      </div>

      {/* 保存按钮 */}
      <div className="fixed bottom-0 left-0 right-0 p-md bg-white border-t border-neutral-100"
           style={{ paddingBottom: "calc(16px + var(--safe-bottom))" }}>
        <button
          className="w-full h-12 bg-primary-600 text-white rounded-md font-semibold text-body disabled:opacity-50"
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? "保存中…" : "保存配置"}
        </button>
      </div>
    </SafeArea>
  );
}
