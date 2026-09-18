"""生成作业票模板种子 SQL（确定性 UUID5，可重复执行）。

用法：python backend/seed_work_ticket_templates.py
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "db_migration_20260917_work_ticket_seed_v2.sql"
STANDARD_TEXT = (
    ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
)
NS = uuid.NAMESPACE_URL
NS_PREFIX = "work-ticket/GB30871-2022/"


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "wt_seed", ROOT / "backend" / "app" / "services" / "work_ticket_seed_data.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{NS_PREFIX}{kind}/{key}"))


def _q(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _bool(v: bool) -> str:
    return "TRUE" if v else "FALSE"


def build_sql() -> str:
    seed = _load_seed()
    text = STANDARD_TEXT.read_text(encoding="utf-8")

    lines = [
        "-- 20260917 作业票模板种子【增量 v2】：补齐至 8 类（GB 30871-2022 附录A/B）",
        "-- 增量说明：已按 v1 部署过的环境用本文件补齐；v2 内容包含 v1，",
        "-- 全部使用 ON CONFLICT (id) DO NOTHING，重复执行安全。",
        "-- 依据：GB 30871-2022 附录A（票面样式与措施）、附录B 表B.1（审批矩阵）。",
        "-- id 使用 uuid5(NAMESPACE_URL, 'work-ticket/GB30871-2022/<表>/<自然键>')。",
        "",
    ]

    for tpl in seed.TEMPLATES:
        tpl_key = f"{tpl['code']}/{tpl['level'] or 'NA'}"
        tpl_id = _uid("template", tpl_key)
        lines.append(
            "INSERT INTO work_ticket_templates "
            "(id, code, name, level, is_graded, standard_ref, is_enabled, sort_order) "
            f"VALUES ({_q(tpl_id)}, {_q(tpl['code'])}, {_q(tpl['name'])}, "
            f"{_q(tpl['level']) if tpl['level'] else 'NULL'}, {_bool(tpl['is_graded'])}, "
            f"{_q(seed.STANDARD_REF)}, TRUE, {seed.TEMPLATES.index(tpl)}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

        for idx, f in enumerate(tpl["fields"], start=1):
            fid = _uid("field", f"{tpl_key}/{f['field_key']}")
            options = f.get("options") or {}
            lines.append(
                "INSERT INTO work_ticket_template_fields "
                "(id, template_id, field_key, label, field_type, group_name, "
                "is_required, options, allow_ai_prefill, sort_order) VALUES "
                f"({_q(fid)}, {_q(tpl_id)}, {_q(f['field_key'])}, {_q(f['label'])}, "
                f"{_q(f['field_type'])}, {_q(f['group_name'])}, {_bool(f.get('is_required', False))}, "
                f"{_q(__import__('json').dumps(options, ensure_ascii=False))}::jsonb, "
                f"{_bool(f.get('allow_ai_prefill', False))}, {idx}) "
                "ON CONFLICT (id) DO NOTHING;"
            )

        parsed = seed.parse_measures(text, chapter=tpl["chapter"])
        if not parsed:
            raise RuntimeError(
                f"「{tpl['name']}」未能从第 {tpl['chapter']} 章解析出任何安全措施，"
                "请检查标准文本的表格结构是否被清洗脚本破坏"
            )
        for m in parsed:
            mid = _uid("measure", f"{tpl_key}/{m['sort_order']}")
            lines.append(
                "INSERT INTO work_ticket_template_measures "
                "(id, template_id, measure_text, article_anchor, is_mandatory, sort_order) "
                f"VALUES ({_q(mid)}, {_q(tpl_id)}, {_q(m['measure_text'])}, "
                f"{_q(m['article_anchor'])}, TRUE, {m['sort_order']}) "
                "ON CONFLICT (id) DO NOTHING;"
            )

        flow_id = _uid("flow", tpl_key)
        approver = next(
            (
                r["approver"]
                for r in seed.APPROVAL_MATRIX
                if r["code"] == tpl["code"] and r["level"] == tpl["level"]
            ),
            None,
        )
        lines.append(
            "INSERT INTO work_ticket_flow_templates (id, template_id, name, is_active) "
            f"VALUES ({_q(flow_id)}, {_q(tpl_id)}, {_q(tpl['name'] + ' 审批流程')}, TRUE) "
            "ON CONFLICT (id) DO NOTHING;"
        )
        if approver:
            node_id = _uid("node", f"{tpl_key}/approve")
            lines.append(
                "INSERT INTO work_ticket_flow_nodes "
                "(id, flow_template_id, node_key, name, sort_order, role_code, "
                "sign_policy, reject_to, is_statutory) VALUES "
                f"({_q(node_id)}, {_q(flow_id)}, 'approve', {_q(approver + '审批')}, 1, "
                f"{_q(approver)}, 'any', 'submitter', TRUE) "
                "ON CONFLICT (id) DO NOTHING;"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    sql = build_sql()
    OUT.write_text(sql, encoding="utf-8", newline="\n")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(sql.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
