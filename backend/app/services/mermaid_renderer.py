"""
Mermaid diagram renderer using Playwright.
Renders Mermaid code blocks to PNG images for embedding in exported docx files.
Uses a shared singleton browser instance and local Mermaid.js for reliability.
"""
import hashlib
import io
import logging
import os
import re
import html as html_mod
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

# In-memory render cache: mermaid_hash -> PNG bytes
_cache: dict[str, bytes] = {}

# Shared browser state
_browser = None
_playwright = None
_browser_lock = asyncio.Lock()

# Local Mermaid.js path
_MERMAID_JS_PATH = Path(__file__).parent / "mermaid.min.js"

# HTML template for rendering - inline local mermaid.js
_RENDER_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { margin: 20px; background: white; font-family: sans-serif; }
.mermaid { text-align: center; }
.error { color: #999; font-size: 14px; padding: 40px; text-align: center; }
</style>
</head>
<body>
<div class="mermaid">
__MERMAID_CODE__
</div>
<div id="status"></div>
<script>
__MERMAID_JS__
</script>
<script>
mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "loose" });
(async function() {
  try {
    const element = document.querySelector(".mermaid");
    const graphDefinition = element.textContent.trim();
    const { svg } = await mermaid.render("mermaid-svg", graphDefinition);
    document.getElementById("status").innerHTML = svg;
  } catch (err) {
    document.getElementById("status").innerHTML =
      '<div class="error">Mermaid rendering failed: ' + err.message + '</div>';
  }
})();
</script>
</body>
</html>"""

# Pre-load mermaid.js once at module level
_merMAID_JS_CACHED: str | None = None


def _load_mermaid_js() -> str:
    """Load the local Mermaid.js file content (cached)."""
    global _merMAID_JS_CACHED
    if _merMAID_JS_CACHED is not None:
        return _merMAID_JS_CACHED
    if _MERMAID_JS_PATH.exists():
        _merMAID_JS_CACHED = _MERMAID_JS_PATH.read_text(encoding="utf-8")
        logger.info("Loaded local mermaid.js (%d bytes)", len(_merMAID_JS_CACHED))
        return _merMAID_JS_CACHED
    logger.warning("mermaid.min.js not found, using CDN fallback")
    _merMAID_JS_CACHED = ""
    return ""


async def _get_browser():
    """Get or create the shared browser instance."""
    global _browser, _playwright

    async with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed")
            return None

        if _playwright is None:
            _playwright = await async_playwright().start()

        _browser = await _playwright.chromium.launch(headless=True)
        logger.info("Shared Chromium browser launched")
        return _browser


async def _close_browser():
    """Close the shared browser (call on app shutdown)."""
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


def _extract_mermaid_code(html_content: str) -> list[str]:
    """Extract all Mermaid code blocks from HTML content."""
    pattern = r'<code class="language-mermaid">(.*?)</code>'
    matches = re.findall(pattern, html_content, re.DOTALL)
    return [html_mod.unescape(m.strip()) for m in matches if m.strip()]


def _mermaid_hash(code: str) -> str:
    """Generate a stable hash for a Mermaid code block."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


async def render_mermaid_png(code: str, retries: int = 3) -> bytes:
    """Render a single Mermaid code block to PNG bytes with retries."""
    h = _mermaid_hash(code)
    if h in _cache:
        return _cache[h]

    mermaid_js = _load_mermaid_js()
    if not mermaid_js:
        # Fallback to CDN script tag
        mermaid_js = ""
        cdn_fallback = '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
    else:
        cdn_fallback = ""

    html_content = (
        _RENDER_TEMPLATE
        .replace("__MERMAID_JS__", mermaid_js or cdn_fallback)
        .replace("__MERMAID_CODE__", html_mod.escape(code))
    )

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            browser = await _get_browser()
            if browser is None:
                raise RuntimeError("Browser not available")

            page = await browser.new_page(viewport={"width": 900, "height": 600})

            try:
                await page.set_content(html_content, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_selector("#status:not(:empty)", timeout=15000)
                await page.wait_for_timeout(300)

                svg_el = await page.query_selector("#status svg")
                if svg_el:
                    element = await page.query_selector("#status")
                    png_bytes = (
                        await element.screenshot(type="png")
                        if element
                        else await page.screenshot(type="png", full_page=True)
                    )
                else:
                    error_text = await page.inner_text("#status")
                    raise RuntimeError(f"Mermaid render error: {error_text[:200]}")
            finally:
                await page.close()

            _cache[h] = png_bytes
            logger.info("Mermaid rendered %s (%d bytes)", h, len(png_bytes))
            return png_bytes

        except Exception as e:
            last_error = e
            logger.warning(
                "Mermaid render attempt %d/%d failed: %s",
                attempt, retries, str(e)[:150],
            )
            if attempt < retries:
                await asyncio.sleep(1)

    raise RuntimeError(f"Mermaid render failed after {retries} attempts") from last_error



async def render_mermaid_svg(code: str, retries: int = 3) -> str:
    """Render a single Mermaid code block to SVG string (for caching)."""
    h = _mermaid_hash(code)

    mermaid_js = _load_mermaid_js()
    if not mermaid_js:
        raise RuntimeError("mermaid.min.js not available")

    html_content = (
        _RENDER_TEMPLATE
        .replace("__MERMAID_JS__", mermaid_js)
        .replace("__MERMAID_CODE__", html_mod.escape(code))
    )

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            browser = await _get_browser()
            if browser is None:
                raise RuntimeError("Browser not available")

            page = await browser.new_page(viewport={"width": 900, "height": 600})

            try:
                await page.set_content(html_content, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_selector("#status:not(:empty)", timeout=15000)
                await page.wait_for_timeout(300)

                svg_el = await page.query_selector("#status svg")
                if svg_el:
                    svg_text = await svg_el.evaluate("el => el.outerHTML")
                else:
                    error_text = await page.inner_text("#status")
                    raise RuntimeError(f"Mermaid render error: {error_text[:200]}")
            finally:
                await page.close()

            logger.info("Mermaid SVG rendered %s (%d chars)", h, len(svg_text))
            return svg_text

        except Exception as e:
            last_error = e
            logger.warning(
                "Mermaid SVG render attempt %d/%d failed: %s",
                attempt, retries, str(e)[:150],
            )
            if attempt < retries:
                await asyncio.sleep(1)

    raise RuntimeError(f"Mermaid SVG render failed after {retries} attempts") from last_error


async def render_svg_to_png(svg_content: str) -> bytes:
    """Render a pre-rendered SVG string to PNG bytes (fast, no Mermaid.js needed)."""
    svg_hash = hashlib.sha256(svg_content.encode("utf-8")).hexdigest()[:16]
    if svg_hash in _cache:
        return _cache[svg_hash]

    svg_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>body {{ margin: 20px; background: white; }}</style></head>
<body>{svg_content}</body></html>"""

    browser = await _get_browser()
    if browser is None:
        raise RuntimeError("Browser not available")

    page = await browser.new_page(viewport={"width": 900, "height": 600})
    try:
        await page.set_content(svg_html, wait_until="domcontentloaded", timeout=10000)
        await page.wait_for_selector("svg", timeout=5000)
        await page.wait_for_timeout(200)

        svg_el = await page.query_selector("svg")
        if svg_el:
            png_bytes = await svg_el.screenshot(type="png")
        else:
            raise RuntimeError("SVG element not found in page")
    finally:
        await page.close()

    _cache[svg_hash] = png_bytes
    logger.info("SVG→PNG rendered %s (%d bytes)", svg_hash, len(png_bytes))
    return png_bytes


def extract_mermaid_from_markdown(md_text: str) -> list[str]:
    """Extract Mermaid code blocks from raw Markdown text."""
    pattern = r'```mermaid\s*\n(.*?)```'
    matches = re.findall(pattern, md_text, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]

def _placeholder_png(message: str = "render failed") -> bytes:
    """Generate a simple placeholder PNG."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
            b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    img = Image.new("RGB", (600, 100), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("simhei.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 35), message, fill=(153, 153, 153), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def replace_mermaid_with_placeholders(html_content: str) -> tuple[str, list[str]]:
    """Replace Mermaid code blocks in HTML with nothing."""
    pattern = r'(?:<pre>)?<code class="language-mermaid">.*?</code>(?:</pre>)?'
    codes = _extract_mermaid_code(html_content)
    cleaned = re.sub(pattern, "", html_content, flags=re.DOTALL)
    return cleaned, codes
