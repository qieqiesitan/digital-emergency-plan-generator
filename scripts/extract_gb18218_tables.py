"""GB 18218-2018 表1~表6 抽取脚本（可复现）。

用途：从标准正本 PDF 中提取「表1 危险化学品名称及其临界量」与
「表2 未在表1中列举的危险化学品临界量」，以及计算引擎所需的常量表
（表3 毒性气体校正系数 β、表4 类别校正系数 β、表5 暴露人员校正系数 α、表6 分级标准），
输出结构化 JSON + 校验报告。

背景：该 PDF 的文本层使用特殊字体编码 —— 数字为全角（U+FF10~U+FF19）、
连字符为私有区码位 U+E011。因此不能直接取文本，必须做码位映射，
并用 CAS 校验位对 CAS 号做程序化验证。

用法：
    python scripts/extract_gb18218_tables.py <标准正本.pdf> [输出目录]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber

# --- 码位映射 -------------------------------------------------------------

FULLWIDTH_DIGITS = {0xFF10 + i: str(i) for i in range(10)}
FULLWIDTH_UPPER = {0xFF21 + i: chr(ord("A") + i) for i in range(26)}
FULLWIDTH_LOWER = {0xFF41 + i: chr(ord("a") + i) for i in range(26)}

SPECIAL = {
    0xE011: "-",  # 私有区连字符
    0xFF0F: "/",
    0xFF0E: ".",
    0xFF05: "%",
    0xFF08: "(",
    0xFF09: ")",
    0xFF0C: ",",
    0xFF1A: ":",
    0xFF1B: ";",
    0xFF1E: ";",
    0xFF1F: "?",
    0xFF01: "!",
    0xFF1D: "=",
    0xFF0B: "+",
    0xFF1C: "<",
    0xFF1E: ">",
}

# 该 PDF 的字体把拉丁字母映射到了中日韩统一表意文字区（如 犚 = R、狇 = q）。
# 这里只登记「实测在表1~表6 中出现过」的字符，其余一旦出现会被显式报错，
# 避免静默产出错误数据。
GLYPH_FIX = {
    "\u729a": "R",  # 犚 表6 「R值」——该 PDF 用生僻汉字充当拉丁字母 R 的字形
}

CODEMAP = {}
CODEMAP.update(FULLWIDTH_DIGITS)
CODEMAP.update(FULLWIDTH_UPPER)
CODEMAP.update(FULLWIDTH_LOWER)
CODEMAP.update(SPECIAL)


def normalize(text: str | None) -> str:
    """码位归一化 + 去空白。全角转半角，私有区连字符转 '-'。"""
    if not text:
        return ""
    mapped = "".join(CODEMAP.get(ord(ch), ch) for ch in text)
    for src, dst in GLYPH_FIX.items():
        mapped = mapped.replace(src, dst)
    mapped = (
        mapped.replace("＞", ">")
        .replace("＜", "<")
        .replace("～", "~")
    )
    return re.sub(r"\s+", "", mapped)


SUSPECT_GLYPH_RANGE = range(0x7200, 0x7400)


def find_suspect_glyphs(text: str, body_chars: set[str]) -> list[str]:
    """找出疑似「字体映射的拉丁字母」但尚未登记映射的字符。

    判据：落在可疑码位区间，且**未在正文（表格外文本）中出现过**——
    正文用正常字体，所以字体映射产生的生僻字只会出现在表格里。
    """
    return sorted({ch for ch in text if ord(ch) in SUSPECT_GLYPH_RANGE and ch not in body_chars})


def unmapped_glyphs(text: str) -> list[str]:
    """自检：登记过映射的字形，若在归一化后仍然存在，说明映射没生效。"""
    return sorted({ch for ch in text if ch in GLYPH_FIX})


def collect_body_chars(pdf) -> set[str]:
    """收集表格之外的正文字符集，用于区分生僻字与正常汉字。"""
    chars: set[str] = set()
    for page in pdf.pages:
        tables = page.find_tables()
        region = page
        for t in tables:
            region = region.outside_bbox(t.bbox)
        text = region.extract_text() or ""
        chars.update(text)
    return chars


def norm_name(text: str | None) -> str:
    """名称类字段：归一化但保留可读性（不删空格以外仍去空白，全角括号转半角）。"""
    return normalize(text)


def parse_cas_list(raw: str) -> list[str]:
    """把 CAS 单元格拆成多个 CAS（标准里存在一格多号，用换行分隔）。"""
    if not raw:
        return []
    parts = re.split(r"[;；]", raw)
    return [p for p in (p.strip() for p in parts) if p]


def cas_checksum_ok(cas: str) -> bool:
    """CAS 登记号校验位算法：去掉连字符后，末位为校验位。

    校验位 = (从右往左第 2 位起，各位数字 × 其序号) 之和 mod 10。
    """
    digits = cas.replace("-", "")
    if not digits.isdigit() or len(digits) < 5:
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check


def split_cas_field(raw: str) -> tuple[list[str], list[str]]:
    """返回 (合法 CAS 列表, 非法/待人工确认项)。"""
    valid: list[str] = []
    suspect: list[str] = []
    # 形如 74-82-8(甲烷)8006-14-2(天然气)：按 CAS 模式切分并保留后缀说明
    # 注意：归一化后括号已是 ASCII 半角。
    pattern = re.compile(r"(\d{2,7}-\d{2}-\d)(\([^)]*\))?")
    for m in pattern.finditer(raw):
        cas, suffix = m.group(1), m.group(2) or ""
        item = cas + suffix
        (valid if cas_checksum_ok(cas) else suspect).append(item)
    leftover = pattern.sub("", raw)
    if leftover:
        suspect.append(f"未匹配片段:{leftover}")
    return valid, suspect


# --- 已登记的人工修正 -----------------------------------------------------
# 该 PDF 中下标（如 H₂、CH₄）的字符位置偏低，表格抽取时会被排到单元格末尾。
# 只对「已逐个视觉核对过」的行做显式修正，并在校验报告中列出，不做猜测式改写。
NAME_OVERRIDES: dict[int, str] = {
    13: "煤气(CO,CO和H₂、CH₄的混合物等)",  # 原始抽取为 "...H、CH的混合物等)24"
}

# 表1 中的纵向合并单元格：`extract_tables()` 只在合并区首行给出内容。
# 已对照渲染页逐一确认：序号 37~41 的「别名=硝化棉」「CAS=9004-70-0」为同一合并单元格，
# 序号 42 起为新单元格。这里登记「本行应从哪一行继承空字段」，不做启发式推断。
ROW_INHERIT: dict[int, int] = {38: 37, 39: 37, 40: 37, 41: 37}
INHERIT_FIELDS = ("alias", "cas_raw")


def extract(pdf_path: Path) -> dict:
    table1: list[dict] = []
    table1_by_seq: dict[int, dict] = {}
    table2: list[dict] = []
    beta_gas: list[dict] = []
    beta_class: list[dict] = []
    alpha: list[dict] = []
    levels: list[dict] = []
    suspect_glyphs: set[str] = set()

    with pdfplumber.open(str(pdf_path)) as pdf:
        body_chars = collect_body_chars(pdf)
        for pno, page in enumerate(pdf.pages):
            for table in page.find_tables():
                tbl = table.extract()
                if not tbl:
                    continue
                header = [normalize(c) for c in tbl[0]]
                while len(header) < 5:
                    header.append("")
                for cells in tbl:
                    for c in cells:
                        suspect_glyphs.update(find_suspect_glyphs(c or "", body_chars))

                kind = None
                if header[:2] == ["序号", "危险化学品名称和说明"]:
                    kind = "t1"
                elif header[:2] == ["类别", "符号"] and header[3].startswith("临界量"):
                    kind = "t2"
                elif header[0] == "名称" and header[1].startswith("校正系数"):
                    kind = "t3"
                elif header[:2] == ["类别", "符号"] and header[2].startswith("β"):
                    kind = "t4"
                elif header[0].startswith("厂外可能暴露人员数量"):
                    kind = "t5"
                elif header[0] == "重大危险源级别":
                    kind = "t6"
                if kind is None:
                    continue
                rows = tbl[1:]

                for row in rows:
                    cells = [normalize(c) for c in row]
                    # 合并单元格会导致行长度短于表头，补齐到 5 列
                    if len(cells) < 5:
                        cells = cells + [""] * (5 - len(cells))
                    if kind == "t1":
                        if not cells or not cells[0].isdigit():
                            continue
                        seq = int(cells[0])
                        name = NAME_OVERRIDES.get(seq, cells[1])
                        raw_cas = cells[3]
                        alias = cells[2] or None
                        if not alias and seq in ROW_INHERIT:
                            alias = table1_by_seq.get(ROW_INHERIT[seq], {}).get("alias")
                        if not raw_cas and seq in ROW_INHERIT:
                            raw_cas = table1_by_seq.get(ROW_INHERIT[seq], {}).get("cas_raw") or ""
                        valid, suspect = split_cas_field(raw_cas)
                        row_out = {
                            "seq": seq,
                            "name": name,
                            "name_overridden": seq in NAME_OVERRIDES,
                            "alias": alias,
                            "alias_inherited_from": ROW_INHERIT.get(seq)
                            if not cells[2] and seq in ROW_INHERIT
                            else None,
                            "cas_raw": raw_cas or None,
                            "cas": valid,
                            "cas_suspect": suspect,
                            "critical_t": cells[4],
                            "source_page": pno + 1,
                        }
                        table1.append(row_out)
                        table1_by_seq[seq] = row_out
                    elif kind == "t2":
                        if not any(cells):
                            continue
                        table2.append(
                            {
                                "category": cells[0],
                                "symbol": cells[1],
                                "description": cells[2],
                                "critical_t": cells[3],
                                "source_page": pno + 1,
                            }
                        )
                    elif kind == "t3":
                        if not cells[0]:
                            continue
                        beta_gas.append(
                            {"name": cells[0], "beta": cells[1], "source_page": pno + 1}
                        )
                    elif kind == "t4":
                        if not any(cells[:2]):
                            continue
                        beta_class.append(
                            {
                                "category": cells[0],
                                "symbol": cells[1],
                                "beta": cells[2],
                                "source_page": pno + 1,
                            }
                        )
                    elif kind == "t5":
                        if not cells[0]:
                            continue
                        alpha.append(
                            {
                                "exposed_population": cells[0],
                                "alpha": cells[1],
                                "source_page": pno + 1,
                            }
                        )
                    elif kind == "t6":
                        if not cells[0]:
                            continue
                        levels.append(
                            {
                                "level": cells[0],
                                "r_expression": cells[1],
                                "source_page": pno + 1,
                            }
                        )

    # 表2 的类别列存在跨行合并，向下填充
    last_cat = ""
    for r in table2:
        if r["category"]:
            last_cat = r["category"]
        else:
            r["category"] = last_cat
    # 表4 同理
    last_cat = ""
    for r in beta_class:
        if r["category"]:
            last_cat = r["category"]
        else:
            r["category"] = last_cat

    return {
        "table1": table1,
        "table2": table2,
        "beta_gas": beta_gas,
        "beta_class": beta_class,
        "alpha": alpha,
        "levels": levels,
        "suspect_glyphs": sorted(suspect_glyphs),
        "unmapped_glyphs": sorted(
            {
                ch
                for group in (table1, table2, beta_gas, beta_class, alpha, levels)
                for row in group
                for v in row.values()
                if isinstance(v, str)
                for ch in unmapped_glyphs(v)
            }
        ),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/标准数据-GB18218-2018")
    out_dir.mkdir(parents=True, exist_ok=True)

    data = extract(pdf_path)
    t1 = data["table1"]

    outputs = {
        "gb18218-2018-table1-critical-quantities.json": data["table1"],
        "gb18218-2018-table2-critical-quantities.json": data["table2"],
        "gb18218-2018-table3-beta-gas.json": data["beta_gas"],
        "gb18218-2018-table4-beta-class.json": data["beta_class"],
        "gb18218-2018-table5-alpha.json": data["alpha"],
        "gb18218-2018-table6-levels.json": data["levels"],
    }
    for fname, payload in outputs.items():
        (out_dir / fname).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # 供业务方人工复核的 Markdown 版（逐条对齐标准原文）
    md: list[str] = [
        "# GB 18218-2018 临界量与分级参数（表1~表6）",
        "",
        f"来源：`{pdf_path.name}` 标准正本，由 `scripts/extract_gb18218_tables.py` 抽取。",
        "",
        "> 本文件用于业务复核；程序使用请以同目录 JSON 为准。",
        "",
        "## 表1 危险化学品名称及其临界量（85 条）",
        "",
        "| 序号 | 危险化学品名称和说明 | 别名 | CAS 号 | 临界量/t | 页 |",
        "|---|---|---|---|---|---|",
    ]
    for r in data["table1"]:
        md.append(
            f"| {r['seq']} | {r['name']} | {r['alias'] or ''} | "
            f"{'；'.join(r['cas']) or ''} | {r['critical_t']} | {r['source_page']} |"
        )
    md += [
        "",
        "## 表2 未在表1中列举的危险化学品临界量",
        "",
        "| 类别 | 符号 | 危险性分类及说明 | 临界量/t |",
        "|---|---|---|---|",
    ]
    for r in data["table2"]:
        md.append(
            f"| {r['category']} | {r['symbol']} | {r['description']} | {r['critical_t']} |"
        )
    md += ["", "## 表3 毒性气体校正系数 β", "", "| 名称 | β |", "|---|---|"]
    for r in data["beta_gas"]:
        md.append(f"| {r['name']} | {r['beta']} |")
    md += ["", "## 表4 未在表3中列举的危险化学品校正系数 β", "", "| 类别 | 符号 | β |", "|---|---|---|"]
    for r in data["beta_class"]:
        md.append(f"| {r['category']} | {r['symbol']} | {r['beta']} |")
    md += ["", "## 表5 暴露人员校正系数 α", "", "| 厂外可能暴露人员数量 | α |", "|---|---|"]
    for r in data["alpha"]:
        md.append(f"| {r['exposed_population']} | {r['alpha']} |")
    md += ["", "## 表6 重大危险源级别和 R 值的对应关系", "", "| 级别 | R 值 |", "|---|---|"]
    for r in data["levels"]:
        md.append(f"| {r['level']} | {r['r_expression']} |")
    md.append("")
    (out_dir / "GB18218-2018-临界量与分级参数.md").write_text("\n".join(md), encoding="utf-8")

    # 校验报告
    bad_cas = [r for r in t1 if r["cas_suspect"]]
    no_cas = [r for r in t1 if not r["cas"] and not r["cas_raw"]]
    seqs = [r["seq"] for r in t1]
    missing_seq = sorted(set(range(1, max(seqs) + 1)) - set(seqs)) if seqs else []

    lines = [
        "# GB 18218-2018 表1~表6 抽取校验报告",
        "",
        f"- 来源：`{pdf_path.name}`",
        f"- 表1 条目数：{len(t1)}（序号 {min(seqs)}~{max(seqs)}）",
        f"- 表2 条目数：{len(data['table2'])}",
        f"- 表3 条目数：{len(data['beta_gas'])}",
        f"- 表4 条目数：{len(data['beta_class'])}",
        f"- 表5 条目数：{len(data['alpha'])}",
        f"- 表6 条目数：{len(data['levels'])}",
        f"- 序号连续性：{'通过（无缺号）' if not missing_seq else '缺失 ' + str(missing_seq)}",
        f"- CAS 校验位通过：{sum(1 for r in t1 if r['cas'] and not r['cas_suspect'])} 条",
        f"- CAS 存疑/需人工确认：{len(bad_cas)} 条",
        f"- 无 CAS（标准原文本身为空）：{len(no_cas)} 条",
        f"- 未登记字体映射字符：{data['suspect_glyphs'] or '无'}",
        f"- 映射未生效字符（应为空）：{data['unmapped_glyphs'] or '无'}",
        f"- 已登记人工修正：{sorted(NAME_OVERRIDES) or '无'}",
        "",
        "## 人工修正清单（已视觉核对）",
        "",
    ]
    if NAME_OVERRIDES:
        lines += ["| 序号 | 修正后名称 | 说明 |", "|---|---|---|"]
        for seq, name in sorted(NAME_OVERRIDES.items()):
            lines.append(f"| {seq} | {name} | 下标字符被表格抽取排到末尾，已手工修正 |")
    else:
        lines.append("无。")
    lines += [
        "",
        "## CAS 存疑清单",
        "",
    ]
    if bad_cas:
        lines += ["| 序号 | 名称 | CAS 原始值 | 问题 |", "|---|---|---|---|"]
        for r in bad_cas:
            lines.append(f"| {r['seq']} | {r['name']} | {r['cas_raw']} | {'; '.join(r['cas_suspect'])} |")
    else:
        lines.append("无。")
    lines += ["", "## 无 CAS 清单（标准原文即空）", ""]
    if no_cas:
        lines += ["| 序号 | 名称 |", "|---|---|"]
        for r in no_cas:
            lines.append(f"| {r['seq']} | {r['name']} |")
    else:
        lines.append("无。")
    (out_dir / "校验报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"表1 {len(t1)} / 表2 {len(data['table2'])} / 表3 {len(data['beta_gas'])} / "
        f"表4 {len(data['beta_class'])} / 表5 {len(data['alpha'])} / 表6 {len(data['levels'])} -> {out_dir}"
    )
    print(f"CAS 存疑 {len(bad_cas)} 条 / 无 CAS {len(no_cas)} 条 / 缺号 {missing_seq or '无'}")
    print(f"未登记字体映射字符：{data['suspect_glyphs'] or '无'}")
    print(f"映射未生效字符（应为空）：{data['unmapped_glyphs'] or '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
