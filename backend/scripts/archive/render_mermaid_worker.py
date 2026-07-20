import sys, base64, os
from playwright.sync_api import sync_playwright

code = base64.b64decode(sys.argv[1]).decode("utf-8")
mermaid_js_path = os.path.join(os.path.dirname(__file__), "mermaid.min.js")
with open(mermaid_js_path, "r", encoding="utf-8") as f:
    mermaid_js = f.read()

import html as _h
code_escaped = _h.escape(code)
html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>
<div class="mermaid">{code_escaped}</div>
<div id="status"></div>
<script>{mermaid_js}</script>
<script>
mermaid.initialize({{startOnLoad:false,theme:"default",securityLevel:"loose"}});
mermaid.run().then(function(){{
  var svg = document.querySelector(".mermaid svg");
  if(svg) document.getElementById("status").innerHTML = svg.outerHTML;
}});
</script>
</body></html>'''

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    try:
        p = b.new_page(viewport={"width": 900, "height": 600})
        try:
            p.set_content(html, wait_until="domcontentloaded", timeout=15000)
            p.wait_for_selector("#status svg", timeout=15000)
            p.wait_for_timeout(300)
            el = p.query_selector("#status svg")
            if el:
                sys.stdout.buffer.write(el.screenshot(type="png"))
            else:
                sys.stderr.write("no svg")
                sys.exit(1)
        finally:
            p.close()
    finally:
        b.close()
