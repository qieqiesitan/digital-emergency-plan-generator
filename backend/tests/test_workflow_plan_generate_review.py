"""新工作流模板 `plan_generate_review`：对已有预案跑「生成 → 复核」，生成前有确认门控。

为什么这样设计：生成是不可逆的耗时动作（25 章十几分钟 + 模型额度），必须等用户确认；
复核复用既有 review_plan 工具。测试只验到"暂停在门控"这一步——**不确认**
（确认会真的触发 AI 生成，消耗真实额度）。
"""


from app.services.workflow.templates import TEMPLATES


def test_template_shape():
    tpl = TEMPLATES["plan_generate_review"]
    assert [s["name"] for s in tpl["steps"]] == ["generate", "review"]
    gen = tpl["steps"][0]
    assert gen["tool"] == "generate_plan_content"
    assert gen["confirm"] is True, "生成前必须有人工确认门控"
    assert gen["params_from"] == {"plan_id": "params.plan_id"}, "字符串形式会被硬编码成 name 键"
    assert tpl["steps"][1]["tool"] == "review_plan"
    assert tpl["dependencies"] == {"review": ["generate"]}


def test_tool_description_mentions_all_templates():
    """工具描述必须列出所有模板，否则模型不知道它存在（N-37 的教训）。"""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "chat.py").read_text(
        encoding="utf-8"
    )
    for name in TEMPLATES:
        assert name in src, f"run_workflow 工具描述未提及模板 {name}"


# 说明：启动/门控的**真实库**端到端不放这里（仓库约定 pytest 不连数据库），
#      由容器内探针 output/_pt/audit/probe_workflow_generate_review.py 覆盖。
