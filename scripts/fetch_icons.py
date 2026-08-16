#!/usr/bin/env python3
"""Fetch chosen iconfont icons as cleaned local SVG assets (build-time only).

Calls the iconfont.cn public search API (no key), picks icons by id from
MAPPING, strips presentation noise and writes
frontend/src/assets/icons/<name>.svg.

The search API sorts by updated_at, so hit positions drift over time; we
paginate (up to MAX_PAGES pages of PAGE_SIZE) until every needed id for a
term is found, and retry transient failures up to 3 times.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://www.iconfont.cn/api/icon/search.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

# name -> (search term, iconfont id)  —— 与设计文档 §4.3 映射表一致
MAPPING = {
    "archive": ("档案", 1490623),
    "org": ("组织架构", 29865223),
    "geo": ("地图", 2076231),
    "chem": ("危化品", 13209754),
    "risk": ("风险管控", 32835841),
    "hazard": ("隐患排查", 12820186),
    "rescue": ("应急资源", 45446276),
    "assessment": ("风险评估", 3759366),
    "investigation": ("调查", 4423489),
    "plan-manage": ("应急预案", 8625443),
    "dashboard": ("工作台", 7215957),
    "enterprise": ("企业", 11239041),
    "plan-list": ("应急预案", 2959108),
    "regulations": ("法规", 8329617),
    "data-dict": ("数据字典", 1680700),
    "prompt": ("对话", 2286510),
    "ai": ("机器人", 5387814),
    "law": ("法律", 7991666),
    "standard": ("标准", 3207743),
    "policy": ("政策", 12031078),
    "topic": ("书本", 3522456),
    "safety": ("安全帽", 3029239),
    "notice": ("通知", 577374),
    "location": ("定位", 11372652),
}

OUT_DIR = "frontend/src/assets/icons"
FILL_RE = re.compile(r'\sfill="#[0-9a-fA-F]{3,8}"')
FILL_RGB_RE = re.compile(r'\sfill="rgb\([^"]*\)"')
MAX_PAGES = 5
PAGE_SIZE = 60


def clean_svg(svg: str) -> str:
    svg = re.sub(r' class="[^"]*"', "", svg)
    svg = re.sub(r' style="[^"]*"', "", svg)
    svg = re.sub(r' version="[^"]*"', "", svg)
    svg = FILL_RE.sub("", svg)
    svg = FILL_RGB_RE.sub("", svg)
    return svg


def search(q: str, page: int = 1, limit: int = PAGE_SIZE) -> list[dict]:
    params = {
        "q": q,
        "sortType": "updated_at",
        "page": str(page),
        "pageSize": str(limit),
        "sType": "",
        "fromCollection": "1",
        "fills": "",
        "ctoken": "null",
        "line": "1",
        "fill": "",
        "flat": "",
        "hand": "",
        "simple": "",
        "complex": "",
        "t": str(int(time.time() * 1000)),
    }
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 200:
        raise RuntimeError(
            f"iconfont api error: code={data.get('code')} msg={data.get('message')}"
        )
    return data.get("data", {}).get("icons", [])


def fetch_all() -> dict[str, str]:
    cache: dict[str, list[dict]] = {}
    assets: dict[str, str] = {}
    for name, (term, icon_id) in MAPPING.items():
        if term not in cache:
            needed = {i for n, (t, i) in MAPPING.items() if t == term}
            hits: list[dict] = []
            for attempt in range(3):
                try:
                    for page in range(1, MAX_PAGES + 1):
                        page_hits = search(term, page)
                        hits.extend(page_hits)
                        found = {h.get("id") for h in hits}
                        if needed.issubset(found):
                            break
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        raise
            cache[term] = hits
        hit = next((i for i in cache[term] if i.get("id") == icon_id), None)
        if not hit or not hit.get("show_svg"):
            raise RuntimeError(f"icon {name} (id={icon_id}) not found for term {term!r}")
        assets[name] = clean_svg(hit["show_svg"])
    return assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and clean iconfont SVG assets.")
    parser.add_argument("--verify", action="store_true", help="verify existing assets")
    args = parser.parse_args()

    if args.verify:
        missing = [n for n in MAPPING if not os.path.isfile(f"{OUT_DIR}/{n}.svg")]
        if missing:
            print("MISSING:", ", ".join(missing))
            return 1
        for name in MAPPING:
            raw = open(f"{OUT_DIR}/{name}.svg", encoding="utf-8").read()
            if not raw.strip() or 'fill="#' in raw or 'class="' in raw or ' style="' in raw:
                print("DIRTY:", name)
                return 1
        print(f"OK: {len(MAPPING)} assets verified")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    assets = fetch_all()
    for name, svg in assets.items():
        with open(f"{OUT_DIR}/{name}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"written: {OUT_DIR}/{name}.svg")
    print(f"total: {len(assets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
