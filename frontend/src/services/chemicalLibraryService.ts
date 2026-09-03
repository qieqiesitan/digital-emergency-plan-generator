import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { AxiosRequestConfig } from "axios";
import type {
  ChemicalLibraryCreate,
  ChemicalLibraryItem,
  ChemicalLibraryUpdate,
  CollectEnterpriseOption,
} from "@/types/chemicalLibrary";
import type { HazardousChemical } from "@/types/hazardousChemical";

export async function listLibrary(
  keyword?: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig,
): Promise<PaginatedResponse<ChemicalLibraryItem>> {
  const res = await api.get<PaginatedResponse<ChemicalLibraryItem>>(
    "/chemical-library",
    { params: { ...(keyword ? { keyword } : {}), ...params }, ...config },
  );
  return res.data;
}

export async function createLibraryItem(
  data: ChemicalLibraryCreate,
  config?: AxiosRequestConfig,
): Promise<ChemicalLibraryItem> {
  const res = await api.post<ApiResponse<ChemicalLibraryItem>>(
    "/chemical-library",
    data,
    config,
  );
  return res.data.data;
}

export async function updateLibraryItem(
  id: string,
  patch: ChemicalLibraryUpdate,
  config?: AxiosRequestConfig,
): Promise<ChemicalLibraryItem> {
  const res = await api.put<ApiResponse<ChemicalLibraryItem>>(
    `/chemical-library/${id}`,
    patch,
    config,
  );
  return res.data.data;
}

export async function deleteLibraryItem(
  id: string,
  config?: AxiosRequestConfig,
): Promise<void> {
  await api.delete(`/chemical-library/${id}`, config);
}

export async function collectEnterprises(
  keyword: string,
  config?: AxiosRequestConfig,
): Promise<CollectEnterpriseOption[]> {
  const res = await api.get<ApiResponse<CollectEnterpriseOption[]>>(
    "/chemical-library/collect/enterprises",
    { params: { keyword }, ...config },
  );
  return res.data.data;
}

export async function listEnterpriseChemicals(
  enterpriseId: string,
  config?: AxiosRequestConfig,
): Promise<HazardousChemical[]> {
  const res = await api.get<ApiResponse<HazardousChemical[]>>(
    `/chemical-library/collect/enterprises/${enterpriseId}/chemicals`,
    config,
  );
  return res.data.data;
}

export async function collectChemical(
  enterpriseId: string,
  chemicalId: string,
  config?: AxiosRequestConfig,
): Promise<ChemicalLibraryItem> {
  const payload = { enterprise_id: enterpriseId, chemical_id: chemicalId };
  const res = config
    ? await api.post<ApiResponse<ChemicalLibraryItem>>("/chemical-library/collect", payload, config)
    : await api.post<ApiResponse<ChemicalLibraryItem>>("/chemical-library/collect", payload);
  return res.data.data;
}
