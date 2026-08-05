import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { RawWorkbenchSnapshot, RawOverviewResponse, BatchSavePayload, BatchSaveResponse, EnterpriseFloor } from "@/types/riskMappingWorkbench";

const BASE = (eid: string) => `/enterprises/${eid}/risk-management`;

export const getRiskMappingWorkbench = (eid: string, floorId?: string) =>
  api.get<ApiResponse<RawWorkbenchSnapshot>>(`${BASE(eid)}/workbench`, { params: floorId ? { floor_id: floorId } : {} }).then(r => {
    const d = r.data.data;
    return {
      floors: d.floors,
      currentFloorId: d.current_floor_id,
      zones: d.zones,
      riskPoints: d.risk_points,
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
