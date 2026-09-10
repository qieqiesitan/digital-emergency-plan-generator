"""化学品库字段富集 CLI。

用法：
  python backend/tools/enrich_chemical_library.py --from-db --limit 30 --out-dir /tmp/smoke
  python backend/tools/enrich_chemical_library.py --from-db --out-dir backend
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.tools.chemical_enrichment.chemblink import parse_product_page
from backend.tools.chemical_enrichment.fetch import CachedFetcher
from backend.tools.chemical_enrichment.merge import FIELDS, merge_sources
from backend.tools.chemical_enrichment.pubchem import parse_pug_view
from backend.tools.chemical_enrichment.sqlgen import write_outputs

PUBCHEM_CID = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{cas}/cids/JSON"
PUBCHEM_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
CHEMBLINK_PAGE = "https://www.chemblink.com/zh/products/{cas}C.htm"
REPORT_PATH = Path("docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md")
SQL_NAME = "db_migration_20260910_chemical_library_enrich.sql"
JSON_NAME = "chemical_library_enrichment_20260910.json"


def load_rows_from_db() -> list:
    sql = ("SELECT id::text || chr(9) || name || chr(9) || cas_no FROM chemical_library "
           "WHERE cas_no IS NOT NULL AND cas_no <> '' ORDER BY id")
    out = subprocess.run(
        ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
         "-d", "emergency_plan", "-tAc", sql],
        capture_output=True, text=True, encoding="utf-8", check=True)
    return [line.split("\t") for line in out.stdout.splitlines() if line.strip()]


def resolve_pubchem(fetcher: CachedFetcher, cas: str) -> tuple:
    cid = json.loads(fetcher.text(PUBCHEM_CID.format(cas=cas)))["IdentifierList"]["CID"][0]
    record = json.loads(fetcher.text(PUBCHEM_VIEW.format(cid=cid)))
    return parse_pug_view(record), cid


def collect_record(fetcher: CachedFetcher, cas: str) -> tuple:
    """分别抓取两个源：单源失败仍返回另一源的数据，两个都失败才视为失败。"""
    chemblink: dict = {}
    pubchem: dict = {}
    errors: list = []
    try:
        chemblink = parse_product_page(fetcher.text(CHEMBLINK_PAGE.format(cas=cas)))
    except Exception as exc:
        errors.append(f"chemblink: {exc}")
    try:
        pubchem, _cid = resolve_pubchem(fetcher, cas)
    except Exception as exc:
        errors.append(f"pubchem: {exc}")
    return chemblink, pubchem, errors


def build_report(rows: list, results: list, failed: list, conflicts: list,
                 same_cas_groups: list, partial: list = None) -> str:
    partial = partial or []
    total = len(rows)
    lines = [
        "# 化学品库字段富集报告（2026-09-10）",
        "",
        f"- 条目总数：{total}",
        f"- 成功富集：{len(results)}",
        f"- 抓取失败：{len(failed)}",
        f"- 仅单源成功（部分字段）：{len(partial)}",
        f"- 双源冲突（相关字段已留空）：{len(conflicts)}",
        "",
        "## 字段覆盖率",
        "",
        "| 字段 | 有值条数 | 占比 |",
        "|---|---|---|",
    ]
    for field in FIELDS:
        filled = sum(1 for r in results if (r["values"].get(field) or "").strip())
        lines.append(f"| {field} | {filled} | {filled * 100 / max(total, 1):.1f}% |")
    lines += ["", "## 抓取失败清单", ""]
    lines += [f"- {f['name']}（{f['cas']}）：{f['error']}" for f in failed[:200]] or ["- 无"]
    lines += ["", "## 双源冲突清单（相关字段已留空）", ""]
    lines += [f"- {c['name']}（{c['cas']}）：{', '.join(c['fields'])}" for c in conflicts[:200]] or ["- 无"]
    lines += ["", "## 单源成功清单（另一源失败）", ""]
    lines += [f"- {p['name']}（{p['cas']}）：{'; '.join(p['errors'])}" for p in partial[:200]] or ["- 无"]
    lines += ["", "## 同 CAS 多规格条目（共享同一组数值）", ""]
    lines += [f"- CAS {cas}：{', '.join(names)}" for cas, names in same_cas_groups[:200]] or ["- 无"]
    lines += [
        "", "## 人工复核抽样（前 30 条，源链接见 ChemBlink）", "",
        "| 品名 | CAS | UN号 | 物理状态 | 闪点 | 沸点 | 密度 | 源链接 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in results[:30]:
        values = row["values"]
        lines.append(
            f"| {row['name']} | {row['cas']} | {values.get('un_no', '')} | "
            f"{values.get('physical_state', '')} | {values.get('flash_point', '')} | "
            f"{values.get('boiling_point', '')} | {values.get('density', '')} | "
            f"[ChemBlink](https://www.chemblink.com/zh/products/{row['cas']}C.htm) |")
    return "\n".join(lines) + "\n"


def process_rows(rows: list, collect_fn, workers: int = 4, progress_every: int = 100,
                 log=print) -> tuple:
    """并发抓取 + 解析；结果严格按输入顺序返回（失败行跳过并单独记录）。"""
    def job(item):
        _index, (row_id, name, cas) = item
        try:
            chemblink, pubchem, errors = collect_fn(cas)
        except Exception as exc:  # 兜底：单行异常不影响整体
            chemblink, pubchem, errors = {}, {}, [str(exc)[:200]]
        return row_id, name, cas, chemblink, pubchem, errors

    results, failed, partial, conflicts = [], [], [], []
    total = len(rows)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for done, (row_id, name, cas, chemblink, pubchem, errors) in enumerate(
                pool.map(job, list(enumerate(rows))), 1):
            if not chemblink and not pubchem:
                failed.append({"id": row_id, "name": name, "cas": cas,
                               "error": "; ".join(errors)[:200]})
            else:
                if errors:
                    partial.append({"id": row_id, "name": name, "cas": cas, "errors": errors})
                merged = merge_sources(chemblink, pubchem)
                if merged["conflicts"]:
                    conflicts.append({"id": row_id, "name": name, "cas": cas,
                                      "fields": merged["conflicts"]})
                results.append({"id": row_id, "name": name, "cas": cas,
                                "values": {field: merged[field] for field in FIELDS}})
            if progress_every and done % progress_every == 0:
                log(f"progress {done}/{total}")
    return results, failed, partial, conflicts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", help="TSV：id\\tname\\tcas（与 --from-db 二选一）")
    parser.add_argument("--from-db", action="store_true")
    parser.add_argument("--out-dir", default="backend")
    parser.add_argument("--cache-dir", default=".cache/chemical_enrichment")
    parser.add_argument("--report", default=str(REPORT_PATH))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if args.from_db:
        rows = load_rows_from_db()
    else:
        rows = [line.split("\t") for line in
                Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    fetcher = CachedFetcher(Path(args.cache_dir))
    results, failed, partial, conflicts = process_rows(
        rows, lambda cas: collect_record(fetcher, cas), workers=args.workers)

    out = Path(args.out_dir)
    write_outputs(results, out / SQL_NAME, out / "data" / JSON_NAME)
    grouped: dict = {}
    for row in results:
        grouped.setdefault(row["cas"], []).append(row["name"])
    same_cas = [(cas, names) for cas, names in grouped.items() if len(names) > 1]
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(rows, results, failed, conflicts, same_cas, partial),
                           encoding="utf-8", newline="\n")
    print(f"rows={len(rows)} enriched={len(results)} failed={len(failed)} "
          f"conflicts={len(conflicts)}")


if __name__ == "__main__":
    main()
