import asyncio, time
from app.services.prompt_cache import ensure_loaded, _cache, _loaded_at, get_diagram_prompt

async def test():
    t0 = time.time()
    await ensure_loaded()
    print(f"ensure_loaded: {time.time()-t0:.1f}s")
    print(f"Cache categories: {list(_cache.keys())}")
    for cat in _cache:
        print(f"  {cat}: {len(_cache[cat])} templates")
    for dt in ['flowchart TD', 'sequenceDiagram', 'pie', 'mindmap', 'graph TD', 'graph LR']:
        p = get_diagram_prompt(dt)
        status = "FOUND" if p else "NOT FOUND"
        preview = p[:60] if p else ""
        print(f"get_diagram_prompt({dt}): {status} {preview}")

asyncio.run(test())
