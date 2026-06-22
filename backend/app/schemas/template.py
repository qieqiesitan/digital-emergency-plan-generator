from pydantic import BaseModel

class SectionTemplateItem(BaseModel):
    key: str; title: str; level: int; sort_order: int
    ai_generatable: bool = True; user_editable: bool = True; required: bool = True
    auto_fill: bool = False; auto_fill_source: str | None = None
    gb_requirement: str = ""; prompt_template: str | None = None
    data_dependencies: list[str] = []; subsections: list["SectionTemplateItem"] = []

class TemplateResponse(BaseModel):
    id: str; plan_type: str; name: str; version: str; structure: list = []; is_active: bool
    model_config = {"from_attributes": True}
