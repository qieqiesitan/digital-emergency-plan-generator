"""antd `List` 与 `SimpleList` 的度量对照（真浏览器）。

前提：dev 服务器提供临时对照页 /src/list-parity.html（跑完即删）。
对比项：每个列表项及其子树元素的相对盒子 + 关键计算样式（padding/margin/border/
字号/字重/颜色/行高/display/flex）。
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PARITY_BASE", "http://localhost:5173")
OUT = os.environ.get("PARITY_OUT", os.path.join("output", "_pt"))
CASES = list(range(1, 14))
TOL = 0.6

COLLECT = """
(cid) => {
  const sec = document.querySelector('section[data-case="' + cid + '"]');
  if (!sec) return null;
  const grab = (impl) => {
    const root = sec.querySelector('[data-impl="' + impl + '"]');
    const rr = root.getBoundingClientRect();
    const r1 = (v) => Math.round(v * 10) / 10;
    const rel = (el) => {
      const b = el.getBoundingClientRect();
      return { x: r1(b.x - rr.x), y: r1(b.y - rr.y), w: r1(b.width), h: r1(b.height) };
    };
    const sty = (el) => {
      const cs = getComputedStyle(el);
      return [cs.display, cs.alignItems, cs.justifyContent,
              cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft,
              cs.marginTop, cs.marginRight, cs.marginBottom, cs.marginLeft,
              cs.borderBottomWidth, cs.fontSize, cs.fontWeight, cs.color,
              cs.lineHeight, cs.textAlign, cs.flex].join('|');
    };
    const ul = root.querySelector('ul');
    const items = ul ? [...ul.children].map((it) => ({
      tag: it.tagName,
      box: rel(it),
      sty: sty(it),
      text: (it.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 40),
      inner: [...it.querySelectorAll('*')].map((e) => ({ tag: e.tagName, box: rel(e), sty: sty(e) })),
    })) : [];
    const pick = (suffix) => {
      const el = root.querySelector('[class*="' + suffix + '"]');
      return el ? { tag: el.tagName, box: rel(el), sty: sty(el) } : null;
    };
    return {
      rootH: r1(rr.height),
      items,
      header: pick('header'),
      empty: pick('empty-text'),
      spin: !!root.querySelector('[class*="spin"]'),
    };
  };
  return { antd: grab('antd'), simple: grab('simple') };
}
"""

PROPS = ["display", "alignItems", "justifyContent", "padT", "padR", "padB", "padL",
         "marT", "marR", "marB", "marL", "borderB", "fontSize", "fontWeight",
         "color", "lineHeight", "textAlign", "flex"]


def cmp_box(a, b, label, diffs):
    for k in ("x", "y", "w", "h"):
        if abs(a[k] - b[k]) > TOL:
            diffs.append(f"{label}.{k}: antd={a[k]} simple={b[k]}")


def cmp_style(sa, sb, label, diffs):
    if sa == sb:
        return
    for n, x, y in zip(PROPS, sa.split("|"), sb.split("|")):
        if x != y:
            diffs.append(f"{label}.{n}: antd={x} simple={y}")


def compare(data):
    diffs = []
    a, s = data["antd"], data["simple"]
    if len(a["items"]) != len(s["items"]):
        diffs.append(f"项数不同: antd={len(a['items'])} simple={len(s['items'])}")
    for i, (ia, is_) in enumerate(zip(a["items"], s["items"])):
        if ia["tag"] != is_["tag"]:
            diffs.append(f"item[{i}] 标签不同: {ia['tag']} vs {is_['tag']}")
        cmp_box(ia["box"], is_["box"], f"item[{i}].box", diffs)
        cmp_style(ia["sty"], is_["sty"], f"item[{i}]", diffs)
        if len(ia["inner"]) != len(is_["inner"]):
            diffs.append(f"item[{i}] 子树元素数不同: antd={len(ia['inner'])} simple={len(is_['inner'])}")
        for j, (ea, es) in enumerate(zip(ia["inner"], is_["inner"])):
            if ea["tag"] != es["tag"]:
                diffs.append(f"item[{i}].inner[{j}] 标签不同: {ea['tag']} vs {es['tag']}")
                continue
            cmp_box(ea["box"], es["box"], f"item[{i}].inner[{j}]({ea['tag']}).box", diffs)
            cmp_style(ea["sty"], es["sty"], f"item[{i}].inner[{j}]({ea['tag']})", diffs)
    for key in ("header", "empty"):
        pa, ps = a[key], s[key]
        if (pa is None) != (ps is None):
            diffs.append(f"{key} 存在性不同: antd={bool(pa)} simple={bool(ps)}")
        elif pa and ps:
            cmp_box(pa["box"], ps["box"], f"{key}.box", diffs)
            cmp_style(pa["sty"], ps["sty"], f"{key}", diffs)
    if abs(a["rootH"] - s["rootH"]) > 2.0:
        diffs.append(f"根高度差: antd={a['rootH']} simple={s['rootH']}")
    return diffs


def main():
    rows = []
    console = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")

        def on_console(msg):
            if msg.type in ("error", "warning"):
                console.append(msg.text[:300])

        page.on("console", on_console)
        page.goto(f"{BASE}/src/list-parity.html", wait_until="networkidle", timeout=60000)
        page.wait_for_selector("section[data-case='1']", timeout=30000)
        page.screenshot(path=os.path.join(OUT, "list-parity-full.png"), full_page=True)
        for cid in CASES:
            data = page.evaluate(COLLECT, cid)
            if not data:
                print(f"!! case {cid}: 未渲染")
                rows.append({"case": cid, "status": "missing", "diffs": []})
                continue
            diffs = compare(data)
            rows.append({"case": cid, "status": "pass" if not diffs else "fail",
                         "diffs": diffs[:12], "antdH": data["antd"]["rootH"],
                         "simpleH": data["simple"]["rootH"], "items": len(data["antd"]["items"])})
            flag = "OK " if not diffs else "!! "
            print(f"{flag}case {cid:2d}  items={len(data['antd']['items'])} "
                  f"h(antd/simple)={data['antd']['rootH']}/{data['simple']['rootH']} diffs={len(diffs)}",
                  flush=True)
            for d in diffs[:8]:
                print(f"      - {d}")
        browser.close()
    with open(os.path.join(OUT, "list-parity.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    bad = [r for r in rows if r["status"] != "pass"]
    print(f"\n==== 对照汇总：{len(rows)} 组；不一致 {len(bad)} 组：{[r['case'] for r in bad]}")
    dep = [c for c in console if "deprecated" in c]
    print(f"==== 页面 console 告警/错误：{len(console)} 条（其中弃用类 {len(dep)}）")
    for c in console[:5]:
        print(f"      ! {c}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
