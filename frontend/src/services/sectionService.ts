import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { PlanSection, SectionUpdate } from "@/types/plan";

export async function listSections(planId: string): Promise<PlanSection[]> {
  const res = await api.get<ApiResponse<PlanSection[]>>(`/plans/${planId}/sections`);
  return res.data.data;
}

export async function getSection(planId: string, sectionKey: string): Promise<PlanSection> {
  const res = await api.get<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}`);
  return res.data.data;
}

export async function updateSection(planId: string, sectionKey: string, data: SectionUpdate): Promise<PlanSection> {
  const res = await api.put<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}`, data);
  return res.data.data;
}
