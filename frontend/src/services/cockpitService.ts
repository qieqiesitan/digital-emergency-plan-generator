import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { CockpitSummary } from "@/types/cockpit";

export const getCockpitSummary = (enterpriseId: string): Promise<CockpitSummary> =>
  api
    .get<ApiResponse<CockpitSummary>>(`/enterprises/${enterpriseId}/cockpit-summary`)
    .then((r) => r.data.data);
