"""端到端工作流模板（JSON：steps + dependencies + 确认门控）。

每步字段：
- name：步骤名（结果以 ctx["steps"][name] 供后续步骤引用）
- tool：实际调用的 chat_dispatch 工具名
- params_from：字符串路径（取单个值）或 dict（字段映射），源为 ctx
- confirm：True 表示该步需人工确认后才执行（确认门控）

步骤按列表顺序执行；dependencies 供 DAG/进度可视化与调用方参考。
"""

CREATE_ENTERPRISE_PLAN = {
    "name": "create_enterprise_plan",
    "steps": [
        {"name": "create_enterprise", "tool": "autofill_enterprise",
         "params_from": "params.name"},
        {"name": "create_plan", "tool": "create_plan",
         "params_from": {"enterprise_id": "steps.create_enterprise.id",
                         "title": "params.title"}},
        {"name": "generate_plan", "tool": "generate_plan_content",
         "params_from": "steps.create_plan.id", "confirm": True},
        {"name": "review_plan", "tool": "review_plan",
         "params_from": "steps.create_plan.id"},
        {"name": "export_docx", "tool": "export_plan_docx",
         "params_from": "steps.create_plan.id", "confirm": True},
    ],
    "dependencies": {
        "create_plan": ["create_enterprise"],
        "generate_plan": ["create_plan"],
        "review_plan": ["generate_plan"],
        "export_docx": ["review_plan"],
    },
}

REGULATORY_COMPLIANCE = {
    "name": "regulatory_compliance",
    "steps": [
        {"name": "collect_enterprise", "tool": "get_enterprise",
         "params_from": "params.enterprise_id"},
        {"name": "search_regulations", "tool": "search_regulation_articles",
         "params_from": "params.query"},
        {"name": "generate_report", "tool": "generate_report",
         "params_from": {"topic": "法规合规"}},
    ],
    "dependencies": {
        "search_regulations": ["collect_enterprise"],
        "generate_report": ["collect_enterprise", "search_regulations"],
    },
}

TEMPLATES = {t["name"]: t for t in (CREATE_ENTERPRISE_PLAN, REGULATORY_COMPLIANCE)}
