import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { ApiResponse } from "@/types/common";
import type {
  ChemicalDefinition,
  CriticalQuantity,
  EvidenceItem,
  MajorHazardCalculation,
  MajorHazardPreviewResult,
  MajorHazardRecord,
  MajorHazardUnit,
  MajorHazardUnitChemical,
  MajorHazardUnitChemicalPayload,
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
