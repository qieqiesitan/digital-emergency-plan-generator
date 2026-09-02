import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getThirdPartyConfig,
  updateThirdPartyConfig,
} from "./thirdPartyConfigService";
import type { ThirdPartyConfigItem } from "./thirdPartyConfigService";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), put: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

const ITEMS: ThirdPartyConfigItem[] = [
  {
    key: "third_party.qcc.api_key",
    label: "企查查主 Key",
    configured: true,
    masked_value: "abc***xyz",
    type: "secret",
    description: "企查查企业工商信息查询主密钥",
  },
  {
    key: "third_party.qcc.endpoint",
    label: "企查查 Endpoint",
    configured: false,
    masked_value: "",
    type: "string",
    description: "企查查 API 服务地址",
  },
];

describe("thirdPartyConfigService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("getThirdPartyConfig 请求 GET /system/third-party-config 并解包返回列表", async () => {
    apiMock.get.mockResolvedValue({
      data: { code: 0, message: "ok", data: ITEMS },
    });

    const result = await getThirdPartyConfig();

    expect(apiMock.get).toHaveBeenCalledWith("/system/third-party-config");
    expect(result).toEqual(ITEMS);
  });

  it("updateThirdPartyConfig PUT /system/third-party-config 携带完整 body 并返回更新 key 列表", async () => {
    const payload = [
      { key: "third_party.qcc.api_key", value: "new-key" },
      { key: "third_party.protego.callback_url", value: "https://example.com/callback" },
    ];
    apiMock.put.mockResolvedValue({
      data: { code: 0, message: "ok", data: payload.map((item) => item.key) },
    });

    const result = await updateThirdPartyConfig(payload);

    expect(apiMock.put).toHaveBeenCalledWith("/system/third-party-config", payload, { skipGlobalError: true });
    expect(result).toEqual([
      "third_party.qcc.api_key",
      "third_party.protego.callback_url",
    ]);
  });
});
