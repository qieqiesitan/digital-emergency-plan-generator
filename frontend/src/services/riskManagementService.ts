import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { RiskAssessmentMethod, RiskZone, RiskZoneCreate, RiskObject, RiskObjectCreate, RiskUnit, RiskUnitCreate, RiskEvent, RiskEventCreate, RiskMeasure, RiskMeasureCreate, HierarchyZone, MethodConfig } from "@/types/riskManagement";

const BASE = (eid: string) => `/enterprises/${eid}/risk-management`;

export const listMethods = (eid: string) => api.get<ApiResponse<RiskAssessmentMethod[]>>(`${BASE(eid)}/methods`).then(r => r.data.data);
export const getMethod = (eid: string, mid: string) => api.get<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}`).then(r => r.data.data);
export const createMethod = (eid: string, data: { method_type: string; name: string; config: MethodConfig }) => api.post<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods`, data).then(r => r.data.data);
export const updateMethod = (eid: string, mid: string, data: Partial<{ name: string; config: MethodConfig; is_active: boolean }>) => api.put<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}`, data).then(r => r.data.data);
export const deleteMethod = (eid: string, mid: string) => api.delete(`${BASE(eid)}/methods/${mid}`);
export const duplicateMethod = (eid: string, mid: string) => api.post<ApiResponse<RiskAssessmentMethod>>(`${BASE(eid)}/methods/${mid}/duplicate`).then(r => r.data.data);
export const previewMethod = (eid: string, method_id: string, params: Record<string, number>) => api.post<ApiResponse<{risk_level:string;risk_score:string;action:string}>>(`${BASE(eid)}/methods/preview`, { method_id, params }).then(r => r.data.data);

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

export const createEvent = (eid: string, uid: string, data: RiskEventCreate) => api.post<ApiResponse<RiskEvent>>(`${BASE(eid)}/units/${uid}/events`, data).then(r => r.data.data);
export const updateEvent = (eid: string, evid: string, data: Partial<RiskEventCreate>) => api.put<ApiResponse<RiskEvent>>(`${BASE(eid)}/events/${evid}`, data).then(r => r.data.data);
export const deleteEvent = (eid: string, evid: string) => api.delete(`${BASE(eid)}/events/${evid}`);
export const recalcEvent = (eid: string, evid: string) => api.post<ApiResponse<RiskEvent>>(`${BASE(eid)}/events/${evid}/recalc`).then(r => r.data.data);

export const listMeasures = (eid: string, evid: string) => api.get<ApiResponse<RiskMeasure[]>>(`${BASE(eid)}/events/${evid}/measures`).then(r => r.data.data);
export const createMeasure = (eid: string, evid: string, data: RiskMeasureCreate) => api.post<ApiResponse<RiskMeasure>>(`${BASE(eid)}/events/${evid}/measures`, data).then(r => r.data.data);
export const updateMeasure = (eid: string, evid: string, mid: string, data: Partial<RiskMeasureCreate & { status: string }>) => api.put<ApiResponse<RiskMeasure>>(`${BASE(eid)}/events/${evid}/measures/${mid}`, data).then(r => r.data.data);
export const deleteMeasure = (eid: string, evid: string, mid: string) => api.delete(`${BASE(eid)}/events/${evid}/measures/${mid}`);

export const getFullHierarchy = (eid: string) => api.get<ApiResponse<HierarchyZone[]>>(`${BASE(eid)}/hierarchy`).then(r => r.data.data);

export const aiSuggestObjects = (eid: string, data: { zone_name: string; zone_desc: string; enterprise_info: Record<string, unknown>; existing_names: string[] }) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-objects`, data).then(r => r.data.data);
export const aiSuggestEvents = (eid: string, data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-events`, data).then(r => r.data.data);
export const aiSuggestMeasures = (eid: string, data: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/suggest-measures`, data).then(r => r.data.data);
export const aiSmartGuide = (eid: string, description: string) => api.post<ApiResponse<{ hierarchy: HierarchyZone[]; summary: Record<string, unknown> }>>(`${BASE(eid)}/ai/smart-guide`, { description }).then(r => r.data.data);
export const aiAnalyzeFloorPlan = (eid: string, enterprise_info: Record<string, unknown>) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/analyze-floor-plan`, { enterprise_info }).then(r => r.data.data);
export const aiMigratePreview = (eid: string) => api.post<ApiResponse<Record<string, unknown>[]>>(`${BASE(eid)}/ai/migrate-preview`).then(r => r.data.data);
