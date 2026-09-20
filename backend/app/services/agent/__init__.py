"""agent 定义与任务分层参数。

历史说明（2026-09-20 清理）：本目录原有一版 `orchestrator.py` + `task_graph.py` 的
DAG 编排骨架，但**从未接线**——真正在跑的是 `app/services/workflow/`
（WorkflowRunner + templates：顺序执行、重试、确认门控、进度落库，已挂聊天工具）。
两者功能重叠，为避免"两套编排"，已删除那版骨架；本模块只保留
`Agent`/`AGENTS`（专业 agent 的提示词与工具子集，供阅读与后续接线）
以及**在用**的 `LAYER_PARAMS`（章节生成/复核/报告按其选择温度与长度）。
"""

from app.services.agent.agents import Agent, AgentRegistry, AGENTS

__all__ = ["Agent", "AgentRegistry", "AGENTS"]
