import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { PlanVersion, PlanVersionDetail, VersionCompare } from "@/types/version";

export async function listVersions(planId: string): Promise<PlanVersion[]> {
  const res = await api.get<ApiResponse<PlanVersion[]>>(`/plans/${planId}/versions`);
  return res.data.data;
}

export async function getVersion(planId: string, versionId: string): Promise<PlanVersionDetail> {
  const res = await api.get<ApiResponse<PlanVersionDetail>>(`/plans/${planId}/versions/${versionId}`);
  return res.data.data;
}

export async function createVersion(planId: string, description?: string): Promise<PlanVersion> {
  const res = await api.post<ApiResponse<PlanVersion>>(`/plans/${planId}/versions`, { description });
  return res.data.data;
}

export async function compareVersions(planId: string, versionA: number, versionB: number): Promise<VersionCompare> {
  const res = await api.get<ApiResponse<VersionCompare>>(`/plans/${planId}/versions/compare`, {
    params: { a: versionA, b: versionB },
  });
  return res.data.data;
}

export async function rollbackVersion(planId: string, versionId: string): Promise<void> {
  await api.post(`/plans/${planId}/versions/${versionId}/rollback`);
}
