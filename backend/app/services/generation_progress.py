"""预案生成进程内状态（keyed by plan_id）：仅供轮询，重启即失，不落库。"""
import time

_PROGRESS: dict[str, dict] = {}


def set_progress(plan_id: str, **fields) -> None:
    state = _PROGRESS.setdefault(plan_id, {})
    state.update(fields)
    state["updated_at"] = time.time()


def get_progress(plan_id: str) -> dict:
    return dict(_PROGRESS.get(plan_id) or {})


def clear_progress(plan_id: str) -> None:
    _PROGRESS.pop(plan_id, None)
