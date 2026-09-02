"""test_agent_registry.py — agent 注册与工具子集。"""
from app.services.agent.agents import AgentRegistry, PLAN_GENERATOR_TOOLS, ASSISTANT_TOOLS


def test_registry_registers_core_agents():
    reg = AgentRegistry()
    assert set(reg.names()) >= {"assistant", "plan_generator", "plan_reviewer", "regulation", "report"}


def test_plan_generator_tools_subset():
    # 生成 agent 工具子集应包含预案/章节相关，且远小于全量
    assert "generate_plan_content" in PLAN_GENERATOR_TOOLS
    assert "get_plan" in PLAN_GENERATOR_TOOLS
    assert "delete_enterprise" not in PLAN_GENERATOR_TOOLS


def test_assistant_tools_is_full_set():
    # ASSISTANT_TOOLS=None 表示占位全量：全量工具由 chat.py CHAT_TOOLS 提供，
    # 语义上大于任何收敛工具子集（勿误配成受限子集）。
    assert ASSISTANT_TOOLS is None
