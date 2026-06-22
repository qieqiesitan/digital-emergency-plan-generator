import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { PlanTemplate } from "@/types/template";
import type { PlanType } from "@/types/plan";

export async function listTemplates(planType?: PlanType): Promise<PaginatedResponse<PlanTemplate>> {
  const params = planType ? { plan_type: planType } : undefined;
  const res = await api.get<PaginatedResponse<PlanTemplate>>("/templates", { params });
  return res.data;
}

export async function getTemplate(id: string): Promise<PlanTemplate> {
  const res = await api.get<ApiResponse<PlanTemplate>>(`/templates/${id}`);
  return res.data.data;
}
