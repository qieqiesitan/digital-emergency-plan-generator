export interface CompletionModule {
  key: string;
  label: string;
  weight: number;
  done: boolean;
}

export interface CompletionResult {
  percent: number;
  modules: CompletionModule[];
}

export interface CandidateItem {
  _key: string;
  source?: string;
  [key: string]: unknown;
}

/** 单文件/资料包导入结果：模块归属 + 候选 + 来源（文件名） */
export interface ImportResult {
  module: string;
  candidates: CandidateItem[];
  source: string;
}
