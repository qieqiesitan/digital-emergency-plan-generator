import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { DashboardData } from "@/types/dashboard";

export async function getDashboard(): Promise<DashboardData> {
  const res = await api.get<ApiResponse<DashboardData>>("/dashboard");
  return res.data.data;
}
