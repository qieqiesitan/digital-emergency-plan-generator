import { describe, it, expect } from "vitest";
import { buildEventPayload, type BuildEventPayloadOptions } from "./eventPayload";
import type { RiskEventFormValues } from "@/types/riskManagement";

const baseOpts: BuildEventPayloadOptions = {
  isEdit: false,
  methodType: "LS",
  initialInherentParams: {},
  lValue: 4,
  sValue: 5,
  lecL: 1,
  lecE: 3,
  lecC: 7,
  inherentL: 4,
  inherentS: 5,
  inherentLecL: 1,
  inherentLecE: 3,
  inherentLecC: 7,
};

describe("buildEventPayload", () => {
  it("新建 LS 携带 method_params 小写键并计算固有等级", () => {
    const payload = buildEventPayload(
      { accident_type: ["火灾"], method_type: "LS" },
      baseOpts,
    );

    expect(payload.accident_type).toBe("火灾");
    expect(payload.method_type).toBe("LS");
    expect(payload.method_params).toEqual({ l: 4, s: 5 });
    expect(payload.inherent_params).toEqual({ L: 4, S: 5 });
    expect(payload.inherent_risk_level).toBe("重大");
    expect(payload.inherent_risk_score).toBe("R=20");
    // 新建不携带显式现有等级，由后端按配置重算
    expect(payload).not.toHaveProperty("risk_level");
    expect(payload).not.toHaveProperty("risk_score");
  });

  it("编辑 LS 未改动省略 method_type/method_params/risk_level/inherent_*", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "LS",
      method_params: { l: 4, s: 5 },
      risk_level: "重大",
      risk_score: "R=20",
      inherent_params: { L: 4, S: 5 },
      inherent_risk_level: "重大",
      inherent_risk_score: "R=20",
    };
    const payload = buildEventPayload(
      { accident_type: "火灾", method_type: "LS" },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        initialParams: { l: 4, s: 5 },
        initialInherentParams: { L: 4, S: 5 },
        lValue: 4,
        sValue: 5,
        inherentL: 4,
        inherentS: 5,
      },
    );

    expect(payload).not.toHaveProperty("method_type");
    expect(payload).not.toHaveProperty("method_params");
    expect(payload).not.toHaveProperty("risk_level");
    expect(payload).not.toHaveProperty("risk_score");
    expect(payload).not.toHaveProperty("inherent_risk_level");
    expect(payload).not.toHaveProperty("inherent_risk_score");
    expect(payload.accident_type).toBe("火灾");
  });

  it("编辑 DIRECT 未改动省略 method_params（不再携带 {level}）", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "DIRECT",
      method_params: { risk_level: "重大" } as unknown as Record<string, number>,
      risk_level: "重大",
      inherent_risk_level: "重大",
    };
    const payload = buildEventPayload(
      {
        accident_type: "火灾",
        method_type: "DIRECT",
        method_params: { level: 4 },
        inherent_risk_level: "重大",
      },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        methodType: "DIRECT",
        initialParams: { directLevel: 4 },
      },
    );

    expect(payload).not.toHaveProperty("method_type");
    expect(payload).not.toHaveProperty("method_params");
    expect(payload).not.toHaveProperty("risk_level");
    expect(payload).not.toHaveProperty("inherent_risk_level");
  });

  it("采用折算参考时携带 risk_level/risk_score 且保留小写键参数", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "LS",
      method_params: { l: 4, s: 5 },
      risk_level: "重大",
      risk_score: "R=20",
    };
    const payload = buildEventPayload(
      { accident_type: "火灾", method_type: "LS" },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        initialParams: { l: 4, s: 5 },
        adoptedRef: { level: "一般", score: "R=10" },
        lValue: 4,
        sValue: 5,
      },
    );

    expect(payload.method_params).toEqual({ l: 4, s: 5 });
    expect(payload.risk_level).toBe("一般");
    expect(payload.risk_score).toBe("R=10");
  });

  it("采用 AI 建议：DIRECT 无条件以建议固有等级/分值覆盖（既有等级已改动也覆盖）", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "DIRECT",
      method_params: { risk_level: "重大" } as unknown as Record<string, number>,
      risk_level: "重大",
      inherent_risk_level: "重大",
    };
    const payload = buildEventPayload(
      {
        accident_type: "火灾",
        method_type: "DIRECT",
        method_params: { level: 4 },
        inherent_risk_level: "较大",
      },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        methodType: "DIRECT",
        initialParams: { directLevel: 4 },
        adoptedInherent: { level: "一般", score: "-" },
      },
    );

    expect(payload.inherent_risk_level).toBe("一般");
    expect(payload.inherent_risk_score).toBe("-");
  });

  it("采用 AI 建议：DIRECT 固有等级未改动时也显式携带建议等级/分值", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "DIRECT",
      method_params: { risk_level: "重大" } as unknown as Record<string, number>,
      risk_level: "重大",
      inherent_risk_level: "重大",
    };
    const payload = buildEventPayload(
      {
        accident_type: "火灾",
        method_type: "DIRECT",
        method_params: { level: 4 },
        inherent_risk_level: "重大",
      },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        methodType: "DIRECT",
        initialParams: { directLevel: 4 },
        adoptedInherent: { level: "低", score: "-" },
      },
    );

    expect(payload.inherent_risk_level).toBe("低");
    expect(payload.inherent_risk_score).toBe("-");
  });

  it("采用 AI 建议：LS 固有参数未改动时透传建议固有等级/分值", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "LS",
      method_params: { l: 4, s: 5 },
      risk_level: "重大",
      risk_score: "R=20",
      inherent_params: { L: 4, S: 5 },
      inherent_risk_level: "重大",
      inherent_risk_score: "R=20",
    };
    const payload = buildEventPayload(
      { accident_type: "火灾", method_type: "LS" },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        initialParams: { l: 4, s: 5 },
        initialInherentParams: { L: 4, S: 5 },
        lValue: 4,
        sValue: 5,
        inherentL: 4,
        inherentS: 5,
        adoptedInherent: { level: "一般", score: "R=10" },
      },
    );

    expect(payload.inherent_risk_level).toBe("一般");
    expect(payload.inherent_risk_score).toBe("R=10");
  });

  it("采用 AI 建议：LS 固有参数改动后以重算等级/分值优先（不透传建议值）", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "LS",
      method_params: { l: 4, s: 5 },
      risk_level: "重大",
      risk_score: "R=20",
      inherent_params: { L: 4, S: 5 },
      inherent_risk_level: "重大",
      inherent_risk_score: "R=20",
    };
    const payload = buildEventPayload(
      { accident_type: "火灾", method_type: "LS" },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        initialParams: { l: 4, s: 5 },
        initialInherentParams: { L: 4, S: 5 },
        lValue: 4,
        sValue: 5,
        inherentL: 1,
        inherentS: 1,
        adoptedInherent: { level: "重大", score: "R=20" },
      },
    );

    expect(payload.inherent_params).toEqual({ L: 1, S: 1 });
    expect(payload.inherent_risk_level).toBe("低");
    expect(payload.inherent_risk_score).toBe("R=1");
  });

  it("DIRECT 固有等级显式清空时透传 null", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "DIRECT",
      method_params: { risk_level: "重大" } as unknown as Record<string, number>,
      risk_level: "重大",
      inherent_risk_level: "重大",
    };
    const payload = buildEventPayload(
      {
        accident_type: "火灾",
        method_type: "DIRECT",
        method_params: { level: 4 },
        inherent_risk_level: null,
      },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        methodType: "DIRECT",
        initialParams: { directLevel: 4 },
      },
    );

    expect(payload.inherent_risk_level).toBeNull();
  });

  it("DIRECT 固有等级未改动时不含 inherent_risk_level 键", () => {
    const initialValues: RiskEventFormValues = {
      accident_type: "火灾",
      method_type: "DIRECT",
      method_params: { risk_level: "重大" } as unknown as Record<string, number>,
      risk_level: "重大",
      inherent_risk_level: "重大",
    };
    const payload = buildEventPayload(
      {
        accident_type: "火灾",
        method_type: "DIRECT",
        method_params: { level: 4 },
        inherent_risk_level: "重大",
      },
      {
        ...baseOpts,
        isEdit: true,
        initialValues,
        methodType: "DIRECT",
        initialParams: { directLevel: 4 },
      },
    );

    expect(payload).not.toHaveProperty("inherent_risk_level");
    expect(payload).not.toHaveProperty("inherent_risk_score");
  });
});
