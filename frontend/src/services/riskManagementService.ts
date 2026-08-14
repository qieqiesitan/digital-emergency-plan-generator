import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { RiskAssessmentMethod, RiskZone, RiskZoneCreate, RiskObject, RiskObjectCreate, RiskUnit, RiskUnitCreate, RiskEvent, RiskEventCreate, RiskMeasure, RiskMeasureCreate, HierarchyZone, MethodConfig, SmartGuideZone, MigrationPreviewResponse, MigrationExecutePayload, MigrationExecuteResponse, RiskZoneFloorPlanPolygon } from "@/types/riskManagement";

const BASE = (eid: string) => `/enterprises/${eid}/risk-management`;

export const listMethods = (eid: string) => api.get<ApiResponse<RiskAssessmentMethod[]>>(`${BASE(eid)}/methods`).then(r => r.data.data);
export const getMethod = (eid: string, mid: string) => api.get<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}`).then(r => r.data.data);
export const createMethod = (eid: string, data: { method_type: string; name: string; config: MethodConfig }) => api.post<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods`, data).then(r => r.data.data);
export const updateMethod = (eid: string, mid: string, data: Partial<{ name: string; config: MethodConfig; is_active: boolean }>) => api.put<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}`, data).then(r => r.data.data);
export const deleteMethod = (eid: string, mid: string) => api.delete(`${BASE(eid)}/methods/${mid}`);
export const duplicateMethod = (eid: string, mid: string) => api.post<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}/duplicate`).then(r => r.data.data);
export interface RiskMethodPreviewPayload {
  method_id: string;
  params: Record<string, number>;
  scenario?: "inherent" | "current";
}
export interface RiskMethodPreviewResult {
  risk_level: string;
  risk_score: string;
  action: string;
  scenario?: string;
}
export interface RiskConversionReference {
  factor: number;
  reference_score: number | null;
  reference_level: string | null;
  note?: string;
}
export const previewRiskMethod = (eid: string, payload: RiskMethodPreviewPayload) =>
  api.post<ApiResponse<RiskMethodPreviewResult>>(`${BASE(eid)}/methods/preview`, payload).then(r => r.data.data);
/** 兼容旧签名：previewMethod(eid, method_id, params) */
export const previewMethod = (eid: string, method_id: string, params: Record<string, number>) =>
  previewRiskMethod(eid, { method_id, params });
export const previewRiskConversion = (eid: string, eventId: string) =>
  api.get<ApiResponse<RiskConversionReference>>(`${BASE(eid)}/events/${eventId}/conversion-reference`).then(r => r.data.data);

export const listZones = (eid: string) => api.get<ApiResponse<RiskZone[]>>(`${BASE(eid)}/zones`).then(r => r.data.data);
export const createZone = (eid: string, data: RiskZoneCreate) => api.post<ApiResponse<RiskZone>>(`${BASE(eid)}/zones`, data).then(r => r.data.data);
export const updateZone = (eid: string, zid: string, data: Partial<RiskZoneCreate>) => api.put<ApiResponse<RiskZone>>(`${BASE(eid)}/zones/${zid}`, data).then(r => r.data.data);
export const deleteZone = (eid: string, zid: string) => api.delete(`${BASE(eid)}/zones/${zid}`);

export const listObjects = (eid: string, params?: { zone_id?: string; is_risk_point?: boolean }) => api.get<ApiResponse<RiskObject[]>>(`${BASE(eid)}/objects`, { params }).then(r => r.data.data);
export const createObject = (eid: string, data: RiskObjectCreate) => api.post<ApiResponse<RiskObject>>(`${BASE(eid)}/objects`, data).then(r => r.data.data);
export const createObjectWithImage = (eid: string, formData: FormData) => api.post<ApiResponse<RiskObject>>(`${BASE(eid)}/objects`, formData, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data.data);
export const updateObject = (eid: string, oid: string, data: Partial<RiskObjectCreate>) => api.put<ApiResponse<RiskObject>>(`${BASE(eid)}/objects/${oid}`, data).then(r => r.data.data);
export const deleteObject = (eid: string, oid: string) => api.delete(`${BASE(eid)}/objects/${oid}`);

export const listUnits = (eid: string, oid: string) => api.get<ApiResponse<RiskUnit[]>>(`${BASE(eid)}/objects/${oid}/units`).then(r => r.data.data);
export const createUnit = (eid: string, oid: string, data: RiskUnitCreate) => api.post<ApiResponse<RiskUnit>>(`${BASE(eid)}/objects/${oid}/units`, data).then(r => r.data.data);
export const updateUnit = (eid: string, oid: string, uid: string, data: Partial<RiskUnitCreate>) => api.put<ApiResponse<RiskUnit>>(`${BASE(eid)}/objects/${oid}/units/${uid}`, data).then(r => r.data.data);
export const deleteUnit = (eid: string, oid: string, uid: string) => api.delete(`${BASE(eid)}/objects/${oid}/units/${uid}`);

export const createEvent = (eid: string, parentId: string, data: RiskEventCreate) => {
  const path = data.object_id && !data.unit_id ? `${BASE(eid)}/objects/${parentId}/events` : `${BASE(eid)}/units/${parentId}/events`;
  return api.post<ApiResponse<RiskEvent>>(path, data).then(r => r.data.data);
};
export const updateEvent = (eid: string, evid: string, data: Partial<RiskEventCreate>) => api.put<ApiResponse<RiskEvent>>(`${BASE(eid)}/events/${evid}`, data).then(r => r.data.data);
export const deleteEvent = (eid: string, evid: string) => api.delete(`${BASE(eid)}/events/${evid}`);
export const recalcEvent = (eid: string, evid: string) => api.post<ApiResponse<RiskEvent>>(`${BASE(eid)}/events/${evid}/recalc`).then(r => r.data.data);

export const listMeasures = (eid: string, evid: string) => api.get<ApiResponse<RiskMeasure[]>>(`${BASE(eid)}/events/${evid}/measures`).then(r => r.data.data);
export const createMeasure = (eid: string, evid: string, data: RiskMeasureCreate) => api.post<ApiResponse<RiskMeasure>>(`${BASE(eid)}/events/${evid}/measures`, data).then(r => r.data.data);
export const updateMeasure = (eid: string, evid: string, mid: string, data: Partial<RiskMeasureCreate & { status: string }>) => api.put<ApiResponse<RiskMeasure>>(`${BASE(eid)}/events/${evid}/measures/${mid}`, data).then(r => r.data.data);
export const deleteMeasure = (eid: string, evid: string, mid: string) => api.delete(`${BASE(eid)}/events/${evid}/measures/${mid}`);

export const getFullHierarchy = (eid: string, floorId?: string) =>
  api.get<ApiResponse<HierarchyZone[]>>(`${BASE(eid)}/hierarchy`, { params: floorId ? { floor_id: floorId } : {} }).then(r => r.data.data);

export const aiSuggestObjects = (eid: string, data: { zone_name: string; zone_desc: string; enterprise_info: Record<string, unknown>; existing_names: string[] }) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-objects`, data).then(r => r.data.data);
export const aiSuggestEvents = (eid: string, data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-events`, data).then(r => r.data.data);
export const aiSuggestMeasures = (eid: string, data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-measures`, data).then(r => r.data.data);
export const aiSmartGuide = (eid: string, description: string) => api.post<ApiResponse<{ hierarchy: SmartGuideZone[]; summary: Record<string, unknown> }>>(`${BASE(eid)}/ai/smart-guide`, { description }).then(r => r.data.data);
export const aiAnalyzeFloorPlan = (eid: string, enterprise_info: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/analyze-floor-plan`, { enterprise_info }).then(r => r.data.data);
export const getMigrationPreview = (eid: string) =>
  api.get<ApiResponse<MigrationPreviewResponse>>(`${BASE(eid)}/migrate/preview`).then(r => r.data.data);

export const aiMigratePreview = (eid: string) =>
  api.post<ApiResponse<MigrationPreviewResponse>>(`${BASE(eid)}/ai/migrate-preview`).then(r => r.data.data);

export const executeMigration = (eid: string, mappings: MigrationExecutePayload[]) =>
  api.post<ApiResponse<MigrationExecuteResponse>>(`${BASE(eid)}/migrate/execute`, { mappings }).then(r => r.data.data);

export const getRiskMappingOverview = (eid: string, floorId?: string) =>
  api.get<ApiResponse<import("@/types/riskMappingWorkbench").RawOverviewResponse>>(`${BASE(eid)}/overview`, { params: floorId ? { floor_id: floorId } : {} }).then(r => {
    const d = r.data.data;
    return {
      floors: [d.floor],
      currentFloorId: d.floor.id,
      zones: d.zones,
      riskPoints: d.risk_points,
      texts: d.floor.canvas_texts,
      pendingRegions: [],
    };
  });

// ── 风险分级管控清单 & 重大风险公示 ──

export interface ControlListRow {
  zone: string;
  object: string;
  unit: string;
  accident: string;
  inherent: string;
  current: string;
  control_level: string;
  measures: string;
  unit_name: string;
  person: string;
  phone: string;
}
export interface ControlListResponse {
  items: ControlListRow[];
  total: number;
}

/** 公示页四色图分区数据（后端 risk-publicity zones 字段，含双模式等级与有效色）。 */
export interface PublicityZone {
  id: string;
  floor_id: string | null;
  floor_name: string | null;
  name: string;
  floor_plan_polygon: RiskZoneFloorPlanPolygon | null;
  max_level: string | null;
  effective_color: string | null;
  inherent_max_level: string | null;
  inherent_effective_color: string | null;
}
export interface RiskPublicityResponse {
  token: string;
  enterprise_name: string;
  items: ControlListRow[];
  zones: PublicityZone[];
  generated_at: string;
}

/** 公开脱敏清单行（不含责任人/电话等敏感字段）。 */
export interface PublicRiskRow {
  zone: string;
  object: string;
  unit: string;
  accident: string;
  inherent: string;
  current: string;
  control_level: string;
  measures: string;
  unit_name: string;
}
export interface PublicRiskResponse {
  enterprise_name: string;
  items: PublicRiskRow[];
  generated_at: string;
}

export async function getControlList(enterpriseId: string, params: object) {
  return api.get<ApiResponse<ControlListResponse>>(`${BASE(enterpriseId)}/control-list`, { params });
}
export async function exportControlList(enterpriseId: string) {
  return api.get<Blob>(`${BASE(enterpriseId)}/control-list/export`, { responseType: "blob" });
}
export async function getRiskPublicity(enterpriseId: string) {
  return api.get<ApiResponse<RiskPublicityResponse>>(`${BASE(enterpriseId)}/risk-publicity`);
}
export async function resetRiskPublicityToken(enterpriseId: string) {
  return api.post<ApiResponse<{ token: string }>>(`${BASE(enterpriseId)}/risk-publicity/token`);
}
export async function fetchPublicRisk(token: string) {
  return api.get<ApiResponse<PublicRiskResponse>>(`/public/risk/${token}`);
}
