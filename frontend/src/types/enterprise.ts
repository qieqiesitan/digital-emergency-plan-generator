export interface OrgMember {
  role: string;
  name: string;
  position: string;
  phone: string;
  responsibilities: string;
}

export interface OrgGroup {
  group_key: string;
  group_name: string;
  members: OrgMember[];
}

export interface NearbyUnit {
  name: string;
  direction: string;
  distance_m: number;
  main_risk: string;
}

export interface SensitiveTarget {
  name: string;
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
  resources_count: number;
  plans_count: number;
  created_at: string;
  updated_at: string;
}

export interface EnterpriseCreate {
  name: string;
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
