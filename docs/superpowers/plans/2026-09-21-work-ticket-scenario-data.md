# 作业票措施条件数据化 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把 8 个票种的措施条件映射搬到数据文件，改标准文本后重跑一次即同步；锚定改用措施正文（标准修订插入条文时不会错判）；前端作业情景按票种渲染（修掉用户反馈的"情景不跟着票种变"）。

**架构：** `work_ticket_conditions.yaml`（唯一事实源，与标准文本并列）→ 生成器按正文锚定产出两张表的种子 SQL → 运行时从表加载映射与情景定义（进程内缓存）→ `/templates` 响应带出该票种的 `scenario_fields` → 前端按票种渲染。两条硬规则：映射失配即报错中止；未映射措施落 `unknown`。

**技术栈：** Python 3 / PyYAML / pytest / PostgreSQL 16 / FastAPI / React + AntD

**依据规格：** `docs/superpowers/specs/2026-09-21-work-ticket-scenario-data-design.md`

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/tools/gen_work_ticket_conditions.py`（创建） | 一次性辅助：内置紧凑映射表 + 从库读措施正文 → 产出初版 YAML |
| `backend/app/regulations/data/work_ticket_conditions.yaml`（创建） | 唯一事实源：条件定义、每票种情景项、逐条措施映射（完整正文） |
| `backend/seed_work_ticket_conditions.py`（创建） | 生成器：YAML + 标准文本 → 种子 SQL + 覆盖报告；失配即报错 |
| `backend/db_migration_20260921_work_ticket_conditions.sql`（创建） | 两张表：`work_ticket_measure_conditions` / `work_ticket_scenarios` |
| `backend/app/services/work_ticket_condition_loader.py`（创建） | 从表加载映射与情景定义（TTL 缓存） |
| `backend/app/services/work_ticket_measure_rules.py`（修改） | 删掉硬编码的 `MEASURE_CONDITIONS`/`CONDITION_LABELS`，改为从 loader 取 |
| `backend/app/routers/work_ticket.py`（修改） | `/templates` 响应增加 `scenario_fields`；新增 `/scenarios` 兜底端点 |
| `frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`（修改） | 情景区按票种渲染、切票种清空勾选、自动项只读回显 |
| `frontend/src/types/workTicket.ts`（修改） | `WorkTicketTemplate.scenario_fields` |
| `backend/tests/test_work_ticket_condition_data.py`（创建） | 生成器、锚定稳定性、失配、未映射 |
| `backend/tests/test_work_ticket_measure_rules.py`（修改） | 改为注入式映射（不再依赖硬编码常量） |
| `output/playwright/e2e-20260921/scripts/_work_ticket_scenario_probe.py`（创建） | 8 票种逐个触发 `not_applicable` 的端到端探针 |

---

## 任务 1：条件数据文件（含初版生成辅助脚本）

**文件：**
- 创建：`backend/tools/gen_work_ticket_conditions.py`
- 生成：`backend/app/regulations/data/work_ticket_conditions.yaml`

- [ ] **步骤 1：编写辅助脚本（内置紧凑映射表）**

创建 `backend/tools/gen_work_ticket_conditions.py`。映射表来自规格 §5.10 逐条清单（下表 66 条），
措施正文由脚本从真库读取——**避免在代码里重复抄写 106 条条文**：

```python
"""一次性辅助脚本：按紧凑映射表 + 真库措施正文，产出初版 work_ticket_conditions.yaml。

为什么要有它：YAML 必须写措施完整正文（正文是锚定键），手抄 106 条易错；
本脚本按"票种 + 序号 → 条件"的紧凑表从库里取正文，生成后即成为人工维护的事实源。
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
    "DLZY": [],   # 唯一条件 night_work 为自动推断，无需人工勾选
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
        if key in seen:      # 同票种多级别共用同一批措施
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
                continue   # 固定措施不写入映射
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
```

- [ ] **步骤 2：运行脚本产出 YAML**

```bash
python backend/tools/gen_work_ticket_conditions.py
head -30 backend/app/regulations/data/work_ticket_conditions.yaml
grep -c "^      - text:" backend/app/regulations/data/work_ticket_conditions.yaml
```

预期：生成成功并打印 `66 条映射，40 个条件`；`grep -c` 输出 `66`（与规格统计一致）。

- [ ] **步骤 3：人工核对 YAML**

逐个票种核对：措施正文与标准文本一致（`grep` 对照库里同序号的文本）、条件键都在 `conditions:` 里定义过、
`scenario:` 只含人工勾选项（不含 `has_other_tickets` / `night_work` / `gas_welding` 等自动项）。

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -tA -c "SELECT count(*) FROM work_ticket_template_measures;"
grep -c "auto: null" backend/app/regulations/data/work_ticket_conditions.yaml
```

预期：措施总数 223（多级别共用）；`auto: null` 的行数 = 人工勾选条件数（28）。

- [ ] **步骤 4：Commit**

```bash
git add backend/tools/gen_work_ticket_conditions.py backend/app/regulations/data/work_ticket_conditions.yaml
git commit -m "feat(work-ticket): 措施条件数据文件 + 初版生成辅助脚本（8 票种 66 条映射）"
```

---

## 任务 2：条件键工具 + 生成器（含失配报错）

**文件：**
- 创建：`backend/app/services/work_ticket_condition_loader.py`（本任务先只写工具函数部分）
- 创建：`backend/seed_work_ticket_conditions.py`
- 测试：`backend/tests/test_work_ticket_condition_data.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_work_ticket_condition_data.py`：

```python
"""条件键工具 + 生成器的锚定规则。"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _loader():
    from app.services.work_ticket_condition_loader import (
        measure_ref,
        normalize_measure_text,
    )

    return normalize_measure_text, measure_ref


def _generator():
    spec = importlib.util.spec_from_file_location(
        "wt_cond_gen", ROOT / "backend" / "seed_work_ticket_conditions.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_normalize_strips_whitespace_and_converts_fullwidth():
    normalize, _ = _loader()
    assert normalize("动火点 30m 内　垂直空间") == normalize("动火点30m内垂直空间")
    assert normalize("（试行）") == normalize("(试行)")


def test_normalize_is_stable_for_punctuation_tail():
    normalize, _ = _loader()
    assert normalize("措施一；") == normalize("措施一")


def test_measure_ref_is_deterministic_and_short():
    _, ref = _loader()
    a = ref("与动火设备相连接的所有管线已断开")
    assert a == ref(" 与动火设备相连接的所有管线已断开 ")
    assert len(a) == 32
    assert a != ref("与动火设备相连接的所有管线已断开，加盲板")


def test_generator_covers_eight_types_and_matches_spec_count():
    mod = _generator()
    sql, report = mod.build_sql()
    assert report["mapped_total"] == 66, report
    assert set(report["by_ticket"]) == {"DHZY", "YXKJ", "MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY"}
    assert report["unmapped_total"] == 40, report
    assert "work_ticket_measure_conditions" in sql


def test_generator_missing_yaml_text_raises(tmp_path, monkeypatch):
    """YAML 里的措施正文在标准文本中找不到 → 必须报错中止，不能静默丢弃。"""
    mod = _generator()
    monkeypatch.setattr(mod, "_load_yaml", lambda: {
        "conditions": {"dummy": {"label": "假条件", "auto": None}},
        "tickets": {"DHZY": {"scenario": ["dummy"],
                             "measures": [{"text": "这条措施在标准文本里根本不存在", "conditions": ["dummy"]}]}},
    })
    with pytest.raises(RuntimeError, match="失配"):
        mod.build_sql()


def test_generator_reports_unmapped_measures():
    """标准文本里有、YAML 未映射的措施必须进入未映射清单。"""
    mod = _generator()
    _, report = mod.build_sql()
    assert len(report["unmapped"]) > 0
    assert all({"ticket_type", "sort_order", "text"} <= set(item) for item in report["unmapped"])


def test_generator_anchor_survives_reordering():
    """锚定稳定性：措施顺序打乱后，映射仍指向同一正文。"""
    mod = _generator()
    sql_a, _ = mod.build_sql()
    shuffled = mod._parse_all_measures(shuffle_seed=7)
    sql_b, _ = mod.build_sql(measures_override=shuffled)
    refs_a = sorted(line.split("'")[3] for line in sql_a.splitlines()
                    if line.startswith("INSERT INTO work_ticket_measure_conditions "))
    refs_b = sorted(line.split("'")[3] for line in sql_b.splitlines()
                    if line.startswith("INSERT INTO work_ticket_measure_conditions "))
    assert refs_a == refs_b
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_work_ticket_condition_data.py -q`

预期：collection error（`work_ticket_condition_loader` / `seed_work_ticket_conditions` 不存在）。

- [ ] **步骤 3：实现条件键工具**

创建 `backend/app/services/work_ticket_condition_loader.py` 的工具部分：

```python
"""措施条件的键工具与运行时加载。

规范化规则（锚定与查找共用同一函数，见规格 §4）：去空白、全角转半角、去尾部标点。
刻意不做模糊匹配与同义词替换——把"改了字的另一条措施"错认成同一条，正是要避免的静默错判。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_TAIL_PUNCT = "。；;.，,、"


def normalize_measure_text(text: str) -> str:
    """规范化措施正文：去空白 + 全角转半角 + 去尾部标点。"""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.rstrip(_TAIL_PUNCT)


def measure_ref(text: str) -> str:
    """措施正文的稳定锚点（规范化后的 sha256 前 32 位）。"""
    digest = hashlib.sha256(normalize_measure_text(text).encode("utf-8")).hexdigest()
    return digest[:32]
```

- [ ] **步骤 4：实现生成器**

创建 `backend/seed_work_ticket_conditions.py`（要点）：

```python
"""生成措施条件种子 SQL：YAML（事实源）+ 标准文本（措施正文）→ SQL + 覆盖报告。

两条硬规则（规格 §3）：
  1. 失配即报错中止：YAML 里的措施正文在标准文本里找不到 → RuntimeError（列出失配条目）
  2. 未映射即 unknown：标准文本里有、YAML 未映射 → 写入报告，运行时落 unknown（绝不猜）

用法：python backend/seed_work_ticket_conditions.py
"""

from __future__ import annotations

import importlib.util
import json
import random
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_SQL = ROOT / "backend" / "db_migration_20260921_work_ticket_conditions.sql"
OUT_REPORT = ROOT / "backend" / "work_ticket_conditions_report.json"
YAML_PATH = ROOT / "backend" / "app" / "regulations" / "data" / "work_ticket_conditions.yaml"
STANDARD_TEXT = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
NS = uuid.NAMESPACE_URL
NS_PREFIX = "work-ticket/conditions/"
_CHAPTER_BY_CODE = {"DHZY": 5, "YXKJ": 6, "MBCD": 7, "GCZY": 8, "QZDZ": 9, "LSYD": 10, "PTZY": 11, "DLZY": 12}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _keys():
    return _load("wt_cond_keys", ROOT / "backend" / "app" / "services" / "work_ticket_condition_loader.py")


def _load_yaml() -> dict:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def _parse_all_measures(shuffle_seed: int | None = None) -> dict[str, list[dict]]:
    """从标准文本解析每票种措施（复用既有解析器），可选打乱顺序用于锚定回归测试。"""
    seed = _load("wt_seed", ROOT / "backend" / "app" / "services" / "work_ticket_seed_data.py")
    text = STANDARD_TEXT.read_text(encoding="utf-8")
    out: dict[str, list[dict]] = {}
    for code, chapter in _CHAPTER_BY_CODE.items():
        items = seed.parse_measures(text, chapter=chapter)
        if shuffle_seed is not None:
            rnd = random.Random(shuffle_seed)
            items = items[:]
            rnd.shuffle(items)
        out[code] = items
    return out


def _q(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{NS_PREFIX}{kind}/{key}"))


def build_sql(measures_override: dict | None = None) -> tuple[str, dict]:
    config = _load_yaml()
    conditions = config.get("conditions") or {}
    tickets = config.get("tickets") or {}
    measures = measures_override or _parse_all_measures()

    lines = [
        "-- 20260921 作业票措施条件映射（由 seed_work_ticket_conditions.py 生成，勿手改）",
        "-- 幂等：先按票种清理再插入。锚定键 measure_ref = 措施正文规范化后的 sha256 前 32 位。",
        "",
    ]
    by_ticket: dict[str, int] = {}
    unmapped: list[dict] = []
    missing: list[dict] = []

    for code, block in tickets.items():
        pool = measures.get(code, [])
        key_of = {_keys().measure_ref(m["measure_text"]): m for m in pool}
        ticket_refs: list[str] = []
        by_ticket[code] = 0
        lines.append(
            "DELETE FROM work_ticket_measure_conditions "
            f"WHERE ticket_type = {_q(code)};"
        )
        for item in block.get("measures") or []:
            ref = _keys().measure_ref(item["text"])
            hit = key_of.get(ref)
            if hit is None:
                missing.append({"ticket_type": code, "text": item["text"][:60]})
                continue
            ticket_refs.append(ref)
            for cond in item["conditions"]:
                lines.append(
                    "INSERT INTO work_ticket_measure_conditions "
                    "(id, ticket_type, measure_ref, sort_order, condition_key) VALUES "
                    f"({_q(_uid('cond', f'{code}/{ref}/{cond}'))}, {_q(code)}, {_q(ref)}, "
                    f"{hit['sort_order']}, {_q(cond)}) ON CONFLICT (id) DO NOTHING;"
                )
                by_ticket[code] += 1
        for measure in pool:
            if _keys().measure_ref(measure["measure_text"]) not in ticket_refs:
                unmapped.append(
                    {"ticket_type": code, "sort_order": measure["sort_order"],
                     "text": measure["measure_text"][:60]}
                )

    if missing:
        raise RuntimeError(
            "条件映射与标准文本失配（YAML 里的下列措施正文在标准文本中找不到）："
            + json.dumps(missing, ensure_ascii=False)
        )

    # 情景项定义
    lines.append("-- 情景项（人工勾选）定义")
    for code, block in tickets.items():
        lines.append(f"DELETE FROM work_ticket_scenarios WHERE ticket_type = {_q(code)};")
    lines.append("")

    report = {
        "by_ticket": by_ticket,
        "mapped_total": sum(by_ticket.values()),
        "unmapped_total": len(unmapped),
        "unmapped": unmapped,
        "conditions": len(conditions),
    }
    return "\n".join(lines) + "\n", report


def main() -> int:
    sql, report = build_sql()
    OUT_SQL.write_text(sql, encoding="utf-8", newline="\n")
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {OUT_SQL.name}：{report['mapped_total']} 条映射，"
          f"未映射 {report['unmapped_total']} 条（见 {OUT_REPORT.name}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

说明：实现时把 `work_ticket_scenarios` 的 INSERT 一并补齐（每票种按 `scenario` 列表写入
`condition_key` + 从 `conditions` 取 `label`/`auto`），并让 SQL 以 `BEGIN;`/`COMMIT;` 包裹。

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_work_ticket_condition_data.py -q`

预期：7 个用例全 PASSED（含失配报错、锚定乱序稳定、未映射清单）。

- [ ] **步骤 6：生成 SQL 并核验报告**

```bash
python backend/seed_work_ticket_conditions.py
cat backend/work_ticket_conditions_report.json | head -20
grep -c "INSERT INTO work_ticket_measure_conditions" backend/db_migration_20260921_work_ticket_conditions.sql
```

预期：`mapped_total = 66`、`unmapped_total = 40`；`grep -c` 输出 `66`。

- [ ] **步骤 7：Commit**

```bash
git add backend/app/services/work_ticket_condition_loader.py backend/seed_work_ticket_conditions.py backend/db_migration_20260921_work_ticket_conditions.sql backend/work_ticket_conditions_report.json backend/tests/test_work_ticket_condition_data.py
git commit -m "feat(work-ticket): 条件生成器（正文锚定 + 失配报错 + 未映射报告）"
```

---

## 任务 3：两张表迁移 + 运行时从表加载

**文件：**
- 创建：`backend/db_migration_20260921_work_ticket_conditions.sql`（已由任务 2 生成，此处补建表语句）
- 修改：`backend/app/services/work_ticket_condition_loader.py`（追加加载逻辑）
- 修改：`backend/app/services/work_ticket_measure_rules.py`（删硬编码，改注入）
- 测试：`backend/tests/test_work_ticket_measure_rules.py`（改注入式）

- [ ] **步骤 1：写建表语句并应用**

在生成 SQL 顶部（`BEGIN;` 之后）加入建表：

```sql
CREATE TABLE IF NOT EXISTS work_ticket_measure_conditions (
    id            UUID PRIMARY KEY,
    ticket_type   VARCHAR(20) NOT NULL,
    measure_ref   VARCHAR(64) NOT NULL,
    sort_order    INTEGER NOT NULL,
    condition_key VARCHAR(60) NOT NULL,
    UNIQUE (ticket_type, measure_ref, condition_key)
);
CREATE INDEX IF NOT EXISTS idx_wtmc_type ON work_ticket_measure_conditions(ticket_type);

CREATE TABLE IF NOT EXISTS work_ticket_scenarios (
    id            UUID PRIMARY KEY,
    ticket_type   VARCHAR(20) NOT NULL,
    condition_key VARCHAR(60) NOT NULL,
    label         VARCHAR(200) NOT NULL,
    auto_rule     VARCHAR(60) NULL,
    sort_order    INTEGER NOT NULL,
    UNIQUE (ticket_type, condition_key)
);
```

```powershell
python backend/seed_work_ticket_conditions.py
docker cp backend/db_migration_20260921_work_ticket_conditions.sql emergency-plan-db:/tmp/wt_cond.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 -f /tmp/wt_cond.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT ticket_type, count(*) FROM work_ticket_measure_conditions GROUP BY ticket_type ORDER BY ticket_type;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT ticket_type, count(*) FROM work_ticket_scenarios GROUP BY ticket_type ORDER BY ticket_type;"
```

预期：表创建成功；8 个票种各有映射（合计 66）；情景表行数 = 各票种人工勾选项数（动火 7 / 受限空间 6 / 盲板 6 / 高处 8 / 吊装 8 / 临电 6 / 动土 4 / 断路 0）。

- [ ] **步骤 2：追加运行时加载（含 TTL 缓存）**

在 `work_ticket_condition_loader.py` 追加：

```python
from sqlalchemy import select

CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, tuple[float, object]] = {}


def _now() -> float:
    import time

    return time.monotonic()


async def load_conditions(db) -> dict[tuple[str, str], tuple[str, ...]]:
    """{(ticket_type, measure_ref): (condition_key, ...)}，TTL 缓存 30 秒。"""
    cached = _CACHE.get("conditions")
    if cached and _now() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]  # type: ignore[return-value]
    from app.models.work_ticket_condition import WorkTicketMeasureCondition

    rows = (await db.execute(select(WorkTicketMeasureCondition))).scalars().all()
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        grouped.setdefault((row.ticket_type, row.measure_ref), []).append(row.condition_key)
    result = {key: tuple(value) for key, value in grouped.items()}
    _CACHE["conditions"] = (_now(), result)
    return result


async def load_scenarios(db, ticket_type: str) -> list[dict]:
    """该票种的情景区（只含人工勾选项，auto_rule 为空）。"""
    from app.models.work_ticket_condition import WorkTicketScenario

    rows = (
        await db.execute(
            select(WorkTicketScenario)
            .where(
                WorkTicketScenario.ticket_type == ticket_type,
                WorkTicketScenario.auto_rule.is_(None),
            )
            .order_by(WorkTicketScenario.sort_order)
        )
    ).scalars().all()
    return [{"key": r.condition_key, "label": r.label} for r in rows]


def invalidate_condition_cache() -> None:
    """重跑生成器并入库后调用（或等 30 秒自动过期）。"""
    _CACHE.clear()
```

并新增模型文件 `backend/app/models/work_ticket_condition.py`（两张表的 ORM，字段与迁移一致）。

- [ ] **步骤 3：改造 `work_ticket_measure_rules`**

删掉硬编码的 `MEASURE_CONDITIONS`，改为注入：

```python
def suggest_measures(
    measures: Sequence[Any],
    context: MeasureContext,
    *,
    conditions_map: Mapping[tuple[str, str], Sequence[str]] | None = None,
    labels: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """conditions_map 缺省时用调用方注入的表数据；无映射的措施落 unknown。"""
```

映射查询键改为 `(context.ticket_type, measure_ref(measure_text))`——**与生成器同一套锚定**。

- [ ] **步骤 4：改测试为注入式**

`test_work_ticket_measure_rules.py` 的既有用例改为显式传 `conditions_map`/`labels`（不再依赖模块常量），
并新增一例：**同一批措施换个顺序，判定结果不变**（锚定稳定性的服务层回归锁）。

- [ ] **步骤 5：跑测试**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -k "work_ticket" -q
backend\.venv\Scripts\python.exe -m ruff check backend/app backend/tests --output-format=concise
```

预期：work_ticket 相关全绿；ruff 全绿。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/work_ticket_condition.py backend/app/services/work_ticket_condition_loader.py backend/app/services/work_ticket_measure_rules.py backend/db_migration_20260921_work_ticket_conditions.sql backend/tests/test_work_ticket_measure_rules.py
git commit -m "feat(work-ticket): 条件映射入库 + 运行时按正文锚点加载（TTL 缓存）"
```

---

## 任务 4：接口（templates 带出情景项 + 兜底端点）

**文件：**
- 修改：`backend/app/routers/work_ticket.py`
- 测试：`backend/tests/test_work_ticket_api.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
def test_templates_expose_scenario_fields():
    """每个模板要带出该票种的人工勾选情景项，前端才能按票种渲染。"""
    field = MagicMock()
    field.field_key = "space_location"
    field.label = "受限空间名称及位置"
    field.field_type = "text"
    field.group_name = "作业内容"
    field.is_required = True
    field.options = {}
    field.allow_ai_prefill = False
    field.sort_order = 1
    template = MagicMock()
    template.id = "tpl-yxkj"
    template.code = "YXKJ"
    template.name = "受限空间安全作业票"
    template.level = None
    template.is_graded = False
    template.fields = [field]
    template.measures = []

    def _scenario_row(key: str, label: str, order: int):
        row = MagicMock()
        row.ticket_type = "YXKJ"
        row.condition_key = key
        row.label = label
        row.sort_order = order
        row.auto_rule = None
        return row

    calls = {"n": 0}

    async def handler(stmt, *a, **k):
        calls["n"] += 1
        # 查询顺序：1=templates 2=flows 3=nodes 4=scenarios
        # （若实现里调整了顺序，同步调整这里的计数）
        if calls["n"] == 1:
            return _Result([template])
        if calls["n"] == 4:
            return _Result([
                _scenario_row("hazardous_residue", "受限空间盛装过有毒/可燃物料", 1),
                _scenario_row("rotating_equipment", "内部有转动设备", 2),
            ])
        return _Result([])

    client = _client(handler)
    resp = client.get("/api/v1/work-ticket/templates")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["scenario_fields"] == [
        {"key": "hazardous_residue", "label": "受限空间盛装过有毒/可燃物料"},
        {"key": "rotating_equipment", "label": "内部有转动设备"},
    ]


def test_scenarios_endpoint_returns_only_manual_items():
    """兜底端点只返回人工勾选项（auto_rule 为空），自动项不出现在情景区。"""
    row = MagicMock()
    row.ticket_type = "YXKJ"
    row.condition_key = "hazardous_residue"
    row.label = "受限空间盛装过有毒/可燃物料"
    row.auto_rule = None
    row.sort_order = 1

    async def handler(stmt, *a, **k):
        return _Result([row])

    client = _client(handler)
    resp = client.get("/api/v1/work-ticket/scenarios", params={"ticket_type": "YXKJ"})
    assert resp.status_code == 200
    assert resp.json()["data"] == [
        {"key": "hazardous_residue", "label": "受限空间盛装过有毒/可燃物料"}
    ]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_work_ticket_api.py -q`

预期：新增两例 FAILED（`KeyError: scenario_fields` / 404）。

- [ ] **步骤 3：实现**

`list_templates` 中对每个模板补一个查询（或一次批量查询后按票种分组，避免 N+1）：

```python
    # 一次取出全部情景项，按票种分组（避免每模板一次查询）
    scenarios_by_type: dict[str, list[dict]] = {}
    scenario_rows = (
        await db.execute(
            select(WorkTicketScenario)
            .where(WorkTicketScenario.auto_rule.is_(None))
            .order_by(WorkTicketScenario.ticket_type, WorkTicketScenario.sort_order)
        )
    ).scalars().all()
    for row in scenario_rows:
        scenarios_by_type.setdefault(row.ticket_type, []).append(
            {"key": row.condition_key, "label": row.label}
        )
```

响应里每个模板增加：`"scenario_fields": scenarios_by_type.get(t.code, [])`。

新增兜底端点：

```python
@router.get("/scenarios")
async def api_scenarios(
    ticket_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """单查某票种的情景区（作业包等场景用）。"""
    return _ok(await load_scenarios(db, ticket_type))
```

- [ ] **步骤 4：跑测试**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_work_ticket_api.py -q
docker restart emergency-plan-backend   # 后端容器无 --reload，接口验证前必须重启
python output/playwright/e2e-20260920/scripts/_work_ticket_prefill_probe.py   # 既有探针确认预填未回归
```

预期：API 测试全绿；既有预填探针 11/11 仍通过。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/work_ticket.py backend/tests/test_work_ticket_api.py
git commit -m "feat(work-ticket): templates 带出票种情景项 + /scenarios 兜底端点"
```

---

## 任务 5：前端按票种渲染作业情景

**文件：**
- 修改：`frontend/src/types/workTicket.ts`
- 修改：`frontend/src/pages/Enterprise/WorkTicketNewPage.tsx`
- 测试：`frontend/src/components/enterprise/workTicket/scenarioScope.test.ts`（创建）

- [ ] **步骤 1：补类型与纯函数（含单测）**

`WorkTicketTemplate` 增加 `scenario_fields?: { key: string; label: string }[];`

把"按票种生成情景区"的逻辑抽成纯函数（便于单测，也避免组件文件混合导出）：

```ts
// frontend/src/components/enterprise/workTicket/scenarioScope.ts
import type { WorkTicketFieldDef } from "@/types/workTicket";

export interface ScenarioField {
  key: string;
  label: string;
}

/** 情景区随票种变化；无人工勾选项时返回空数组（界面据此显示提示文案）。 */
export function scenarioFieldsFor(
  template: { scenario_fields?: ScenarioField[] } | undefined,
  _fields?: WorkTicketFieldDef[],
): ScenarioField[] {
  return template?.scenario_fields ?? [];
}

/** 切票种时清空上一票种的情景勾选，只保留新票种声明的键。 */
export function pruneScenario(
  scenario: Record<string, boolean>,
  fields: ScenarioField[],
): Record<string, boolean> {
  const allowed = new Set(fields.map((f) => f.key));
  return Object.fromEntries(
    Object.entries(scenario).filter(([key]) => allowed.has(key)),
  );
}
```

创建 `scenarioScope.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { pruneScenario, scenarioFieldsFor } from "./scenarioScope";

describe("scenarioFieldsFor", () => {
  it("动火票返回 7 项", () => {
    const fields = scenarioFieldsFor({ scenario_fields: Array.from({ length: 7 }, (_, i) => ({ key: `k${i}`, label: `项${i}` })) });
    expect(fields).toHaveLength(7);
  });

  it("断路票没有人工勾选项", () => {
    expect(scenarioFieldsFor({ scenario_fields: [] })).toEqual([]);
  });

  it("模板缺失时返回空数组", () => {
    expect(scenarioFieldsFor(undefined)).toEqual([]);
  });
});

describe("pruneScenario", () => {
  it("切票种时丢弃不属于新票种的勾选", () => {
    const kept = pruneScenario(
      { hazardous_residue: true, internal_work: true },
      [{ key: "hazardous_residue", label: "x" }],
    );
    expect(kept).toEqual({ hazardous_residue: true });
  });

  it("空情景区清空全部勾选", () => {
    expect(pruneScenario({ internal_work: true }, [])).toEqual({});
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker exec emergency-plan-frontend npx vitest run src/components/enterprise/workTicket/scenarioScope.test.ts`

预期：模块不存在（FAILED）。

- [ ] **步骤 3：改造页面**

`WorkTicketNewPage.tsx`：

1. 删除硬编码的 `SCENARIO_FIELDS`，改为 `const scenarioFields = scenarioFieldsFor(template);`
2. 情景区渲染 `scenarioFields`；为空时显示：`本票种无需额外情景（如夜间照明要求由作业时段自动判定）`
3. 票种切换（`setTicketType` 处）追加 `setScenario((prev) => pruneScenario(prev, scenarioFieldsFor(下一模板)))`
4. 自动推断项只读回显（在情景区下方显示一行）：`系统自动判定：<label>` —— 数据来自模板响应新增的
   `auto_scenarios`（实现时在 `/templates` 一并带出 `auto_rule` 非空的项及其当前推断结果）
5. `scenarioParam` 的计算沿用现有逻辑（勾选=true；声明核实=false）

- [ ] **步骤 4：跑前端门禁**

```powershell
docker exec emergency-plan-frontend npx tsc -b --pretty false
docker exec emergency-plan-frontend npx vitest run
docker exec emergency-plan-frontend npx eslint src --max-warnings 0
docker exec emergency-plan-frontend npm run build
```

预期：tsc 0 / vitest 全绿（既有 321 + 新增 5）/ eslint 0 / build 成功。

- [ ] **步骤 5：同步到 8082**

```powershell
docker cp emergency-plan-frontend:/app/dist "output/_dist_sync"
docker cp "output/_dist_sync/." shuzihuayuan:/app/dist
[System.IO.Directory]::Delete('C:\Users\55061\Documents\数字化预案自动生成 2\output\_dist_sync', $true)
docker restart shuzihuayuan
```

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/workTicket.ts frontend/src/pages/Enterprise/WorkTicketNewPage.tsx frontend/src/components/enterprise/workTicket/scenarioScope.ts frontend/src/components/enterprise/workTicket/scenarioScope.test.ts
git commit -m "fix(work-ticket): 作业情景按票种渲染（不再固定 7 项动火情景）+ 切票种清空勾选"
```

---

## 任务 6：端到端验证（8 票种逐个触发判定）

**文件：**
- 创建：`output/playwright/e2e-20260921/scripts/_work_ticket_scenario_probe.py`

- [ ] **步骤 1：写接口层探针**

对 8 个票种各传一组"明确不涉及"的情景，断言 `not_applicable` 数量 > 0：

```python
SCENARIOS = {
    "DHZY": {"in_tank_area": False, "internal_work": False, "connected_pipeline": False,
             "surroundings_ignition": False, "has_flammable_lining": False,
             "surrounding_hazardous_ops": False, "height_work": False},
    "YXKJ": {"hazardous_residue": False, "connected_pipeline": False,
             "rotating_equipment": False, "flammable_atmosphere": False,
             "dust_inside": False, "corrosive_medium": False},
    "MBCD": {"toxic_medium": False, "explosion_hazard_area": False, "corrosive_medium": False,
             "high_temp_medium": False, "low_temp_medium": False, "multi_point_same_pipe": False},
    "GCZY": {"toxic_gas_area": False, "scaffold_used": False, "layered_work": False,
             "ladder_used": False, "light_shed": False, "load_bearing_plate": False,
             "night_or_poor_light": False, "outdoor": False},
    "QZDZ": {"hazardous_equipment_nearby": False, "building_as_anchor": False,
             "near_power_line": False, "pipe_as_anchor": False,
             "underground_facilities": False, "overhead_facilities": False,
             "explosion_hazard_area": False, "outdoor": False},
    "LSYD": {"explosion_hazard_area": False, "line_elevated": False, "cross_road": False,
             "line_along_surface": False, "underground_cable": False, "outdoor": False},
    "PTZY": {"underground_cable": False, "underground_pipeline": False,
             "on_road": False, "hazardous_area": False},
    "DLZY": {},
}
```

断言：
1. 每个有条件的票种 `not_applicable > 0`（断路依赖自动的 `night_work`，改由时段推导，单独断言）
2. **反向断言**：不传任何情景时每个票种 `not_applicable == 0`（保守策略未被破坏）
3. 情景项接口：`GET /scenarios?ticket_type=` 返回的项数与该票种 `scenario:` 声明一致（断路为 0）

- [ ] **步骤 2：跑探针并留证据**

```powershell
python output/playwright/e2e-20260921/scripts/_work_ticket_scenario_probe.py
```

预期：全绿，产出 `work-ticket-scenario-data.json`。

- [ ] **步骤 3：浏览器实测**

复用并扩展 `_work_ticket_prefill_browser_probe.py`：切票种后断言情景区文本变化（动火含"本次动火在设备内部"、
受限空间含"受限空间盛装过有毒/可燃物料"、断路显示"本票种无需额外情景"），并截图留档。

```powershell
python output/playwright/e2e-20260920/scripts/_work_ticket_prefill_browser_probe.py
```

预期：7/7 通过且新增的情景断言通过。

- [ ] **步骤 4：全量门禁**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests -q
backend\.venv\Scripts\python.exe -m ruff check backend/app backend/tests --output-format=concise
docker exec emergency-plan-frontend npx vitest run
python output/playwright/e2e-20260920/scripts/_work_ticket_regression_smoke.py
```

预期：后端全绿（2148 + 新增）；ruff 全绿；前端全绿；29 路由冒烟 0 pageerror / 0 5xx。

- [ ] **步骤 5：Commit + 推送**

```bash
git add output/playwright/e2e-20260921/scripts
git commit -m "test(probe): 8 票种情景判定端到端验证 + 证据"
git push origin master
git push gitee master
```

---

## 验收清单

- [ ] `work_ticket_conditions.yaml` 覆盖 8 个票种、66 条映射、40 条固定措施，且每条映射带完整措施正文
- [ ] 生成器：失配时报错中止（构造用例验证）；未映射清单写入 `work_ticket_conditions_report.json`
- [ ] 锚定稳定性：措施顺序打乱后映射指向同一正文（单测）
- [ ] 两张表已建、种子已入库：映射 66 条、情景项按票种分布（动火 7 / 受限空间 6 / 盲板 6 / 高处 8 / 吊装 8 / 临电 6 / 动土 4 / 断路 0）
- [ ] `/templates` 每个模板带 `scenario_fields`；`/scenarios` 兜底端点可用
- [ ] 代码里不再存在硬编码的 `MEASURE_CONDITIONS`（`rg "MEASURE_CONDITIONS" backend/app` 无命中）
- [ ] 前端：切票种时情景区随之变化；断路票显示"无需额外情景"；切票种清空上一票种勾选
- [ ] 8 票种各传情景后 `not_applicable > 0`；不传情景时 `not_applicable == 0`（保守策略保持）
- [ ] 后端 `pytest` + `ruff` 全绿；前端 `tsc -b` / `vitest` / `eslint` / `build` 全绿
- [ ] 浏览器实测：情景区随票种变化 + 既有 7 项断言仍通过
- [ ] 29 路由冒烟 0 pageerror / 0 5xx

## 不做（本计划范围外）

- 不做"系统自动发现 GB 修订并提示"的法规变更检测（用户已确认只要"重跑一次即同步"）
- 不做条件映射的 AI 自动生成（语义判断无文本依据）
- 不做管理界面在线编辑映射（映射与标准文本同源，走"改文件 + 重跑"）
- 不改票面法定字段与提交门禁语义
