export interface OrgMember {
  role: string;
  name: string;
  economic_type?: string | null;
  position: string;
  phone: string;
  responsibilities: string;
}

export interface OrgGroup {
  group_key: string;
  group_name: string;
  economic_type?: string | null;
  members: OrgMember[];
}

export interface NearbyUnit {
  name: string;
  economic_type?: string | null;
  direction: string;
  distance_m: number;
  main_risk: string;
}

export interface SensitiveTarget {
  name: string;
  economic_type?: string | null;
  direction: string;
  distance_m: number;
  type: string;
}

export interface SurroundingInfo {
  nearby_units: NearbyUnit[];
  sensitive_targets: SensitiveTarget[];
  traffic_info: string;
}

export interface Enterprise {
  id: string;
  name: string;
  economic_type: string | null;
  address: string;
  industry: string;
  business_scope: string;
  employee_count: number | null;
  building_overview: string | null;
  org_structure: OrgGroup[];
  surrounding_info: SurroundingInfo | null;
  floor_plan_url: string | null;
  gis_lat: number | null;
  gis_lng: number | null;
  risk_sources_count: number;
  risk_events_count: number;
  resources_count: number;
  plans_count: number;
  created_at: string;
  updated_at: string;
  // extended fields from backend
  credit_code?: string | null;
  legal_representative?: string | null;
  established_date?: string | null;
  registered_capital?: string | null;
  phone?: string | null;
  fax?: string | null;
  postal_code?: string | null;
  land_area?: number | null;
  building_area?: number | null;
  safety_officer?: string | null;
  safety_officer_phone?: string | null;
  safety_staff_count?: number | null;
  safety_standardization?: string | null;
  fire_approval?: string | null;
  fire_approval_date?: string | null;
  last_plan_filing_date?: string | null;
  last_plan_filing_authority?: string | null;
  main_products?: string | null;
  annual_capacity?: string | null;
  hazardous_chemicals?: string | null;
  special_equipment?: string | null;
}

export interface EnterpriseCreate {
  name: string;
  economic_type?: string | null;
  address?: string;
  industry?: string;
  business_scope?: string;
  employee_count?: number | null;
  building_overview?: string;
  floor_plan_url?: string | null;
  gis_lat?: number | null;
  gis_lng?: number | null;
}

export interface EnterpriseUpdate extends Partial<EnterpriseCreate> {
  floor_plan_url?: string | null;
  gis_lat?: number | null;
  gis_lng?: number | null;
}

// 楼层相关字段（四色分布图工作台；类型定义见 riskMappingWorkbench.ts）
export type { EnterpriseFloor } from "./riskMappingWorkbench";
