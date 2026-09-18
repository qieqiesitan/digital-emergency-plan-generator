import api from "./api";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import type { ApiResponse } from "@/types/common";
import { filenameFromContentDisposition } from "@/utils/download";
import type {
  ChemicalDefinition,
  CriticalQuantity,
  DesignMaxSuggestion,
  EvidenceItem,
  LedgerChemical,
  LinkableRiskObject,
  MajorHazardCalculation,
  MajorHazardPreviewResult,
  MajorHazardRecord,
  MajorHazardUnit,
  MajorHazardUnitChemical,
  MajorHazardUnitChemicalPayload,
  MajorHazardUnitPolygon,
  MajorHazardUnitPayload,
} from "@/types/majorHazard";

// api.ts 的 baseURL 已含 /api/v1，故此处只写业务路径
const BASE = "/major-hazard";

// --- 常量查询 ---
export const listCriticalQuantities = (keyword?: string) =>
  api
    .get<ApiResponse<CriticalQuantity[]>>(`${BASE}/definitions/critical-quantities`, {
      params: { keyword, limit: 30 },
    })
    .then((r) => r.data.data);

// --- 单元 ---
/**
 * 按品种名查标准值（Q 与 β）。
 *
 * β 查不到时（表3 未命中）返回 needs_hazard_symbol=true 与表4 的类别清单，
 * 前端让用户选类别后再调一次本函数并传 hazard_symbol。
 */
export const lookupChemical = (name: string, hazardSymbol?: string) =>
  api
    .get<ApiResponse<ChemicalDefinition>>(`${BASE}/definitions/lookup`, {
      params: { name, hazard_symbol: hazardSymbol },
    })
    .then((r) => r.data.data);

export const listUnits = (enterpriseId: string) =>
  api
    .get<ApiResponse<MajorHazardUnit[]>>(`${BASE}/units`, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

export const createUnit = (
  enterpriseId: string,
  payload: MajorHazardUnitPayload,
  config?: AxiosRequestConfig,
) =>
  api
    .post<ApiResponse<MajorHazardUnit>>(`${BASE}/units`, payload, {
      params: { enterprise_id: enterpriseId },
      ...config,
    })
    .then((r) => r.data.data);

export const updateUnit = (unitId: string, payload: MajorHazardUnitPayload) =>
  api
    .put<ApiResponse<MajorHazardUnit>>(`${BASE}/units/${unitId}`, payload)
    .then((r) => r.data.data);

export const deleteUnit = (unitId: string) => api.delete(`${BASE}/units/${unitId}`);

/** 保存单元在平面图上的落点。floor_id 与 polygon 必须成对（同时给或同时清空）。 */
export const setUnitPolygon = (
  unitId: string,
  payload: { floor_id: string | null; polygon: MajorHazardUnitPolygon | null },
) =>
  api
    .put<ApiResponse<{ unit_id: string; floor_id: string | null }>>(
      `${BASE}/units/${unitId}/polygon`,
      payload,
    )
    .then((r) => r.data.data);

// --- 跨模块关联（计划 7） ---
/** 本企业可关联的风险点（`is_risk_point=true`）。 */
export const listLinkableRiskObjects = (enterpriseId: string) =>
  api
    .get<ApiResponse<LinkableRiskObject[]>>(`${BASE}/linkable/risk-objects`, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

/** 关联/解除风险点；传 null 表示解除。后端做同企业校验。 */
export const linkRiskObject = (unitId: string, riskObjectId: string | null) =>
  api
    .put<ApiResponse<{ unit_id: string; risk_object_id: string | null }>>(
      `${BASE}/units/${unitId}/risk-object`,
      { risk_object_id: riskObjectId },
    )
    .then((r) => r.data.data);

/** 本企业危化品台账条目（供单元品种关联）。 */
export const listLedgerChemicals = (enterpriseId: string) =>
  api
    .get<ApiResponse<LedgerChemical[]>>(`${BASE}/ledger/chemicals`, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

/** 取设计最大量建议初值。只读，不写库——落库要等用户在界面上确认后保存。 */
export const suggestDesignMaxFromLedger = (chemicalId: string, enterpriseId: string) =>
  api
    .get<ApiResponse<DesignMaxSuggestion>>(
      `${BASE}/ledger/chemicals/${chemicalId}/suggest-design-max`,
      { params: { enterprise_id: enterpriseId } },
    )
    .then((r) => r.data.data);

// --- 单元品种 ---
export const listUnitChemicals = (unitId: string) =>
  api
    .get<ApiResponse<MajorHazardUnitChemical[]>>(`${BASE}/units/${unitId}/chemicals`)
    .then((r) => r.data.data);

export const replaceUnitChemicals = (
  unitId: string,
  payload: MajorHazardUnitChemicalPayload[],
) =>
  api
    .put<ApiResponse<{ unit_id: string; count: number }>>(
      `${BASE}/units/${unitId}/chemicals`,
      payload,
    )
    .then((r) => r.data.data);

// --- 计算 ---
/** 实时预览：只算不写快照。调用方需自行防抖。 */
export const previewCalculation = (unitId: string, exposedPopulation: number) =>
  api
    .post<ApiResponse<MajorHazardPreviewResult>>(`${BASE}/units/${unitId}/preview`, {
      exposed_population: exposedPopulation,
    })
    .then((r) => r.data.data);

/** 固化：写一条不可变快照。 */
export const computeCalculation = (unitId: string, exposedPopulation: number) =>
  api
    .post<ApiResponse<MajorHazardPreviewResult>>(`${BASE}/units/${unitId}/compute`, {
      exposed_population: exposedPopulation,
    })
    .then((r) => r.data.data);

export const listCalculations = (unitId: string) =>
  api
    .get<ApiResponse<MajorHazardCalculation[]>>(`${BASE}/units/${unitId}/calculations`)
    .then((r) => r.data.data);

// --- 档案 ---
/** 取档案。后端 404 表示"尚未建档"，不是错误，故关掉全局 toast 由页面处理。 */
export const getUnitRecord = (unitId: string) =>
  api
    .get<ApiResponse<MajorHazardRecord>>(`${BASE}/units/${unitId}/record`, {
      skipGlobalError: true,
    })
    .then((r) => r.data.data);

export const upsertUnitRecord = (
  unitId: string,
  enterpriseId: string,
  payload: Partial<MajorHazardRecord>,
) =>
  api
    .put<ApiResponse<MajorHazardRecord>>(`${BASE}/units/${unitId}/record`, payload, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

// --- 依据 ---
export const listUnitEvidence = (unitId: string) =>
  api
    .get<ApiResponse<EvidenceItem[]>>(`${BASE}/units/${unitId}/evidence`)
    .then((r) => r.data.data);

export const attachUnitEvidence = (
  unitId: string,
  items: Array<{
    article_anchor: string;
    regulation_id?: string;
    relation?: string;
    note?: string;
  }>,
) =>
  api
    .post<ApiResponse<{ created: number }>>(`${BASE}/units/${unitId}/evidence`, items)
    .then((r) => r.data.data);

// --- 报告导出 ---
/**
 * responseType=blob 时后端返回的错误体也是 Blob，先把里面的 detail 读出来。
 * 读不到就退回通用话术，不要把 "[object Blob]" 抛给用户。
 */
async function blobErrorDetail(err: unknown): Promise<string> {
  const data = (err as { response?: { data?: unknown } })?.response?.data;
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      return parsed?.detail || parsed?.message || "报告导出失败";
    } catch {
      return "报告导出失败";
    }
  }
  const message = (err as { detail?: string; message?: string })?.detail
    || (err as { message?: string })?.message;
  return message || "报告导出失败";
}

/**
 * 下载辨识报告 DOCX。走 blob 避免文件名被 URL 编码破坏，同时复用 axios 的鉴权头。
 *
 * 后端在"尚未固化计算结果"时返回 422，故开 skipGlobalError 由调用方自己提示。
 */
export const downloadUnitReport = async (
  unitId: string,
  fallbackName = "重大危险源辨识报告",
): Promise<void> => {
  let resp: AxiosResponse<Blob>;
  try {
    resp = await api.get<Blob>(`${BASE}/units/${unitId}/report.docx`, {
      responseType: "blob",
      skipGlobalError: true,
    });
  } catch (err) {
    throw new Error(await blobErrorDetail(err), { cause: err });
  }
  const name = filenameFromContentDisposition(
    String(resp.headers?.["content-disposition"] ?? ""),
    `${fallbackName}.docx`,
  );
  const url = URL.createObjectURL(resp.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};
