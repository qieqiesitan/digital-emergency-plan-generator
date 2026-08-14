import { computeRiskLS, computeRiskLEC } from "@/utils/riskMethodEngine";
import type { MethodType, RiskEventFormValues } from "@/types/riskManagement";

export const DIRECT_LEVELS = [
  { value: 1, label: "低" },
  { value: 2, label: "一般" },
  { value: 3, label: "较大" },
  { value: 4, label: "重大" },
];

export interface InitialParams {
  l?: number;
  s?: number;
  e?: number;
  c?: number;
  directLevel?: number;
}

export interface BuildEventPayloadOptions {
  isEdit: boolean;
  initialValues?: RiskEventFormValues;
  methodType: MethodType;
  initialParams?: InitialParams | null;
  initialInherentParams: Record<string, number>;
  adoptedRef?: { level: string; score: string } | null;
  adoptedInherent?: { level: string; score: string } | null;
  lValue: number;
  sValue: number;
  lecL: number;
  lecE: number;
  lecC: number;
  inherentL: number;
  inherentS: number;
  inherentLecL: number;
  inherentLecE: number;
  inherentLecC: number;
}

// 构建风险事件 create/update payload（纯函数）。
// 规则：
// - 编辑模式方法未改动时不提交 method_type/method_params，避免后端按（空/旧）参数重算覆盖已存等级；
// - 固有风险：编辑未改动对应参数则保持已存等级（不携带键），DIRECT 显式清空以 null 透传；
// - 现有风险：参数未改动且采用折算参考时显式携带 risk_level/risk_score，其余场景省略由后端重算；
// - AI 建议采用（adoptedInherent）：DIRECT 无条件携带建议固有等级/分值（覆盖既有）；
//   LS/LEC/COAL_LS 仅在固有参数未改动（未携带计算值）时透传，改参数后以重算为准；
// - 新建/参数改动时 method_params 使用小写键（l/s/e/c），DIRECT 使用 risk_level 文案键（与后端一致）。
export function buildEventPayload(
  values: RiskEventFormValues,
  opts: BuildEventPayloadOptions,
): RiskEventFormValues {
  const {
    isEdit, initialValues, methodType, initialParams, initialInherentParams, adoptedRef, adoptedInherent,
    lValue, sValue, lecL, lecE, lecC,
    inherentL, inherentS, inherentLecL, inherentLecE, inherentLecC,
  } = opts;

  const payload: RiskEventFormValues = {
    ...values,
    accident_type: Array.isArray(values.accident_type)
      ? values.accident_type.join("、")
      : values.accident_type,
    control_level: values.control_level ?? null,
  };

  const methodUnchanged = isEdit
    && methodType === (initialValues?.method_type as MethodType | undefined);
  if (methodUnchanged) {
    delete payload.method_type;
    delete payload.method_params;
  } else {
    payload.method_type = methodType;
  }

  // ── 固有风险：编辑模式未改动对应参数则保持已存等级，不重算不覆盖 ──
  if (methodType === "DIRECT") {
    const inherentLevel = values.inherent_risk_level ?? null;
    const inherentUnchanged = isEdit
      && inherentLevel === (initialValues?.inherent_risk_level ?? null);
    if (!inherentUnchanged) {
      // null 显式清空透传，undefined 序列化省略
      payload.inherent_risk_level = inherentLevel;
    } else {
      delete payload.inherent_risk_level;
      delete payload.inherent_risk_score;
    }
  } else if (methodType === "LS" || methodType === "COAL_LS") {
    payload.inherent_params = { L: inherentL, S: inherentS };
    const inherentUnchanged = isEdit
      && (initialInherentParams.L ?? 1) === inherentL
      && (initialInherentParams.S ?? 1) === inherentS;
    if (inherentUnchanged) {
      delete payload.inherent_risk_level;
      delete payload.inherent_risk_score;
    } else {
      const ir = computeRiskLS(inherentL, inherentS);
      payload.inherent_risk_level = ir.riskLevel;
      payload.inherent_risk_score = ir.riskScore;
    }
  } else {
    payload.inherent_params = { L: inherentLecL, E: inherentLecE, C: inherentLecC };
    const inherentUnchanged = isEdit
      && (initialInherentParams.L ?? 1) === inherentLecL
      && (initialInherentParams.E ?? 3) === inherentLecE
      && (initialInherentParams.C ?? 7) === inherentLecC;
    if (inherentUnchanged) {
      delete payload.inherent_risk_level;
      delete payload.inherent_risk_score;
    } else {
      const ir = computeRiskLEC(inherentLecL, inherentLecE, inherentLecC);
      payload.inherent_risk_level = ir.riskLevel;
      payload.inherent_risk_score = ir.riskScore;
    }
  }

  // ── AI 建议采用：固有等级/分值显式携带 ──
  if (adoptedInherent) {
    if (methodType === "DIRECT") {
      // DIRECT 无条件以建议值覆盖（含既存等级），并显式携带分值
      payload.inherent_risk_level = adoptedInherent.level;
      payload.inherent_risk_score = adoptedInherent.score;
    } else if (payload.inherent_risk_level == null) {
      // LS/LEC/COAL_LS：固有参数未改动（未携带计算值）时透传建议值；
      // 用户改动固有参数后 payload 已有计算值，以计算值优先
      payload.inherent_risk_level = adoptedInherent.level;
      payload.inherent_risk_score = adoptedInherent.score;
    }
  }

  // ── 现有风险：编辑模式未改动则不提交，保持后端已存等级；改动/新建才重算提交 ──
  if (methodType === "LS" || methodType === "COAL_LS") {
    const params = { l: lValue, s: sValue };
    const paramsUnchanged = methodUnchanged
      && (initialParams?.l ?? 1) === lValue
      && (initialParams?.s ?? 1) === sValue;
    if (adoptedRef && paramsUnchanged) {
      // 采用折算参考：显式提交等级/分值，后端不按参数重算
      payload.method_params = params;
      payload.risk_level = adoptedRef.level;
      payload.risk_score = adoptedRef.score;
    } else {
      if (!paramsUnchanged) {
        payload.method_params = params;
      }
      delete payload.risk_level;
      delete payload.risk_score;
    }
  } else if (methodType === "LEC") {
    const params = { l: lecL, e: lecE, c: lecC };
    const paramsUnchanged = methodUnchanged
      && (initialParams?.l ?? 1) === lecL
      && (initialParams?.e ?? 3) === lecE
      && (initialParams?.c ?? 7) === lecC;
    if (adoptedRef && paramsUnchanged) {
      payload.method_params = params;
      payload.risk_level = adoptedRef.level;
      payload.risk_score = adoptedRef.score;
    } else {
      if (!paramsUnchanged) {
        payload.method_params = params;
      }
      delete payload.risk_level;
      delete payload.risk_score;
    }
  } else if (methodType === "DIRECT") {
    const lv = values.method_params?.level ?? 1;
    const label = DIRECT_LEVELS.find((d) => d.value === lv)?.label ?? "一般";
    const directUnchanged = methodUnchanged && (initialParams?.directLevel ?? 1) === lv;
    if (adoptedRef && label === adoptedRef.level) {
      payload.method_params = { risk_level: label } as unknown as Record<string, number>;
      payload.risk_level = adoptedRef.level;
      payload.risk_score = adoptedRef.score;
    } else {
      if (!directUnchanged) {
        // 与后端 compute_risk DIRECT 一致：等级文案存于 method_params.risk_level
        payload.method_params = { risk_level: label } as unknown as Record<string, number>;
      } else {
        // 未改动且未采用折算参考：不提交 method_params，保持后端已存等级
        delete payload.method_params;
      }
      delete payload.risk_level;
      delete payload.risk_score;
    }
  }

  return payload;
}
