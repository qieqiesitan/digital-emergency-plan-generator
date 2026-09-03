"""风险评估报告四色分布图渲染服务。"""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from app.models.enterprise import EnterpriseFloor
from app.models.risk_management import RiskZone, RiskObject
from app.services.risk_mapping_service import (
    LEVEL_COLORS,
    effective_color,
    max_risk_level,
    normalize_polygon,
)

logger = logging.getLogger(__name__)

CANVAS_W, CANVAS_H = 1200, 900
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def hex_to_rgba(color: str | None, alpha: int = 255) -> tuple[int, int, int, int]:
    c = (color or "#d9d9d9").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        rgb = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        rgb = (217, 217, 217)
    return (rgb[0], rgb[1], rgb[2], alpha)


def polygon_points_to_pixels(points: list[dict], width: int = CANVAS_W, height: int = CANVAS_H) -> list[tuple[int, int]]:
    out = []
    for p in points:
        x = max(0.0, min(100.0, float(p.get("x", 0))))
        y = max(0.0, min(100.0, float(p.get("y", 0))))
        out.append((int(x / 100 * width), int(y / 100 * height)))
    return out


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return None


def render_four_color_png(floor: dict, zones: list[dict], risk_points: list[dict],
                          out_path: str, font_path: str | None = None) -> None:
    """在 1200x900 画布上绘制单层四色分布图（zones/points 坐标为 0-100 百分比）。"""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "#ffffff")
    # 底图（可选）
    base = floor.get("floor_plan_url")
    if base:
        try:
            # floor_plan_url 形如 /uploads/...；由调用方换算为本地绝对路径传入
            local = floor.get("_floor_plan_local")
            if local and Path(local).exists():
                bg = Image.open(local).convert("RGB")
                bg = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
                img.paste(bg, (0, 0))
        except Exception as e:
            logger.warning("four-color floor plan load failed: %s", e)
    draw = ImageDraw.Draw(img, "RGBA")
    font = _load_font(22) if font_path is None else None
    if font_path:
        try:
            font = ImageFont.truetype(font_path, 22)
        except Exception:
            font = None
    font_small = _load_font(13) if font is not None else None

    for z in zones:
        fill = hex_to_rgba(z.get("effective_color"), alpha=110)
        for poly in z.get("polygons", []):
            pts = polygon_points_to_pixels(poly.get("points", []))
            if len(pts) < 3:
                continue
            draw.polygon(pts, fill=fill, outline=hex_to_rgba(z.get("effective_color"), 255))
            if font is not None:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                label = poly.get("label") or z.get("name", "")
                draw.text((cx - 30, cy - 12), label, fill=(30, 30, 30, 255), font=font)

    for p in risk_points:
        px = int(max(0.0, min(100.0, float(p.get("x", 50)))) / 100 * CANVAS_W)
        py = int(max(0.0, min(100.0, float(p.get("y", 50)))) / 100 * CANVAS_H)
        r = 10
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(22, 119, 255, 255), outline="#ffffff")
        if font_small is not None:
            draw.text((px + 12, py - 8), p.get("name", ""), fill=(20, 20, 20, 255), font=font_small)

    # 标题与图例
    if font is not None:
        draw.text((24, 18), f"{floor.get('name', '')} 四色分布图", fill=(20, 20, 20, 255), font=font)
        legend = [("重大风险", LEVEL_COLORS.get("重大", "#ff4d4f")),
                  ("较大风险", LEVEL_COLORS.get("较大", "#fa8c16")),
                  ("一般风险", LEVEL_COLORS.get("一般", "#fadb14")),
                  ("低风险", LEVEL_COLORS.get("低", "#52c41a"))]
        ly = CANVAS_H - 48
        for label, color in legend:
            draw.rectangle((CANVAS_W - 240, ly, CANVAS_W - 220, ly + 16), fill=hex_to_rgba(color))
            draw.text((CANVAS_W - 212, ly - 2), label, fill=(20, 20, 20, 255), font=font_small)
            ly += 24

    img.save(out_path, "PNG")


def four_color_images_markdown(images: list[dict]) -> str:
    lines = []
    for im in images:
        title = f"{im.get('floor_name', '')} 四色分布图"
        lines.append(f"![{title}]({im.get('url', '')})")
    return "\n\n".join(lines)


def insert_figure_block(content: str, block: str, marker_title: str) -> str:
    """把 block 插入到 “## {marker_title}” 之前；找不到标题则追加文末；已含 block 则幂等跳过。"""
    if not block:
        return content
    if block in content:
        return content
    marker = f"## {marker_title}"
    idx = content.find(marker)
    if idx == -1:
        return content.rstrip() + "\n\n" + block + "\n"
    return content[:idx].rstrip() + "\n\n" + block + "\n\n" + content[idx:]


def _uploads_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "uploads"


async def render_enterprise_four_color_images(enterprise_id: str, db) -> list[dict]:
    """按楼层渲染四色图 PNG；无楼层/分区时返回 []。写入 uploads 并返回 url 列表。"""
    floors = (await db.execute(
        select(EnterpriseFloor)
        .where(EnterpriseFloor.enterprise_id == enterprise_id)
        .order_by(EnterpriseFloor.sort_order)
    )).scalars().all()
    if not floors:
        return []
    zones = (await db.execute(
        select(RiskZone).where(RiskZone.enterprise_id == enterprise_id)
    )).scalars().all()
    points = (await db.execute(
        select(RiskObject).where(
            RiskObject.enterprise_id == enterprise_id,
            RiskObject.is_risk_point.is_(True),
        )
    )).scalars().all()

    by_floor: dict[str, list[RiskZone]] = {}
    for z in zones:
        by_floor.setdefault(z.floor_id, []).append(z)

    base_dir = _uploads_dir() / "enterprises" / enterprise_id / "four-color"
    base_dir.mkdir(parents=True, exist_ok=True)
    images: list[dict] = []
    for floor in floors:
        fzones = by_floor.get(floor.id, [])
        if not fzones:
            continue
        zdata = []
        for z in fzones:
            level = max_risk_level(z)
            color = effective_color(z.floor_plan_polygon, level)
            polygon = normalize_polygon(z.floor_plan_polygon, z.name)
            zdata.append({
                "name": z.name,
                "effective_color": color,
                "polygons": (polygon or {}).get("polygons", []),
            })
        pdata = [
            {"name": p.name, "x": p.location_x, "y": p.location_y}
            for p in points if p.floor_id == floor.id
        ]
        out = base_dir / f"{floor.id}.png"
        try:
            render_four_color_png(
                {"name": floor.name, "floor_plan_url": floor.floor_plan_url,
                 "_floor_plan_local": _resolve_floor_plan_local(floor.floor_plan_url)},
                zdata, pdata, str(out),
            )
        except Exception as e:
            logger.error("four-color render failed floor=%s: %s", floor.id, e)
            continue
        images.append({
            "floor_id": floor.id,
            "floor_name": floor.name,
            "url": f"/uploads/enterprises/{enterprise_id}/four-color/{floor.id}.png",
        })
    return images


def _resolve_floor_plan_local(url: str | None):
    if not url or not url.startswith("/uploads/"):
        return None
    return str(_uploads_dir() / url[len("/uploads/"):])
