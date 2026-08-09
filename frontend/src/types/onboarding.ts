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
