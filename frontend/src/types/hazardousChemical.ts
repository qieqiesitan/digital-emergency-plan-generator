export interface HazardousChemical {
  id: string;
  enterprise_id: string;
  name: string;
  cas_no: string | null;
  un_no: string | null;
  physical_state: string | null;
  flash_point: string | null;
  explosion_limit: string | null;
  ignition_temp: string | null;
  density: string | null;
  boiling_point: string | null;
  health_hazard: string | null;
  fire_hazard: string | null;
  leak_response: string | null;
  storage_transport: string | null;
  first_aid: string | null;
  protective_measures: string | null;
  location: string | null;
  max_storage: string | null;
  created_at: string;
  updated_at: string;
}

export interface HazardousChemicalCreate {
  name: string;
  cas_no?: string;
  un_no?: string;
  physical_state?: string;
  flash_point?: string;
  explosion_limit?: string;
  ignition_temp?: string;
  density?: string;
  boiling_point?: string;
  health_hazard?: string;
  fire_hazard?: string;
  leak_response?: string;
  storage_transport?: string;
  first_aid?: string;
  protective_measures?: string;
  location?: string;
  max_storage?: string;
}

export interface HazardousChemicalUpdate extends Partial<HazardousChemicalCreate> {}
