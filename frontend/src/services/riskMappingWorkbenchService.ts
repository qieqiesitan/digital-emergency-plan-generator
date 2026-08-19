import api from "./api";
import type { ApiResponse } from "@/types/common";
import type {
  RawWorkbenchSnapshot,
  BatchSavePayload,
  BatchSaveResponse,
  EnterpriseFloor,
  FourColorAnalyzeResult,
  FourColorCommitPayload,
  FourColorCommitResult,
} from "@/types/riskMappingWorkbench";

const BASE = (eid: string) => `/enterprises/${eid}/risk-management`;

export const getRiskMappingWorkbench = (eid: string, floorId?: string) =>
  api.get<ApiResponse<RawWorkbenchSnapshot>>(`${BASE(eid)}/workbench`, { params: floorId ? { floor_id: floorId } : {} }).then(r => {
    const d = r.data.data;
    const zoneRiskPoints = d.zones.flatMap(z =>
      (z.objects || [])
        .filter(obj => obj.is_risk_point)
        .map(obj => ({
          ...obj,
          floor_id: obj.floor_id ?? z.floor_id,
          location_x: obj.location_x ?? 50,
          location_y: obj.location_y ?? 50,
        })),
    );
    const seen = new Set(d.risk_points.map(p => p.id));
    const riskPoints = [
      ...d.risk_points,
      ...zoneRiskPoints.filter(p => !seen.has(p.id)),
    ];
    return {
      floors: d.floors,
      currentFloorId: d.current_floor_id,
      zones: d.zones,
      riskPoints,
      texts: d.texts,
      pendingRegions: d.pending_regions ?? [],
    };
  });

export const saveRiskMappingWorkbench = (eid: string, payload: BatchSavePayload) =>
  api.post<ApiResponse<BatchSaveResponse>>(`${BASE(eid)}/workbench/batch-save`, payload).then(r => r.data.data);

export const listEnterpriseFloors = (eid: string) =>
  api.get<ApiResponse<EnterpriseFloor[]>>(`${BASE(eid)}/floors`).then(r => r.data.data);

export const createEnterpriseFloor = (eid: string, data: Partial<EnterpriseFloor>) =>
  api.post<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors`, data).then(r => r.data.data);

export const updateEnterpriseFloor = (eid: string, floorId: string, data: Partial<EnterpriseFloor>) =>
  api.put<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors/${floorId}`, data).then(r => r.data.data);

export const deleteEnterpriseFloor = (eid: string, floorId: string) =>
  api.delete(`${BASE(eid)}/floors/${floorId}`);

export const uploadEnterpriseFloorPlan = (eid: string, floorId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors/${floorId}/plan`, form).then(r => r.data.data);
};

export const deleteEnterpriseFloorPlan = (eid: string, floorId: string) =>
  api.delete<ApiResponse<EnterpriseFloor>>(`${BASE(eid)}/floors/${floorId}/plan`).then(r => r.data.data);

export const analyzeFourColorMap = (eid: string, floorId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api
    .post<ApiResponse<FourColorAnalyzeResult>>(`${BASE(eid)}/floors/${floorId}/four-color/analyze`, form)
    .then(r => r.data.data);
};

export const commitFourColorImport = (eid: string, floorId: string, payload: FourColorCommitPayload) =>
  api
    .post<ApiResponse<FourColorCommitResult>>(`${BASE(eid)}/floors/${floorId}/four-color/commit`, payload)
    .then(r => r.data.data);

export const cancelFourColorImport = (eid: string, floorId: string, token: string) =>
  api.delete(`${BASE(eid)}/floors/${floorId}/four-color/${token}`);
