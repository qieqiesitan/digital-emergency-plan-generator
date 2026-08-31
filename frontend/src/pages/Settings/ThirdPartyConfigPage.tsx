import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  message,
  Spin,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getThirdPartyConfig,
  updateThirdPartyConfig,
} from "@/services/thirdPartyConfigService";
import type { ThirdPartyConfigUpdateItem } from "@/services/thirdPartyConfigService";
import { PageHeader } from "@/components/common/PageHeader";

/** 配置分组：组名 -> config_key 列表（顺序与后端 KEY_SPEC 保持一致） */
const GROUPS: { title: string; keys: string[] }[] = [
  {
    title: "企查查",
    keys: [
      "third_party.qcc.api_key",
      "third_party.qcc.api_key_fallback",
      "third_party.qcc.endpoint",
    ],
  },
  {
    title: "高德",
    keys: ["third_party.amap.api_key"],
  },
  {
    title: "PROTEGO",
    keys: [
      "third_party.protego.hmac_secret",
      "third_party.protego.callback_url",
    ],
  },
];

/** 解析请求错误：优先透出后端 detail，其次 e.message，最后兜底文案 */
function errorDetail(e: unknown, fallback: string): string {
  const resp = (e as { response?: { data?: { detail?: unknown } } })?.response;
  const detail = resp?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  return e instanceof Error && e.message ? e.message : fallback;
}

export default function ThirdPartyConfigPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();

  const { data: items = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["thirdPartyConfig"],
    queryFn: getThirdPartyConfig,
  });

  const saveMut = useMutation({
    mutationFn: updateThirdPartyConfig,
    onSuccess: () => {
      message.success("已保存");
      queryClient.invalidateQueries({ queryKey: ["thirdPartyConfig"] });
      form.resetFields();
    },
    onError: (e: unknown) => message.error(errorDetail(e, "保存失败")),
  });

  const handleSave = async () => {
    const values = await form.validateFields();
    // 空值忽略：已配置项留空保持不变，未配置项留空不提交
    const payload: ThirdPartyConfigUpdateItem[] = GROUPS.flatMap(
      (group) => group.keys,
    )
      .filter((key) => String(values[key] ?? "").trim() !== "")
      .map((key) => ({ key, value: String(values[key]).trim() }));
    if (payload.length === 0) {
      message.info("未填写任何配置项");
      return;
    }
    saveMut.mutate(payload);
  };

  if (isLoading) {
    return (
      <div style={{ maxWidth: 600 }}>
        <PageHeader title="第三方接口配置" />
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ maxWidth: 600 }}>
        <PageHeader title="第三方接口配置" />
        <Alert
          type="error"
          message="加载配置失败"
          showIcon
          action={<Button onClick={() => refetch()}>重试</Button>}
        />
      </div>
    );
  }

  const itemByKey = new Map(items.map((item) => [item.key, item]));

  return (
    <div style={{ maxWidth: 600 }}>
      <PageHeader title="第三方接口配置" />
      <Form form={form} layout="vertical">
        {GROUPS.map((group) => (
          <Card key={group.title} title={group.title} style={{ marginBottom: 24 }}>
            {group.keys.map((key) => {
              const item = itemByKey.get(key);
              if (!item) return null;
              const placeholder = item.configured
                ? "已配置（留空保持不变）"
                : "未配置";
              return (
                <Form.Item
                  key={key}
                  name={key}
                  label={item.label}
                  extra={
                    <span>
                      {item.description}
                      {item.configured && (
                        <>
                          {"；当前值："}
                          <span style={{ fontFamily: "monospace" }}>
                            {item.masked_value}
                          </span>
                        </>
                      )}
                    </span>
                  }
                >
                  {item.type === "secret" ? (
                    <Input.Password placeholder={placeholder} autoComplete="new-password" />
                  ) : (
                    <Input placeholder={placeholder} />
                  )}
                </Form.Item>
              );
            })}
          </Card>
        ))}
        <Button
          type="primary"
          loading={saveMut.isPending}
          onClick={() => handleSave()}
        >
          保存
        </Button>
      </Form>
    </div>
  );
}
