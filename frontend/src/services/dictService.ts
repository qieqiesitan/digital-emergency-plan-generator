import api from "./api";
import type { ApiResponse } from "@/types/common";

export interface DictItem {
  id: number;
  dictType: string;
  dictCode: string;
  dictLabel: string;
  dictSort: number;
  status: number;
}

export interface DictType {
  id: number;
  dictName: string;
  dictType: string;
  status: number;
}

export async function fetchDictItems(dictType: string): Promise<DictItem[]> {
  const res = await api.get<ApiResponse<DictItem[]>>(`/system/dicts/${dictType}`);
  return res.data.data;
}

export async function fetchDictTypes(): Promise<DictType[]> {
  const res = await api.get<ApiResponse<DictType[]>>("/system/dict-types");
  return res.data.data;
}
