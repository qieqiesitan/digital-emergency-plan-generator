export interface EmergencyResource {
  id: string;
  enterprise_id: string;
  category: string;
  name: string;
  specification: string;
  quantity: number;
  unit: string;
  location: string;
  responsible_person: string;
  contact_phone: string;
  is_external: boolean;
  external_address: string;
  external_distance_km: number | null;
  created_at: string;
}

export interface EmergencyResourceCreate {
  category: string;
  name: string;
  specification?: string;
  quantity?: number;
  unit?: string;
  location?: string;
  responsible_person?: string;
  contact_phone?: string;
  is_external?: boolean;
  external_address?: string;
  external_distance_km?: number | null;
}

export interface EmergencyResourceUpdate extends Partial<EmergencyResourceCreate> {}
