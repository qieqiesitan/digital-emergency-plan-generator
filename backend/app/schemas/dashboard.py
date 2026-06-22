from app.schemas.common import DatetimeStr
from pydantic import BaseModel

class DashboardStats(BaseModel):
    enterprise_count: int; plan_count: int; completed_plan_count: int; risk_source_count: int

class DashboardRecentPlan(BaseModel):
    id: str; title: str; plan_type: str; enterprise_name: str; status: str
    completed_sections: int; total_sections: int; updated_at: DatetimeStr

class DashboardRecentEnterprise(BaseModel):
    id: str; name: str; plan_count: int; updated_at: DatetimeStr

class DashboardResponse(BaseModel):
    stats: DashboardStats; recent_plans: list[DashboardRecentPlan]
    recent_enterprises: list[DashboardRecentEnterprise]
