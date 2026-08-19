#!/usr/bin/env python3
"""Search iconfont.cn public API and optionally download SVG icons/illustrations.

Unofficial public API; no login or API key required. May be rate-limited or
change without notice. Designed for design-time icon selection; production
code should use locally stored SVG assets instead of hot-linking.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ICON_ENDPOINT = "https://www.iconfont.cn/api/icon/search.json"
ILLUSTRATION_ENDPOINT = "https://www.iconfont.cn/api/illustration/search.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
)
REFERER = "https://www.iconfont.cn/"
STYLE_FILTERS = ["line", "fill", "flat", "hand", "simple", "complex"]


def build_params(args):
    params = {
        "q": args.q,
        "sortType": args.sort,
        "page": "1",
        "pageSize": str(max(1, min(60, args.limit))),
        "sType": "",
        "fromCollection": "1",
        "fills": "0" if args.fills == "line" else ("1" if args.fills == "fill" else ""),
        "ctoken": "null",
    }
    for name in STYLE_FILTERS:
        params[name] = "1" if getattr(args, name) else ""
    params["t"] = str(int(time.time() * 1000))
    return params


def post(url, params):
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_svg(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": REFERER,
            "Accept": "image/svg+xml,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def to_abs(url):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.iconfont.cn" + url
    if url.startswith(("http://", "https://")):
        return url
    return "https://" + url


def safe_filename(name, icon_id):
    stem = re.sub(r'[\\/:*?"<>|\s]+', "-", name).strip("-") or str(icon_id)
    return f"{stem}-{icon_id}.svg"


def main():
    parser = argparse.ArgumentParser(
        description="Search iconfont.cn public API and optionally download SVG icons."
    )
    parser.add_argument("q", help="搜索关键词，中文效果最好")
    parser.add_argument("--limit", type=int, default=10, help="返回数量 1-60，默认 10")
    parser.add_argument(
        "--type",
        choices=["icon", "illustration"],
        default="icon",
        help="icon=UI 单色图标；illustration=场景插画",
    )
    parser.add_argument(
        "--sort", choices=["updated_at", "popular"], default="updated_at"
    )
    parser.add_argument(
        "--fills",
        choices=["all", "line", "fill"],
        default="all",
        help="线条/面性筛选",
    )
    for name in STYLE_FILTERS:
        parser.add_argument(
            f"--{name}", action="store_true", help=f"{name} 风格筛选"
        )
    parser.add_argument(
        "--out-dir", help="下载 SVG 到该目录（不传则仅打印结果）"
    )
    parser.add_argument("--json", action="store_true", help="同时输出完整 JSON")
    args = parser.parse_args()

    endpoint = ILLUSTRATION_ENDPOINT if args.type == "illustration" else ICON_ENDPOINT
    try:
        data = post(endpoint, build_params(args))
    except Exception as exc:
        print(f"搜索失败: {exc}", file=sys.stderr)
        print(
            "提示：公开接口可能限流，稍后重试；或改用用户提供的 iconfont 项目/CDN 链接。",
            file=sys.stderr,
        )
        sys.exit(2)

    if data.get("code") != 200:
        print(
            f"接口返回错误 code={data.get('code')} msg={data.get('message')}",
            file=sys.stderr,
        )
        sys.exit(2)

    icons = data.get("data", {}).get("icons", [])
    total = data.get("data", {}).get("count", 0)
    results = []
    for item in icons:
        if args.type == "illustration":
            svg = None
            origin = item.get("origin_file") or ""
            if "svg" in origin.lower():
                try:
                    svg = fetch_svg(to_abs(origin))
                except Exception:
                    svg = None
            results.append(
                {
                    "type": "illustration",
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "svg": svg,
                    "preview_image": item.get("preview_image"),
                }
            )
        else:
            results.append(
                {
                    "type": "icon",
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "font_class": item.get("font_class"),
                    "unicode": item.get("unicode"),
                    "fills": item.get("fills"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "svg": item.get("show_svg"),
                    "preview_image": item.get("preview_image"),
                }
            )

    print(f"共 {total} 个结果，返回 {len(results)} 条")
    for item in results:
        detail = (
            f"font_class={item['font_class']}"
            if item["type"] == "icon"
            else f"尺寸={item['width']}x{item['height']}"
        )
        print(
            f"- id={item['id']} 名称={item['name']} {detail} "
            f"svg={'有' if item.get('svg') else '无'}"
        )

    if args.json:
        print(json.dumps({"total": total, "hits": results}, ensure_ascii=False, indent=2))

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for item in results:
            if not item.get("svg"):
                continue
            path = os.path.join(args.out_dir, safe_filename(item["name"], item["id"]))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(item["svg"])
            print(f"已保存: {path}")


if __name__ == "__main__":
    main()
