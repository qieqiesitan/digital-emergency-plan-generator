with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\schemas\enterprise.py", "r", encoding="utf-8") as f:
    content = f.read()

# Build the new file content
import textwrap

# Shared fields definition
shared_fields = """class EnterpriseBase(BaseModel):
    \"\"\"企业共享字段。Create/Update/Response 继承此基类，消除字段重复定义。\"\"\"
    name: str
    address: str | None = None
    industry: str | None = None
    business_scope: str | None = None
    employee_count: int | None = None
    credit_code: str | None = None
    legal_representative: str | None = None
    economic_type: str | None = None
    established_date: str | None = None
    registered_capital: float | None = None
    phone: str | None = None
    fax: str | None = None
    postal_code: str | None = None
    land_area: float | None = None
    building_area: float | None = None
    safety_officer: str | None = None
    safety_officer_phone: str | None = None
    safety_staff_count: int | None = None
    safety_standardization: str | None = None
    fire_approval: str | None = None
    fire_approval_date: str | None = None
    last_plan_filing_date: str | None = None
    last_plan_filing_authority: str | None = None
    main_products: str | None = None
    annual_capacity: str | None = None
    hazardous_chemicals: str | None = None
    special_equipment: str | None = None
    building_overview: str | None = None
    floor_plan_url: str | None = None
    gis_lat: float | None = None
    gis_lng: float | None = None


class EnterpriseCreate(EnterpriseBase):
    \"\"\"创建企业。name 从 EnterpriseBase 继承为必填。\"\"\"
    pass


class EnterpriseUpdate(EnterpriseBase):
    \"\"\"更新企业。所有字段均为可选，包括 name。\"\"\"
    name: str | None = None  # 覆盖为可选"""

# New EnterpriseResponse
response_class = """class EnterpriseResponse(EnterpriseBase):
    \"\"\"企业响应。包含 EnterpriseBase 所有字段 + 额外响应字段。\"\"\"
    id: str
    established_date: DatetimeStr | None = None
    fire_approval_date: DatetimeStr | None = None
    last_plan_filing_date: DatetimeStr | None = None
    last_plan_filing_authority: str | None = None
    building_overview: str | None = None
    org_structure: list = []
    surrounding_info: dict | None = None
    floor_plan_url: str | None = None
    gis_lat: float | None = None
    gis_lng: float | None = None
    risk_sources_count: int = 0
    resources_count: int = 0
    plans_count: int = 0
    created_at: DatetimeStr
    updated_at: DatetimeStr

    model_config = {"from_attributes": True}"""

# Now replace in the file
# 1. Keep everything before "class EnterpriseCreate" (imports + OrgMember + OrgGroup + NearbyUnit + SensitiveTarget + SurroundingInfo)
# 2. Replace the EnterpriseCreate/Update/Response classes with EnterpriseBase + delegations
# 3. Keep Autofill classes

import re

# Find the start of EnterpriseCreate
create_start = content.find("class EnterpriseCreate")
# Find the end of EnterpriseResponse (start of AutofillRequest)
response_end = content.find("class AutofillRequest")

if create_start >= 0 and response_end > create_start:
    new_content = content[:create_start]
    new_content += shared_fields + "\n\n"
    new_content += response_class + "\n\n"
    new_content += content[response_end:]
    
    with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\schemas\enterprise.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Enterprise schema refactored successfully")
else:
    print(f"Error: create_start={create_start}, response_end={response_end}")
    print("File may not have expected structure")
