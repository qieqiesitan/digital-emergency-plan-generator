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
    onSuccess: () => { message.success("已保存"); queryClient.invalidateQueries({ queryKey: ["aiConfig"] }); },
    onError: () => message.error("保存失败"),
  });

  const handleTest = async () => {
    const vals = await form.validateFields();
    setTesting(true); setTestResult(null);
    try { setTestResult(await testAIConnection({ provider: vals.provider, api_key: vals.api_key, model_name: vals.model_name, base_url: vals.base_url || null })); }
    catch { setTestResult({ ok: false, detail: "请求失败" }); }
    finally { setTesting(false); }
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <PageHeader title="AI 配置" />
      <Card title="模型配置" style={{ marginBottom: 24 }}>
        <Form form={form} layout="vertical" initialValues={config ? { ...config } : { temperature: 0.7, max_tokens: 4096, top_p: 1.0 }}>
          <Form.Item name="provider" label="服务商" rules={[{ required: true }]}>
            <Select options={PROVIDERS} onChange={(p: AIProvider) => form.setFieldsValue({ base_url: DEFAULT_URLS[p], model_name: DEFAULT_MODELS[p], api_key: "" })} />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="model_name" label="模型名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="base_url" label="接口地址">
            <Input />
          </Form.Item>
          <Collapse ghost items={[{ key: "adv", label: "高级参数",
            children: <>
              <Form.Item name="temperature" label="温度"><Slider min={0} max={2} step={0.1} /></Form.Item>
              <Form.Item name="max_tokens" label="最大 Token"><InputNumber min={1} max={128000} style={{ width: "100%" }} /></Form.Item>
              <Form.Item name="top_p" label="Top P"><Slider min={0} max={1} step={0.05} /></Form.Item>
            </>
          }]} />
          <div style={{ display: "flex", gap: 12 }}>
            <Button onClick={handleTest} loading={testing}>测试连接</Button>
            <Button type="primary" loading={saveMut.isPending} onClick={() => form.validateFields().then((v) => saveMut.mutate(v))}>保存</Button>
          </div>
        </Form>
      </Card>
      <Card title="连接状态">
        {testResult ? (
          <Alert type={testResult.ok ? "success" : "error"} title={testResult.ok ? "连接成功：" + testResult.detail : "连接失败：" + testResult.detail} showIcon />
        ) : config?.last_test_at ? (
          <Alert type="success" title={"上次测试：" + new Date(config.last_test_at).toLocaleString()} showIcon />
        ) : (
          <Alert type="info" message="尚未测试" showIcon />
        )}
      </Card>
      {config && <Button danger style={{ marginTop: 24 }} onClick={() => { deleteAIConfig().then(() => { message.success("已删除"); queryClient.invalidateQueries({ queryKey: ["aiConfig"] }); form.resetFields(); }); }}>删除配置</Button>}
    </div>
  );
}
