import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { ApiResponse } from "@/types/common";
import type { EmergencyUnit } from "@/types/emergencyOrg";

/** 读取应急组织整树（平铺单元，靠 parent_id 组树）。 */
export const getEmergencyOrg = (enterpriseId: string) =>
  api
    .get<ApiResponse<EmergencyUnit[]>>(`/enterprises/${enterpriseId}/emergency-org`)
    .then(r => r.data.data);

/** 整树覆盖保存应急组织（字段名 units，与后端 EmergencyOrgUpdate 一致）。 */
export const saveEmergencyOrg = (
  enterpriseId: string,
  units: EmergencyUnit[],
  config?: AxiosRequestConfig,
) => {
  const req = config
    ? api.put<ApiResponse<EmergencyUnit[]>>(
        `/enterprises/${enterpriseId}/emergency-org`,
        { units },
        config,
      )
    : api.put<ApiResponse<EmergencyUnit[]>>(`/enterprises/${enterpriseId}/emergency-org`, {
        units,
      });
  return req.then(r => r.data.data);
};
