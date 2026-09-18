"""GB 30871-2022 标准文本 OCR 讹字清洗。

背景：该 PDF 的文本层有系统性讹字——"式"全部被识成"怯"（30 处）、
罗马数字"Ⅱ"被识成"聂"（4 处）。不修就 seed 作业票措施库，
用户会在票面上看到"动火方怯"这类错字。

用法：
    python scripts/clean_gb30871_text.py            # 就地清洗（自动备份）
    python scripts/clean_gb30871_text.py --check    # 只检查不改
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
BACKUP_DIR = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "_backup"

# 讹字映射。只登记已确认的映射；新增必须附证据，不做猜测式替换。
REPLACEMENTS: dict[str, str] = {"怯": "式", "聂": "Ⅱ"}


def clean_text(text: str) -> str:
    out = text
    for bad, good in REPLACEMENTS.items():
        out = out.replace(bad, good)
    return out


def count_replacements(before: str) -> dict:
    return {f"{b}->{g}": before.count(b) for b, g in REPLACEMENTS.items() if before.count(b)}


def verify(text: str) -> dict:
    """判据。三项全 True 才算清洗干净。"""
    return {
        "has_zheng_shi": text.count("式") > 0,
        "no_qie": text.count("怯") == 0,
        "no_nie": text.count("聂") == 0,
    }


def clean_file(target: Path, *, backup_dir: Path | None = None, check_only: bool = False) -> dict:
    before = target.read_text(encoding="utf-8")
    after = clean_text(before)
    report = {
        "file": str(target),
        "replacements": count_replacements(before),
        "before_criteria": verify(before),
        "after_criteria": verify(after),
    }
    if check_only or before == after:
        return report
    backup_dir = backup_dir or BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_dir / target.name)
    target.write_text(after, encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查不改")
    parser.add_argument("--target", default=str(TARGET))
    args = parser.parse_args()

    report = clean_file(Path(args.target), check_only=args.check)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not all(report["after_criteria"].values()):
        print("判据未全部通过，请人工复核", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
