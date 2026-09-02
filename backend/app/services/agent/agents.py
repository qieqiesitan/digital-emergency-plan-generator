"""专业 agent 注册表：每个 agent = 名称 + 系统提示词 + 工具子集 + 执行说明。"""
from dataclasses import dataclass

PLAN_GENERATOR_TOOLS = frozenset({
    "get_plan", "list_plans", "get_enterprise", "generate_plan_content",
    "get_generation_progress", "search_regulation_articles", "list_regulations",
})
PLAN_REVIEWER_TOOLS = frozenset({"get_plan", "get_enterprise", "list_risk_sources",
                                 "search_regulation_articles", "list_regulations"})
REGULATION_TOOLS = frozenset({"search_regulation_articles", "search_regulations",
                              "list_regulations", "get_regulation_stats"})
REPORT_TOOLS = frozenset({"get_dashboard", "list_enterprises", "list_plans",
                          "list_risk_sources", "list_resources", "list_regulations"})
ASSISTANT_TOOLS = None  # 占位：全量工具由 chat.py CHAT_TOOLS 提供


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    system_prompt: str
    tools: frozenset | None = None


AGENTS = {
    "assistant": Agent(
        name="assistant",
        description="对外对话入口：覆盖全部系统操作",
        system_prompt="你是数字化应急预案自动生成系统的AI助手，负责理解用户意图并调度专业能力。",
        tools=None,
    ),
    "plan_generator": Agent(
        name="plan_generator",
        description="预案内容生成：按章节批量生成正文",
        system_prompt="你是应急预案编制专家，专注预案章节内容生成，输出规范公文正文。",
        tools=PLAN_GENERATOR_TOOLS,
    ),
    "plan_reviewer": Agent(
        name="plan_reviewer",
        description="预案质量审查与修订",
        system_prompt="你是应急预案质量审查专家，依据法规与模板审查章节完整性、引用真实性、数据一致性。",
        tools=PLAN_REVIEWER_TOOLS,
    ),
    "regulation": Agent(
        name="regulation",
        description="法规检索与引用校验",
        system_prompt="你是安全生产法规检索助手，优先用语义检索返回真实条文并给出出处。",
        tools=REGULATION_TOOLS,
    ),
    "report": Agent(
        name="report",
        description="数据采集与图文报告",
        system_prompt="你是应急管理数据分析师，基于系统数据生成结构化报告。",
        tools=REPORT_TOOLS,
    ),
}


class AgentRegistry:
    def __init__(self):
        self._agents = dict(AGENTS)

    def get(self, name: str) -> Agent:
        if name not in self._agents:
            raise KeyError(f"未知 agent: {name}")
        return self._agents[name]

    def names(self) -> list[str]:
        return list(self._agents)
