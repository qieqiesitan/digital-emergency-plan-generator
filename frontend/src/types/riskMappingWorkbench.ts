import type {
  RiskObject,
  RiskLevel,
  RiskPolygonPoint,
  RiskZoneFloorPlanPolygon,
} from "@/types/riskManagement";

export type {
  RiskLevel,
  ColorSource,
  RiskPolygonPoint,
  RiskPolygon,
  RiskZoneFloorPlanPolygon,
} from "@/types/riskManagement";

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
  inherent_max_level?: RiskLevel | null;
  inherent_effective_color?: string | null;
  object_count: number;
  open_hazard_count?: number;
  created_at: string;
  updated_at: string;
  objects?: RiskObject[];
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
  riskPoints: RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
}
export interface RawWorkbenchSnapshot {
  floors: EnterpriseFloor[];
  current_floor_id: string;
  zones: WorkbenchZone[];
  risk_points: RiskObject[];
  texts: RiskCanvasText[];
  pending_regions?: PendingRegion[];
}
export interface RawOverviewResponse {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
  risk_points: RiskObject[];
}

export interface BatchSaveZoneCreateItem {
  zone_id: null;
  client_id: string;
  name: string;
  description?: string;
  sort_order?: number;
  floor_plan_polygon: RiskZoneFloorPlanPolygon;
}
export interface BatchSaveZoneUpdateItem {
  zone_id: string;
  updated_at: string;
  client_id?: string;
  name?: string;
  description?: string;
  sort_order?: number;
  floor_plan_polygon: RiskZoneFloorPlanPolygon;
}
export type BatchSaveZoneItem = BatchSaveZoneCreateItem | BatchSaveZoneUpdateItem;

export interface BatchSaveRiskPointCreateItem {
  id: null;
  client_id: string;
  name: string;
  category?: string;
  description?: string;
  zone_id?: string | null;
  zone_client_id?: string | null;
  floor_id?: string | null;
  location_x: number;
  location_y: number;
}
export interface BatchSaveRiskPointUpdateItem {
  id: string;
  updated_at: string;
  client_id?: string;
  name?: string;
  category?: string;
  description?: string;
  zone_id?: string | null;
  zone_client_id?: string | null;
  floor_id?: string | null;
  location_x: number;
  location_y: number;
}
export type BatchSaveRiskPointItem = BatchSaveRiskPointCreateItem | BatchSaveRiskPointUpdateItem;

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
  risk_points: RiskObject[];
  texts: RiskCanvasText[];
  created_zone_map: Record<string, string>;
  created_risk_point_map: Record<string, string>;
}

export interface FourColorDraftPolygon {
  id: string;
  label?: string | null;
  points: { x: number; y: number }[];
}
export interface FourColorDraftZone {
  client_id: string;
  name: string;
  risk_level: RiskLevel;
  color: string;
  suspected?: boolean;
  suggested_name?: string | null;
  ai_hint?: string | null;
  polygons: FourColorDraftPolygon[];
}
export interface FourColorExcludedItem {
  color: string;
  reason: "legend" | "thin" | "border_frame" | "tiny";
  polygons: FourColorDraftPolygon[];
}
export interface FourColorTextItem {
  points: { x: number; y: number }[];
  text: string;
  confidence: number;
}
export interface FourColorAnalyzeResult {
  preview_url: string;
  canvas_width: number;
  canvas_height: number;
  zones: FourColorDraftZone[];
  warnings: string[];
  excluded: FourColorExcludedItem[];
  texts: FourColorTextItem[];
}
export interface FourColorCommitPolygon {
  points: { x: number; y: number }[];
}
export interface FourColorCommitZone {
  name: string;
  risk_level: RiskLevel;
  polygons: FourColorCommitPolygon[];
}
export interface FourColorCommitPayload {
  file_token: string;
  zones: FourColorCommitZone[];
  replace_existing: boolean;
}
export interface FourColorCommitResult {
  floor: EnterpriseFloor;
  zones: WorkbenchZone[];
}
