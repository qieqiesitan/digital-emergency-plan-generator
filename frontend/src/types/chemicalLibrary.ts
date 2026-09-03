export interface ChemicalLibraryItem {
  id: string;
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
  created_at: string;
  updated_at: string;
}

export interface ChemicalLibraryPayload {
  name: string;
  cas_no?: string | null;
  un_no?: string | null;
  physical_state?: string | null;
  flash_point?: string | null;
  explosion_limit?: string | null;
  ignition_temp?: string | null;
  density?: string | null;
  boiling_point?: string | null;
  health_hazard?: string | null;
  fire_hazard?: string | null;
  leak_response?: string | null;
  storage_transport?: string | null;
  first_aid?: string | null;
  protective_measures?: string | null;
}

export interface ChemicalLibraryCreate extends ChemicalLibraryPayload {}
export type ChemicalLibraryUpdate = Partial<ChemicalLibraryPayload>;

export interface CollectEnterpriseOption {
  id: string;
  name: string;
}
