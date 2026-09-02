"""编排入口：把「生成→审查→修订」组合成 DAG 执行。"""
from app.services.agent.task_graph import TaskGraph, run_dag


async def run_generate_review(plan_id: str, mode: str = "llm") -> dict:
    """示例组合：generate_plan_content → get_plan → review（POST apply 由调用方触发）。
    本函数为编排骨架；具体步骤接入见任务 4 工作流（此处保留最小可用实现供测试）。"""
    g = TaskGraph()
    g.add_task("generate", deps=[])
    g.add_task("review", deps=["generate"])
    return await run_dag(g, {"plan_id": plan_id}, _noop_step)


async def _noop_step(name, ctx):
    return {"step": name, "ctx": ctx}
