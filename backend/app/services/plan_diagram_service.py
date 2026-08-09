"""预案附图数据绘制服务：风险矩阵、平面疏散图、占位符。"""

import html as _html

VIEW_W, VIEW_H = 1000, 700

LEVEL_TO_NUM = {
    "很低": 1, "低": 2, "一般": 3, "较大": 4, "重大": 5,
}


def _esc(v) -> str:
    """转义 SVG 文本内容。"""
    return _html.escape(str(v), quote=True)


def _to_int(v, default: int) -> int:
    """L/S 数值化：数字 / 中文等级 / 缺省均容忍。"""
    if isinstance(v, str) and v.strip() in LEVEL_TO_NUM:
        return LEVEL_TO_NUM[v.strip()]
    try:
        return min(max(int(float(v)), 1), 5)
    except (TypeError, ValueError):
        return default


def make_placeholder(key: str, reason: str) -> dict:
    return {"key": key, "placeholder": True, "reason": reason}


def build_risk_matrix_svg(risk_events: list) -> dict:
    """5×5 L×S 风险矩阵热力图。risk_events: [{name, likelihood, severity, risk_level}]"""
    events = []
    for e in risk_events:
        l = _to_int(e.get("likelihood"), 0)
        s = _to_int(e.get("severity"), 0)
        if l and s:
            events.append({**e, "_l": l, "_s": s})
    if not events:
        return make_placeholder("risk_matrix", "missing_risk_events")

    level_colors = {"重大": "#d4380d", "较大": "#fa8c16", "一般": "#fadb14", "低": "#91d5ff"}
    cell = 96
    origin_x, origin_y = 100, 560  # 行向上：y = origin_y - (i+1)*cell，顶部 y=80 与标题不重叠
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="0 0 1000 700">',
             '<rect width="1000" height="700" fill="#fff"/>',
             '<text x="500" y="40" text-anchor="middle" font-size="20" font-weight="bold">风险矩阵图（可能性 L × 严重度 S）</text>']

    for i in range(5):
        for j in range(5):
            x = origin_x + j * cell
            y = origin_y - (i + 1) * cell
            score = (i + 1) * (j + 1)
            color = "#ffccc7" if score >= 15 else "#ffd591" if score >= 9 else "#fff1b8" if score >= 4 else "#e6f7ff"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{color}" stroke="#d9d9d9"/>')

    for i in range(5):
        parts.append(f'<text x="{origin_x - 30}" y="{origin_y - i*cell - cell/2 + 5}" text-anchor="middle" font-size="14">S{i+1}</text>')
        parts.append(f'<text x="{origin_x + i*cell + cell/2}" y="{origin_y + 25}" text-anchor="middle" font-size="14">L{i+1}</text>')

    for e in events:
        x = origin_x + (e["_l"] - 1) * cell + cell / 2
        y = origin_y - e["_s"] * cell + cell / 2
        color = level_colors.get(e.get("risk_level", ""), "#333")
        parts.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="10" fill="#fff">{_esc(e.get("name", ""))}</text>')

    parts.append("</svg>")
    return {"key": "risk_matrix", "placeholder": False, "svg": "\n".join(parts)}


def _parse_points(pts_raw) -> list:
    """兼容 [{"x":..,"y":..}, ...] 与 [[x,y], ...] 两种 points 形态。"""
    pts = []
    for pt in pts_raw or []:
        if isinstance(pt, dict) and pt.get("x") is not None and pt.get("y") is not None:
            pts.append((float(pt["x"]), float(pt["y"])))
        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                pts.append((float(pt[0]), float(pt[1])))
            except (TypeError, ValueError):
                continue
    return pts


def _to_view(x: float, y: float) -> tuple[float, float]:
    """0-100 坐标 → 1000×700 视口（留边距）。"""
    return 60 + x / 100 * 880, 40 + y / 100 * 620


def build_evacuation_svg(floor_plan_url, zones, objects, resources) -> dict:
    """厂区平面疏散图：底图（如有）+ 分区 + 风险点 + 疏散标注。"""
    has_geometry = bool(zones) or bool(objects)
    if not has_geometry:
        return make_placeholder("evacuation", "missing_floor_data")

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="0 0 1000 700">',
             '<rect width="1000" height="700" fill="#fafafa"/>',
             '<text x="500" y="30" text-anchor="middle" font-size="18" font-weight="bold">厂区平面疏散示意图</text>']
    if floor_plan_url:
        parts.append(f'<image href="{_esc(floor_plan_url)}" x="60" y="40" width="880" height="620" preserveAspectRatio="xMidYMid meet" opacity="0.35"/>')

    zone_colors = ["#ffccc7", "#ffd591", "#fff1b8", "#e6f7ff"]
    for idx, z in enumerate(zones):
        poly = z.get("floor_plan_polygon") or z.get("polygon") or {}
        for p in poly.get("polygons", []):
            pts_raw = p.get("points", []) if isinstance(p, dict) else []
            pts = _parse_points(pts_raw)
            if len(pts) < 3:
                continue
            mapped = " ".join(f"{_to_view(x, y)[0]:.1f},{_to_view(x, y)[1]:.1f}" for x, y in pts)
            color = zone_colors[idx % len(zone_colors)]
            parts.append(f'<polygon points="{mapped}" fill="{color}" stroke="#999" stroke-width="2"/>')
            cx = sum(x for x, y in pts) / len(pts)
            cy = sum(y for x, y in pts) / len(pts)
            vx, vy = _to_view(cx, cy)
            parts.append(f'<text x="{vx}" y="{vy}" text-anchor="middle" font-size="13">{_esc(z.get("name", ""))}</text>')

    for o in objects:
        x, y = _to_view(o.get("location_x") or 50, o.get("location_y") or 50)
        parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#d4380d"/>')
        parts.append(f'<text x="{x + 12}" y="{y + 4}" font-size="12">{_esc(o.get("name", ""))}</text>')

    ex, ey = _to_view(85, 10)
    parts.append(f'<rect x="{ex-30}" y="{ey-30}" width="60" height="60" fill="#52c41a" rx="8"/>')
    parts.append(f'<text x="{ex}" y="{ey+4}" text-anchor="middle" font-size="11" fill="#fff">集合点</text>')
    for r in resources:
        if r.get("category") in ("消防", "灭火"):
            rx, ry = _to_view(10, 10)
            parts.append(f'<rect x="{rx-14}" y="{ry-14}" width="28" height="28" fill="#fa541c" rx="5"/>')
            parts.append(f'<text x="{rx}" y="{ry+4}" text-anchor="middle" font-size="9" fill="#fff">{_esc(r.get("name", "消防"))}</text>')
            break

    parts.append("</svg>")
    return {"key": "evacuation", "placeholder": False, "svg": "\n".join(parts)}
