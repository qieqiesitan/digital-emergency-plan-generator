#!/usr/bin/env python3
"""Generate frontend/src/components/common/icons.tsx from assets/icons/*.svg."""

import json
import os
import xml.etree.ElementTree as ET

SRC_DIR = "frontend/src/assets/icons"
OUT_FILE = "frontend/src/components/common/icons.tsx"

ATTR_MAP = {
    "stroke-width": "strokeWidth",
    "stroke-linecap": "strokeLinecap",
    "stroke-linejoin": "strokeLinejoin",
    "xml:space": "xmlSpace",
}


def jsx_attr(name: str, value: str) -> str:
    key = ATTR_MAP.get(name, name)
    return f"{key}={json_str(value)}"


def json_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def element_to_jsx(el: ET.Element) -> str:
    attrs = " ".join(jsx_attr(k, v) for k, v in el.attrib.items())
    tag = el.tag.split("}")[-1]
    if len(el) == 0:
        return f"<{tag}{(' ' + attrs) if attrs else ''}/>"
    children = "".join(element_to_jsx(c) for c in el)
    return f"<{tag}{(' ' + attrs) if attrs else ''}>{children}</{tag}>"


def main() -> int:
    names = sorted(f[:-4] for f in os.listdir(SRC_DIR) if f.endswith(".svg"))
    if not names:
        print("no svg assets found")
        return 1
    lines = ['import type { ReactNode } from "react";', ""]
    lines.append("export type AppIconName =")
    lines.append("  | " + "\n  | ".join(json_str(n) for n in names))
    lines.append("")
    lines.append("export const ICONS: Record<AppIconName, { viewBox: string; body: ReactNode }> = {")
    for name in names:
        root = ET.parse(f"{SRC_DIR}/{name}.svg").getroot()
        view_box = root.attrib.get("viewBox", "0 0 1024 1024")
        body = "".join(element_to_jsx(c) for c in list(root))
        lines.append(f"  {json_str(name)}: {{ viewBox: {json_str(view_box)}, body: (<>" + body + "</>) },")
    lines.append("};")
    lines.append("")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"written: {OUT_FILE} ({len(names)} icons)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
