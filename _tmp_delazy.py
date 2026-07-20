import re

# ── 1. Fix chat_dispatch.py ──
with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add missing top-level imports after the last enterprise import (before "AIConfig")
# Current last import: AIConfig as AIConfigModel,
replacement_imports = """from app.models.enterprise import (
    Enterprise, RiskSource, EmergencyResource, PlanProject,
    PlanSection, PlanTemplate, AIConfig as AIConfigModel,
)
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport
from app.services.enterprise_autofill import autofill
from app.regulations import get_graph, get_vector_store
import os
from app.routers.export import generate_plan_docx as generate_plan_docx_func"""

old_imports = """from app.models.enterprise import (
    Enterprise, RiskSource, EmergencyResource, PlanProject,
    PlanSection, PlanTemplate, AIConfig as AIConfigModel,
)"""

content = content.replace(old_imports, replacement_imports)

# Remove all lazy imports from function bodies
lazy_imports = [
    "    from app.services.enterprise_autofill import autofill as do_autofill\n",
    "    from app.models.risk_assessment import RiskAssessmentReport\n",
    "    from app.models.resource_investigation import ResourceInvestigationReport\n",
    "    from app.regulations import get_graph, get_vector_store\n",
    "    from app.regulations import get_graph\n",
    "    from app.regulations import get_vector_store, get_graph\n",
    "    from app.routers.export import generate_plan_docx as do_export\n",
    "    import os\n",
]

for lazy in lazy_imports:
    if lazy in content:
        content = content.replace(lazy, "")
        print(f"  Removed: {lazy.strip()}")

# Fix references to aliased imports
# autofill was aliased as do_autofill, now it's just autofill
content = content.replace("do_autofill(", "autofill(")
# export was aliased as do_export, now it's generate_plan_docx_func
content = content.replace("generate_plan_docx as do_export", "generate_plan_docx as generate_plan_docx_func")
content = content.replace("await do_export(", "await generate_plan_docx_func(")

with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py", "w", encoding="utf-8") as f:
    f.write(content)
print("chat_dispatch.py fixed")

# ── 2. Fix chat.py ──
with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\chat.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add datetime import at top level
content = content.replace(
    "from app.services.sse_utils import sse_line\nimport httpx",
    "from datetime import datetime, timezone\nfrom app.services.sse_utils import sse_line\nimport httpx"
)

# Remove lazy imports from function bodies
lazy_chat = [
    "    from app.services.mermaid_renderer import render_mermaid_svg\n",
    "    from app.models.chat import ChatConversation, ChatMessage\n",
    "    from datetime import datetime, timezone\n",
]
for lazy in lazy_chat:
    if lazy in content:
        content = content.replace(lazy, "")
        print(f"  Removed: {lazy.strip()}")

with open(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\chat.py", "w", encoding="utf-8") as f:
    f.write(content)
print("chat.py fixed")

print("\nDone")
