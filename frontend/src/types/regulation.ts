export interface RegulationNode {
  id: string;
  label: string;
  full_name: string;
  node_type: "law" | "standard" | "policy" | "topic";
  code: string;
  version: string;
  effective_date: string;
  issuing_body: string;
  status: "effective" | "abolished" | "revised";
  abolished_by?: string;
  topics: string[];
  article_count: number;
  indexed: boolean;
  ai_topics?: string[];
  is_core?: boolean;
  created_at: string;
  updated_at: string;
  source?: string;
  articles?: RegulationArticle[];
  source_files?: SourceFile[];
}

export interface RegulationEdge {
  source: string;
  target: string;
  relation: string;
}

export interface RegulationArticle {
  number: string;
  text: string;
}

export interface SourceFile {
  filename: string;
  size: number;
  uploaded_at: string;
  path: string;
}

export interface RegulationParseRequest {
  raw_text?: string;
  file?: File;
}

export interface RegulationParseResult {
  code: string;
  full_name: string;
  issuing_body: string;
  issue_date: string;
  effective_date: string;
  replaces: string[];
  based_on: string[];
  topics: string[];
  articles: RegulationArticle[];
  article_count: number;
  version?: string;
  node_type?: string;
}

export interface RegulationCreateRequest {
  code: string;
  full_name: string;
  issuing_body: string;
  issue_date: string;
  effective_date: string;
  node_type?: string;
  version?: string;
  replaces: string[];
  based_on: string[];
  topics: string[];
  articles: RegulationArticle[];
}

export interface RegulationListParams {
  keyword?: string;
  status?: "effective" | "abolished" | "all";
  node_type?: "law" | "standard" | "policy" | "all";
  page?: number;
  page_size?: number;
}

export interface RegulationListResponse {
  items: RegulationNode[];
  total: number;
  page: number;
  page_size: number;
  indexed_articles?: number;
}

export interface RegulationStats {
  total: number;
  effective: number;
  abolished: number;
  indexed_articles: number;
}

export interface RegulationGraphData {
  nodes: RegulationNode[];
  edges: RegulationEdge[];
}

export interface HistoryEvent {
  event_id: string;
  timestamp: string;
  regulation_id: string;
  action: "created" | "updated" | "abolished" | "deleted" | "reindexed";
  operator: string;
  detail: Record<string, unknown>;
}

export interface UpdateTopicsRequest {
  topics: string[];
}
export interface DuplicateCheckRequest {
  code: string;
  full_name: string;
}

export interface DuplicateMatch {
  id: string;
  code: string;
  full_name: string;
  similarity: number;
}

export interface DuplicateCheckResponse {
  duplicates: DuplicateMatch[];
  is_duplicate: boolean;
}

export interface ImpactResult {
  id: string;
  name: string;
  affected_count: number;
  plan_names: string[];
}

export interface ImpactResponse {
  affected_plan_count: number;
  plans: ImpactResult[];
}

export interface BatchAbolishRequest {
  ids: string[];
}

export interface BatchAbolishResult {
  id: string;
  success: boolean;
  error?: string;
}

export interface BatchAbolishResponse {
  results: BatchAbolishResult[];
  total: number;
  success_count: number;
  fail_count: number;
}

