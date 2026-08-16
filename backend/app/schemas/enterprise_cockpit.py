from pydantic import BaseModel


class RiskCounts(BaseModel):
    major: int = 0
    larger: int = 0
    general: int = 0
    low: int = 0
    total: int = 0


class TopRisk(BaseModel):
    name: str
    level: str
    score: float | None = None
    responsible_unit: str | None = None


class ZoneRisk(BaseModel):
    zone_name: str
    counts: RiskCounts
    total: int = 0


class CockpitTodo(BaseModel):
    priority: str
    title: str
    note: str = ""


class CompletionModule(BaseModel):
    key: str
    label: str
    done: bool


class CockpitCompletion(BaseModel):
    percent: int = 0
    modules: list[CompletionModule] = []


class ActivityItem(BaseModel):
    actor: str = "系统"
    action: str
    time: str = ""


class HazardCounts(BaseModel):
    open: int = 0
    due: int = 0
    overdue: int = 0


class CockpitSummary(BaseModel):
    risk_counts: RiskCounts = RiskCounts()
    zone_risks: list[ZoneRisk] = []
    top_risks: list[TopRisk] = []
    risk_index: int = 0
    hazard_counts: HazardCounts = HazardCounts()
    todos: list[CockpitTodo] = []
    completion: CockpitCompletion = CockpitCompletion()
    recent_activities: list[ActivityItem] = []
