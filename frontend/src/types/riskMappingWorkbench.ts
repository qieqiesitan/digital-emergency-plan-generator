export type RiskLevel = "重大" | "较大" | "一般" | "低" | "未评估";
export type ColorSource = "auto" | "manual";

export interface RiskPolygonPoint { x: number; y: number }
export interface RiskPolygon { id: string; label?: string; points: RiskPolygonPoint[] }
export interface RiskZoneFloorPlanPolygon {
  version: 2;
  color_source: ColorSource;
  color: string | null;
  polygons: RiskPolygon[];
}
export interface RiskCanvasText {
  id: string;
  content: string;
  x: number;
  y: number;
  font_size: number;
  color: string;
  rotation: number;
  sort_order: number;
}
export interface EnterpriseFloor {
  id: string;
  enterprise_id: string;
  name: string;
  sort_order: number;
  floor_plan_url: string | null;
  description?: string | null;
  canvas_width?: number | null;
  canvas_height?: number | null;
  canvas_texts: RiskCanvasText[];
  is_default: boolean;
  zone_count?: number;
  risk_point_count?: number;
  updated_at: string;
}
export interface WorkbenchZone {
  id: string;
  enterprise_id: string;
  floor_id: string;
  floor_name: string;
  name: string;
  description: string | null;
  sort_order: number;
  floor_plan_polygon: RiskZoneFloorPlanPolygon | null;
  max_risk_level: RiskLevel | null;
  effective_color: string | null;
  object_count: number;
  created_at: string;
  updated_at: string;
  objects?: import("@/types/riskManagement").RiskObject[];
}
export interface PendingRegion {
  id: string;
  floor_id: string;
  points: RiskPolygonPoint[];
  created_at: string;
}
export interface WorkbenchSnapshot {
  floors: EnterpriseFloor[];
  currentFloorId: string;
  zones: WorkbenchZone[];
  riskPoints: import("@/types/riskManagement").RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
}
export interface RawWorkbenchSnapshot {
  floors: EnterpriseFloor[];
  current_floor_id: string;
  zones: WorkbenchZone[];
  risk_points: import("@/types/riskManagement").RiskObject[];
  texts: RiskCanvasText[];
  pending_regions?: PendingRegion[];
}
export interface RawOverviewResponse {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
  risk_points: import("@/types/riskManagement").RiskObject[];
}
export interface BatchSaveZoneItem {
  client_id?: string;
  zone_id?: string | null;
  name?: string;
  description?: string;
  sort_order?: number;
  updated_at?: string | null;
  floor_plan_polygon: RiskZoneFloorPlanPolygon;
}
export interface BatchSaveRiskPointItem {
  client_id?: string;
  id?: string | null;
  name?: string;
  category?: string;
  description?: string;
  zone_id?: string | null;
  zone_client_id?: string | null;
  floor_id?: string | null;
  location_x: number;
  location_y: number;
  updated_at?: string | null;
}
export interface BatchSavePayload {
  floor_id: string;
  floor_updated_at: string;
  zones: BatchSaveZoneItem[];
  risk_points: BatchSaveRiskPointItem[];
  deleted_risk_point_ids: string[];
  deleted_zone_ids: string[];
  confirm_cascade_zone_ids: string[];
  texts: RiskCanvasText[];
}
export interface BatchSaveResponse {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
  risk_points: import("@/types/riskManagement").RiskObject[];
  texts: RiskCanvasText[];
  created_zone_map: Record<string, string>;
  created_risk_point_map: Record<string, string>;
}
