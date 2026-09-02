"""任务 DAG：拓扑排序 + 并行执行（失败中止/降级由调用方策略决定）。"""
import asyncio


class TaskGraph:
    def __init__(self):
        self._tasks: dict[str, list[str]] = {}   # name -> deps

    def add_task(self, name: str, deps: list[str] | None = None):
        self._tasks[name] = list(deps or [])

    def topological_order(self):
        indeg = {n: len(deps) for n, deps in self._tasks.items()}
        adj = {n: [] for n in self._tasks}
        for n, deps in self._tasks.items():
            for d in deps:
                adj[d].append(n)
        queue = [n for n, d in indeg.items() if d == 0]
        order = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if len(order) != len(self._tasks):
            raise ValueError("DAG 存在环")
        return order


async def run_dag(graph: TaskGraph, ctx: dict, run_fn, max_concurrency: int = 3):
    """按拓扑序执行；无依赖的任务并行（受 max_concurrency 限制）。失败抛异常（由 orchestrator 捕获降级）。"""
    order = list(graph.topological_order())
    sem = asyncio.Semaphore(max_concurrency)
    results: dict = {}

    async def run_one(name):
        async with sem:
            return name, await run_fn(name, ctx)

    pending = order[:]
    while pending:
        ready = [n for n in pending if all(d in results for d in graph._tasks[n])]
        if not ready:
            raise RuntimeError("无法推进 DAG")
        outs = await asyncio.gather(*[run_one(n) for n in ready])
        for name, res in outs:
            results[name] = res
            pending.remove(name)
    return results
