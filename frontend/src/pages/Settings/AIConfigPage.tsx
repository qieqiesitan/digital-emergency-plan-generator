import { useState } from "react";
import { Card, Form, Select, Input, Slider, InputNumber, Button, message, Alert, Collapse } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAIConfig, updateAIConfig, testAIConnection, deleteAIConfig } from "@/services/aiConfigService";
import { PageHeader } from "@/components/common/PageHeader";
import type { AIProvider, AITestResult } from "@/types/aiConfig";

const PROVIDERS: { value: AIProvider; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "qwen", label: "Qwen" },
  { value: "wenxin", label: "Wenxin" },
  { value: "deepseek", label: "DeepSeek" },
];

const DEFAULT_URLS: Record<AIProvider, string> = {
  openai: "https://api.openai.com/v1",
  qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  wenxin: "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
  deepseek: "https://api.deepseek.com/v1",
};
const DEFAULT_MODELS: Record<AIProvider, string> = {
  openai: "gpt-4o", qwen: "qwen-turbo", wenxin: "ernie-4.0-8k", deepseek: "deepseek-chat",
};

export default function AIConfigPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [testResult, setTestResult] = useState<AITestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const { data: config } = useQuery({ queryKey: ["aiConfig"], queryFn: getAIConfig });

  const saveMut = useMutation({
    mutationFn: updateAIConfig,
    onSuccess: () => { message.success("saved"); queryClient.invalidateQueries({ queryKey: ["aiConfig"] }); },
    onError: () => message.error("save failed"),
  });

  const handleTest = async () => {
    const vals = await form.validateFields();
    setTesting(true); setTestResult(null);
    try { setTestResult(await testAIConnection({ provider: vals.provider, api_key: vals.api_key, model_name: vals.model_name, base_url: vals.base_url || null })); }
    catch { setTestResult({ ok: false, detail: "request failed" }); }
    finally { setTesting(false); }
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <PageHeader title="AI config" />
      <Card title="model config" style={{ marginBottom: 24 }}>
        <Form form={form} layout="vertical" initialValues={config ? { ...config } : { temperature: 0.7, max_tokens: 4096, top_p: 1.0 }}>
          <Form.Item name="provider" label="provider" rules={[{ required: true }]}>
            <Select options={PROVIDERS} onChange={(p: AIProvider) => form.setFieldsValue({ base_url: DEFAULT_URLS[p], model_name: DEFAULT_MODELS[p], api_key: "" })} />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="model_name" label="model" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="base_url" label="custom API URL">
            <Input />
          </Form.Item>
          <Collapse ghost items={[{ key: "adv", label: "advanced",
            children: <>
              <Form.Item name="temperature" label="Temperature"><Slider min={0} max={2} step={0.1} /></Form.Item>
              <Form.Item name="max_tokens" label="Max Tokens"><InputNumber min={1} max={128000} style={{ width: "100%" }} /></Form.Item>
              <Form.Item name="top_p" label="Top P"><Slider min={0} max={1} step={0.05} /></Form.Item>
            </>
          }]} />
          <div style={{ display: "flex", gap: 12 }}>
            <Button onClick={handleTest} loading={testing}>test connection</Button>
            <Button type="primary" loading={saveMut.isPending} onClick={() => form.validateFields().then((v) => saveMut.mutate(v))}>save</Button>
          </div>
        </Form>
      </Card>
      <Card title="connection status">
        {testResult ? (
          <Alert type={testResult.ok ? "success" : "error"} title={testResult.ok ? "connected: " + testResult.detail : "failed: " + testResult.detail} showIcon />
        ) : config?.last_test_at ? (
          <Alert type="success" title={"last test: " + new Date(config.last_test_at).toLocaleString()} showIcon />
        ) : (
          <Alert type="info" message="not tested" showIcon />
        )}
      </Card>
      {config && <Button danger style={{ marginTop: 24 }} onClick={() => { deleteAIConfig().then(() => { message.success("deleted"); queryClient.invalidateQueries({ queryKey: ["aiConfig"] }); form.resetFields(); }); }}>delete config</Button>}
    </div>
  );
}
