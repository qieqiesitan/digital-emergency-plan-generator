export interface DashboardStats {
  enterprise_count: number;
  plan_count: number;
  completed_plan_count: number;
  risk_source_count: number;
  risk_event_count: number;
}

export interface DashboardRecentPlan {
  id: string;
  title: string;
  plan_type: string;
  enterprise_name: string;
  status: string;
  completed_sections: number;
  total_sections: number;
  updated_at: string;
}

export interface DashboardData {
  stats: DashboardStats;
  recent_plans: DashboardRecentPlan[];
  recent_enterprises: Array<{
    id: string;
    name: string;
    plan_count: number;
    updated_at: string;
  }>;
}
