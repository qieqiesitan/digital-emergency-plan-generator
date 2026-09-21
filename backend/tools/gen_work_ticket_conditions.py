"""一次性辅助脚本：按紧凑映射表 + 真库措施正文，产出初版 work_ticket_conditions.yaml。

为什么要有它：YAML 必须写措施完整正文（正文是锚定键），手抄 106 条易错；
本脚本按「票种 + 序号 → 条件」的紧凑表从库里取正文，生成后即成为人工维护的事实源。
产物若已存在则拒绝覆盖（防止误删人工修改）。

用法（仓库根目录）：
    python backend/tools/gen_work_ticket_conditions.py            # 生成
    python backend/tools/gen_work_ticket_conditions.py --force    # 覆盖（慎用）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "app" / "regulations" / "data" / "work_ticket_conditions.yaml"
PSQL = [
    "docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
    "-d", "emergency_plan", "-tA", "-F", "|", "-c",
]

# 条件定义：auto 非空表示可自动推断（前端不展示为勾选项）
CONDITIONS: dict[str, dict[str, str | None]] = {
    "has_other_tickets": {"label": "本次作业还办理了其他特殊作业票", "auto": "tickets_in_batch"},
    "night_work": {"label": "作业时段涉及夜间（20:00~06:00）", "auto": "period_at_night"},
    # ── 动火 ──
    "internal_work": {"label": "本次动火在设备内部", "auto": None},
    "connected_pipeline": {"label": "作业设备连接有管线/阀门", "auto": None},
    "surroundings_ignition": {"label": "作业点周围有孔洞/窨井/地沟/污水井", "auto": None},
    "in_tank_area": {"label": "作业点在油气罐区防火堤内", "auto": None},
    "height_work": {"label": "本次作业涉及高处作业", "auto": None},
    "has_flammable_lining": {"label": "设备内有可燃物构件或防腐内衬", "auto": None},
    "surrounding_hazardous_ops": {"label": "作业点周围有装卸/排放/喷漆等危险作业", "auto": None},
    "gas_welding": {"label": "本次动火使用气焊/气割", "auto": "fire_method_gas"},
    "electric_welding": {"label": "本次动火使用电焊", "auto": "fire_method_electric"},
    # ── 受限空间 ──
    "hazardous_residue": {"label": "受限空间盛装过有毒/可燃物料", "auto": None},
    "rotating_equipment": {"label": "内部有转动设备", "auto": None},
    "flammable_atmosphere": {"label": "内部存在易燃易爆物料", "auto": None},
    "dust_inside": {"label": "内部存在大量扬尘", "auto": None},
    "corrosive_medium": {"label": "存在强腐蚀性介质", "auto": None},
    # ── 介质 / 场所（多票种复用）──
    "toxic_medium": {"label": "存在有毒介质", "auto": None},
    "explosion_hazard_area": {"label": "作业点在火灾爆炸危险场所", "auto": None},
    "high_temp_medium": {"label": "介质温度较高（可能烫伤）", "auto": None},
    "low_temp_medium": {"label": "介质温度较低（可能冻伤）", "auto": None},
    "multi_point_same_pipe": {"label": "同一管道多处同时抽堵", "auto": None},
    "hazardous_area": {"label": "作业点存在易燃易爆/有毒气体", "auto": None},
    # ── 高处 ──
    "toxic_gas_area": {"label": "作业点可能散发有毒气体", "auto": None},
    "scaffold_used": {"label": "现场搭设脚手架/防护网", "auto": None},
    "layered_work": {"label": "垂直分层作业", "auto": None},
    "ladder_used": {"label": "使用梯子/安全绳", "auto": None},
    "light_shed": {"label": "作业处有轻型棚", "auto": None},
    "load_bearing_plate": {"label": "在不承重物处作业并搭设承重板", "auto": None},
    "night_or_poor_light": {"label": "夜间作业或采光不足", "auto": None},
    "above_30m": {"label": "作业高度 30m 以上", "auto": "work_height_ge_30"},
    "outdoor": {"label": "露天作业", "auto": None},
    # ── 吊装 ──
    "level_1_or_2": {"label": "一、二级吊装作业", "auto": "lift_level_1_or_2"},
    "hazardous_equipment_nearby": {"label": "吊装场所含危险物料的设备/管道", "auto": None},
    "building_as_anchor": {"label": "以建筑物/构筑物作锚点", "auto": None},
    "near_power_line": {"label": "吊装范围附近有带电线路/架空线路", "auto": None},
    "pipe_as_anchor": {"label": "以管道/管架作吊装锚点", "auto": None},
    "underground_facilities": {"label": "吊装区域地下有电缆/管线/排水沟", "auto": None},
    "overhead_facilities": {"label": "吊装高度有管线/电缆桥架", "auto": None},
    # ── 临时用电 ──
    "line_elevated": {"label": "临时用电线路架高敷设", "auto": None},
    "cross_road": {"label": "线路跨越道路", "auto": None},
    "line_along_surface": {"label": "线路沿墙面或地面敷设", "auto": None},
    "underground_cable": {"label": "有暗管埋设/地下电缆", "auto": None},
    # ── 动土 ──
    "underground_pipeline": {"label": "地下有供排水/消防/工艺管线", "auto": None},
    "on_road": {"label": "在道路范围施工", "auto": None},
    "deep_excavation": {"label": "动土深度超过 1.2m", "auto": "dig_depth_gt_1_2"},
}

# 逐条映射（规格 §5.10）：票种 → 措施序号 → 条件键；未列出的序号 = 固定措施（不判定）
MAPPING: dict[str, dict[int, list[str]]] = {
    "DHZY": {
        1: ["internal_work"], 2: ["connected_pipeline"], 3: ["surroundings_ignition"],
        4: ["in_tank_area"], 5: ["height_work"], 6: ["has_flammable_lining"],
        7: ["gas_welding"], 9: ["electric_welding"],
        10: ["surrounding_hazardous_ops"], 11: ["surrounding_hazardous_ops"],
        12: ["has_other_tickets"], 13: ["gas_welding", "electric_welding"],
        15: ["has_other_tickets"],
    },
    "YXKJ": {
        1: ["hazardous_residue", "connected_pipeline"], 2: ["hazardous_residue"],
        4: ["rotating_equipment"], 5: ["flammable_atmosphere"], 7: ["hazardous_residue"],
        8: ["dust_inside"], 11: ["corrosive_medium"], 14: ["has_other_tickets"],
    },
    "MBCD": {
        2: ["toxic_medium"], 3: ["explosion_hazard_area"], 4: ["explosion_hazard_area"],
        5: ["corrosive_medium"], 6: ["high_temp_medium"], 7: ["low_temp_medium"],
        8: ["multi_point_same_pipe"], 9: ["has_other_tickets"],
    },
    "GCZY": {
        3: ["toxic_gas_area"], 5: ["scaffold_used"], 6: ["layered_work"],
        7: ["ladder_used"], 8: ["light_shed"], 9: ["load_bearing_plate"],
        10: ["night_or_poor_light"], 11: ["above_30m"], 13: ["outdoor"],
        14: ["has_other_tickets"],
    },
    "QZDZ": {
        1: ["level_1_or_2"], 2: ["hazardous_equipment_nearby"], 6: ["building_as_anchor"],
        7: ["near_power_line"], 8: ["pipe_as_anchor"], 12: ["underground_facilities"],
        14: ["overhead_facilities"], 16: ["near_power_line"],
        17: ["explosion_hazard_area"], 18: ["outdoor"], 19: ["has_other_tickets"],
    },
    "LSYD": {
        2: ["explosion_hazard_area"], 5: ["line_elevated"],
        6: ["line_along_surface", "cross_road"], 7: ["line_elevated"],
        8: ["underground_cable"], 9: ["outdoor"], 12: ["has_other_tickets"],
        13: ["explosion_hazard_area"],
    },
    "PTZY": {
        1: ["underground_cable"], 2: ["underground_pipeline"], 5: ["deep_excavation"],
        6: ["on_road"], 7: ["night_work"], 9: ["deep_excavation", "hazardous_area"],
        10: ["has_other_tickets"],
    },
    "DLZY": {3: ["night_work"]},
}

# 各票种要向用户展示的情景项（人工勾选；自动推断项不出现在这里）
SCENARIO: dict[str, list[str]] = {
    "DHZY": [
        "internal_work", "connected_pipeline", "surroundings_ignition", "in_tank_area",
        "height_work", "has_flammable_lining", "surrounding_hazardous_ops",
    ],
    "YXKJ": [
        "hazardous_residue", "connected_pipeline", "rotating_equipment",
        "flammable_atmosphere", "dust_inside", "corrosive_medium",
    ],
    "MBCD": [
        "toxic_medium", "explosion_hazard_area", "corrosive_medium",
        "high_temp_medium", "low_temp_medium", "multi_point_same_pipe",
    ],
    "GCZY": [
        "toxic_gas_area", "scaffold_used", "layered_work", "ladder_used", "light_shed",
        "load_bearing_plate", "night_or_poor_light", "outdoor",
    ],
    "QZDZ": [
        "hazardous_equipment_nearby", "building_as_anchor", "near_power_line",
        "pipe_as_anchor", "underground_facilities", "overhead_facilities",
        "explosion_hazard_area", "outdoor",
    ],
    "LSYD": [
        "explosion_hazard_area", "line_elevated", "cross_road",
        "line_along_surface", "underground_cable", "outdoor",
    ],
    "PTZY": ["underground_cable", "underground_pipeline", "on_road", "hazardous_area"],
    "DLZY": [],  # 唯一条件 night_work 为自动推断，无需人工勾选
}


def _measures_from_db() -> dict[str, dict[int, str]]:
    """从真库读每票种的措施正文：{code: {sort_order: text}}。"""
    sql = (
        "SELECT t.code, m.sort_order, m.measure_text "
        "FROM work_ticket_template_measures m "
        "JOIN work_ticket_templates t ON t.id = m.template_id "
        "ORDER BY t.code, m.sort_order;"
    )
    out: dict[str, dict[int, str]] = {}
    raw = subprocess.run(
        PSQL + [sql], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout
    seen: set[tuple[str, int]] = set()
    for line in raw.strip().splitlines():
        code, order, text = line.split("|", 2)
        key = (code, int(order))
        if key in seen:  # 同票种多级别共用同一批措施
            continue
        seen.add(key)
        out.setdefault(code, {})[int(order)] = text
    return out


def _yaml_escape(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def build_yaml() -> str:
    measures = _measures_from_db()
    lines = [
        "# 作业票措施条件映射（唯一事实源）。",
        "# 改这里 → 重跑 backend/seed_work_ticket_conditions.py → 同步入库；不需要改代码、不发版。",
        "# 锚定键 = 票种 + 措施正文（规范化后精确匹配），不用序号：标准修订插入条文时不会错判。",
        "# 正文必须完整——生成器失配会报错中止，不会静默放过。",
        "version: 1",
        "",
        "conditions:",
    ]
    for key, meta in CONDITIONS.items():
        lines.append(f"  {key}:")
        lines.append(f"    label: {_yaml_escape(str(meta['label']))}")
        auto = meta.get("auto")
        lines.append(f"    auto: {auto if auto else 'null'}")
    lines.append("")
    lines.append("tickets:")
    for code, scenario in SCENARIO.items():
        lines.append(f"  {code}:")
        if scenario:
            lines.append("    scenario:")
            for key in scenario:
                lines.append(f"      - {key}")
        else:
            lines.append("    scenario: []")
        lines.append("    measures:")
        for order in sorted(measures.get(code, {})):
            conds = MAPPING.get(code, {}).get(order)
            if not conds:
                continue  # 固定措施不写入映射
            text = measures[code][order]
            lines.append(f"      - text: {_yaml_escape(text)}")
            lines.append(f"        conditions: [{', '.join(conds)}]")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if OUT.exists() and not args.force:
        print(f"{OUT.relative_to(ROOT)} 已存在，拒绝覆盖（--force 可强制）")
        return 1
    content = build_yaml()
    OUT.write_text(content, encoding="utf-8", newline="\n")
    mapped = sum(len(v) for v in MAPPING.values())
    print(f"已生成 {OUT.relative_to(ROOT)}：{mapped} 条映射，{len(CONDITIONS)} 个条件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
