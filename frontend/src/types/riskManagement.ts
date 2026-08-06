export type MethodType = "LS" | "LEC" | "COAL_LS" | "DIRECT";
export type MeasureCategory = "engineering" | "management" | "ppe" | "emergency";
export type MeasureStatus = "pending" | "implemented" | "expired";

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

export interface CheckItem { name: string; standard: string; frequency: string; }

export interface MethodConfig {
  version: string; formula: string; display_name: string;
  parameters: { key: string; label: string; type: string; range: number[]; levels: { value: number; label: string; desc: string }[] }[];
  risk_thresholds: { min: number; max: number; level: string; color: string; action: string; deadline: string }[];
}

export interface RiskAssessmentMethod {
  id: string; enterprise_id: string | null; method_type: MethodType;
  name: string; description: string; config: MethodConfig; is_active: boolean; is_system: boolean;
}

export interface RiskZone {
  id: string;
  enterprise_id: string;
  floor_id: string | null;
  floor_name: string | null;
  name: string;
  description: string | null;
  sort_order: number;
  floor_plan_polygon: RiskZoneFloorPlanPolygon | null;
  max_risk_level: string | null;
  effective_color: string | null;
  object_count: number;
  created_at: string;
  updated_at: string;
}
export interface RiskZoneCreate {
  floor_id?: string | null;
  name: string;
  description?: string;
  sort_order?: number;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
}

export interface RiskObject {
  id: string;
  enterprise_id: string;
  zone_id: string | null;
  floor_id: string | null;
  name: string;
  category: string | null;
  location: string | null;
  location_x: number | null;
  location_y: number | null;
  description: string | null;
  image_url: string | null;
  is_risk_point: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
  unit_count: number;
}
export interface RiskObjectCreate {
  zone_id?: string;
  floor_id?: string | null;
  name: string;
  category?: string;
  location?: string;
  location_x?: number;
  location_y?: number;
  description?: string;
  image_url?: string;
  is_risk_point?: boolean;
}

export interface RiskUnit { id: string; object_id: string; name: string; unit_type: string | null; description: string | null; location: string | null; sort_order: number; created_at: string; event_count: number; }
export interface RiskUnitCreate { object_id?: string; name: string; unit_type?: string; description?: string; location?: string; }

export interface RiskEvent { id: string; unit_id: string | null; object_id: string | null; accident_type: string; description: string | null; trigger_conditions: string | null; consequences: string | null; method_type: MethodType; method_params: Record<string, number>; risk_level: string | null; risk_score: string | null; sort_order: number; created_at: string; measure_count: number; }
export interface RiskEventCreate { unit_id?: string; object_id?: string; accident_type: string; description?: string; trigger_conditions?: string; consequences?: string; method_type?: MethodType; method_params?: Record<string, number>; }

export interface RiskMeasure { id: string; event_id: string; measure_category: MeasureCategory; measure_type: string | null; description: string; responsible_person: string | null; deadline: string | null; check_items: CheckItem[]; status: MeasureStatus; sort_order: number; created_at: string; }
export interface RiskMeasureCreate { event_id?: string; measure_category: MeasureCategory; measure_type?: string; description: string; responsible_person?: string; deadline?: string; check_items?: CheckItem[]; }

export interface HierarchyMeasure extends Pick<RiskMeasure, 'id'|'measure_category'|'measure_type'|'description'|'status'> { check_items: CheckItem[]; }
export interface HierarchyEvent extends Pick<RiskEvent, 'id'|'accident_type'|'description'|'risk_level'|'risk_score'|'method_type'> { method_params: Record<string, number>; measures: HierarchyMeasure[]; }
export interface HierarchyUnit extends Pick<RiskUnit, 'id'|'name'|'unit_type'> { events: HierarchyEvent[]; }
export interface HierarchyObject {
  id: string;
  name: string;
  category: string | null;
  is_risk_point: boolean;
  floor_id?: string | null;
  location_x?: number | null;
  location_y?: number | null;
  units: HierarchyUnit[];
  events: HierarchyEvent[];
}
export interface HierarchyZone {
  id: string;
  name: string;
  description: string | null;
  floor_id?: string | null;
  floor_name?: string | null;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
  max_risk_level?: string | null;
  effective_color?: string | null;
  objects: HierarchyObject[];
}

export interface SmartGuideMeasure {
  description: string;
  measure_category?: string;
  measure_type?: string;
  check_items?: CheckItem[];
}

export interface SmartGuideEvent {
  accident_type: string;
  description?: string;
  risk_level?: string;
  risk_score?: string;
  method_type?: string;
  method_params?: Record<string, number>;
  measures?: SmartGuideMeasure[];
}

export interface SmartGuideUnit {
  name: string;
  unit_type?: string;
  description?: string;
  events?: SmartGuideEvent[];
}

export interface SmartGuideObject {
  name: string;
  category?: string;
  is_risk_point?: boolean;
  units?: SmartGuideUnit[];
  events?: SmartGuideEvent[];
}

export interface SmartGuideZone {
  name: string;
  description?: string;
  objects?: SmartGuideObject[];
}

export interface MigrationPreviewItem {
  source_id: string;
  source_name: string;
  source_location: string | null;
  source_categories: string[];
  suggested_zone: string;
  suggested_object: string;
  suggested_event: string;
  suggested_params: Record<string, number>;
  control_measures: string | null;
}

export interface MigrationPreviewResponse {
  items: MigrationPreviewItem[];
  total: number;
  migrated_total: number;
}

export interface MigrationExecutePayload {
  source_id: string;
  zone_name: string;
  object_name: string;
  accident_type: string;
  method_params: Record<string, number>;
}

export interface MigrationExecuteResponse {
  migrated: number;
  skipped: number;
  created: {
    zones: number;
    objects: number;
    events: number;
    measures: number;
  };
}
