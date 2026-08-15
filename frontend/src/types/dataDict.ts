/** 数据字典类型定义（与 backend/app/schemas/data_dict.py 对应）。 */

export interface DataDictItem {
  id: string;
  dict_type: string;
  code: string;
  label: string;
  value: Record<string, unknown>;
  scope: "system" | "enterprise";
  enterprise_id: string | null;
  sort_order: number;
  enabled: boolean;
  is_system: boolean;
  description?: string | null;
}

export interface DataDictPayload {
  dict_type: string;
  code: string;
  label: string;
  value: Record<string, unknown>;
  sort_order?: number;
  enabled?: boolean;
  description?: string | null;
}
