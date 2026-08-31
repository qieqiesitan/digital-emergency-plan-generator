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
import type {
  ThirdPartyConfigItem,
  ThirdPartyConfigUpdateItem,
} from "@/services/thirdPartyConfigService";
import { PageHeader } from "@/components/common/PageHeader";

/** 与后端 VALUE_MAX_LENGTH 保持一致（router third_party_config.py） */
const VALUE_MAX_LENGTH = 2000;

/** 分组标题：key 前缀 -> 组名；未知前缀原样展示，后端新增 key 自动出现 */
const GROUP_TITLES: Record<string, string> = {
  "third_party.qcc": "企查查",
  "third_party.amap": "高德",
  "third_party.protego": "PROTEGO",
};

/** 取 key 的 vendor 前缀（third_party.<vendor>），无法识别时回退整 key */
function groupPrefix(key: string): string {
  const match = /^third_party\.[^.]+/.exec(key);
  return match ? match[0] : key;
}

/** 按 key 前缀动态分组，保持后端返回顺序（新增 key 自动归组或成新组） */
function groupItems(
  items: ThirdPartyConfigItem[],
): { title: string; items: ThirdPartyConfigItem[] }[] {
  const groups = new Map<string, ThirdPartyConfigItem[]>();
  for (const item of items) {
    const prefix = groupPrefix(item.key);
    const list = groups.get(prefix) ?? [];
    list.push(item);
    groups.set(prefix, list);
  }
  return [...groups.entries()].map(([prefix, list]) => ({
    title: GROUP_TITLES[prefix] ?? prefix,
    items: list,
  }));
}

/** 解析请求错误：优先透出后端 detail（兼容 FastAPI 422 数组），其次 e.message，最后兜底文案 */
function errorDetail(e: unknown, fallback: string): string {
  const resp = (e as { response?: { data?: { detail?: unknown } } })?.response;
  const detail = resp?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const joined = detail
      .map((d) => {
        if (typeof d === "string") return d;
        if (
          d &&
          typeof d === "object" &&
          typeof (d as { msg?: unknown }).msg === "string"
        ) {
          return (d as { msg: string }).msg;
        }
        return String(d);
      })
      .filter(Boolean)
      .join("；");
    if (joined) return joined;
  }
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
      // 不 resetFields：保留请求期间的输入，留空项语义为「保持不变」
    },
    onError: (e: unknown) => message.error(errorDetail(e, "保存失败")),
  });

  const handleSave = async () => {
    let values: Record<string, unknown>;
    try {
      values = await form.validateFields();
    } catch {
      // 校验失败由 Form 就地展示错误，不触发保存
      return;
    }
    // 空值忽略：已配置项留空保持不变，未配置项留空不提交
    const payload: ThirdPartyConfigUpdateItem[] = items
      .map((item) => item.key)
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

  const groups = groupItems(items);

  return (
    <div style={{ maxWidth: 600 }}>
      <PageHeader title="第三方接口配置" />
      <Form form={form} layout="vertical">
        {groups.map((group) => (
          <Card key={group.title} title={group.title} style={{ marginBottom: 24 }}>
            {group.items.map((item) => {
              const placeholder = item.configured
                ? "已配置（留空保持不变）"
                : "未配置";
              return (
                <Form.Item
                  key={item.key}
                  name={item.key}
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
                    <Input.Password
                      placeholder={placeholder}
                      maxLength={VALUE_MAX_LENGTH}
                      autoComplete="new-password"
                    />
                  ) : (
                    <Input placeholder={placeholder} maxLength={VALUE_MAX_LENGTH} />
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
