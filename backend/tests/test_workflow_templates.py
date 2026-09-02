"""test_workflow_templates.py — 两个工作流模板结构校验。"""
import pytest
from app.services.workflow.templates import (
    CREATE_ENTERPRISE_PLAN,
    REGULATORY_COMPLIANCE,
    TEMPLATES,
)


def test_create_enterprise_plan_template_shape():
    assert CREATE_ENTERPRISE_PLAN["name"] == "create_enterprise_plan"
    names = [s["name"] for s in CREATE_ENTERPRISE_PLAN["steps"]]
    assert names == ["create_enterprise", "create_plan",
                     "generate_plan", "review_plan", "export_docx"]
    # 顺序执行 + 确认门控：generate_plan 与 export_docx 需人工确认
    confirm_flags = {s["name"]: s.get("confirm", False) for s in CREATE_ENTERPRISE_PLAN["steps"]}
    assert confirm_flags["generate_plan"] is True
    assert confirm_flags["export_docx"] is True
    assert confirm_flags["create_enterprise"] is False
    # dependencies 只引用存在的步骤
    dep_keys = set(CREATE_ENTERPRISE_PLAN["dependencies"])
    assert dep_keys <= set(names)
    for deps in CREATE_ENTERPRISE_PLAN["dependencies"].values():
        assert set(deps) <= set(names)


def test_regulatory_compliance_template_shape():
    assert REGULATORY_COMPLIANCE["name"] == "regulatory_compliance"
    names = [s["name"] for s in REGULATORY_COMPLIANCE["steps"]]
    assert names == ["collect_enterprise", "search_regulations", "generate_report"]
    assert all(s.get("confirm") is not True for s in REGULATORY_COMPLIANCE["steps"])
    assert REGULATORY_COMPLIANCE["dependencies"]["generate_report"] == [
        "collect_enterprise", "search_regulations"]


def test_templates_registry_contains_both():
    assert set(TEMPLATES) == {"create_enterprise_plan", "regulatory_compliance"}
    for name, tpl in TEMPLATES.items():
        assert tpl["name"] == name
        assert isinstance(tpl["steps"], list) and tpl["steps"]
        # 每步有名字；有 tool 的步骤 tool 名与依赖解析均基于步骤集合
        step_names = {s["name"] for s in tpl["steps"]}
        assert len(step_names) == len(tpl["steps"])


@pytest.mark.parametrize("tpl_name", ["create_enterprise_plan", "regulatory_compliance"])
def test_template_params_from_references_existing_keys(tpl_name):
    tpl = TEMPLATES[tpl_name]
    step_names = {s["name"] for s in tpl["steps"]}
    for step in tpl["steps"]:
        spec = step.get("params_from")
        paths = [spec] if isinstance(spec, str) else (spec.values() if isinstance(spec, dict) else [])
        for p in paths:
            parts = str(p).split(".")
            if parts[0] == "steps":
                # steps.<step_name> 必须指向模板内已有步骤
                assert parts[1] in step_names, f"{tpl_name} {step['name']} 引用了未知步骤 {parts[1]}"
