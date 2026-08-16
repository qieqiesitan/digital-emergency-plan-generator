# 图标系统整体优化实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 桌面 Web 端图标统一为线性风格：新建 `AppIcon` 组件承载 24 个 iconfont 本地 SVG，替换驾驶舱模块导航 10 项、主导航业务菜单 7 项、业务页语义图标（法规类型 4 + 安全/通知/定位/AI 共 8 个场景）；通用操作图标保留 AntD。

**架构：** 双轨制。业务图标以本地 SVG 落盘 `frontend/src/assets/icons/`，由 `scripts/fetch_icons.py` 从 iconfont 公开接口按 id 抓取并清洗（去 class/style/version/硬编码色），再由 `scripts/gen_icons_tsx.py` 生成集中 `frontend/src/components/common/icons.tsx`（JSX 内联、零新依赖、类型安全），统一经 `AppIcon` 组件渲染；AntD 通用图标保持直接引用。迁移分 4 个独立提交批次，每批跑 tsc/eslint/vitest + 截图回归。

**技术栈：** React 19 + TypeScript + Vite + Vitest + AntD 6 + iconfont 公开接口（仅构建期抓取，生产零 CDN 依赖）。

**前置：** 本计划在分支 `codex/icon-system` 的隔离工作区 `.worktrees/icon-system` 执行。设计规格：`docs/superpowers/specs/2026-08-16-icon-system-design.md`（含 §4.3 完整映射表）。图标抓取脚本为仓库自包含实现，不依赖 `.codex` 技能目录。

---

### 任务 1：图标抓取脚本与 24 个 SVG 资产

**文件：**
- 创建：`scripts/fetch_icons.py`
- 创建：`scripts/test_fetch_icons.py`
- 创建：`frontend/src/assets/icons/*.svg`（24 个，脚本生成）

- [ ] **步骤 1：编写失败的测试**

创建 `scripts/test_fetch_icons.py`：

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_icons import clean_svg


class CleanSvgTest(unittest.TestCase):
    def test_strips_noise_and_preserves_geometry(self):
        svg = (
            '<svg class="icon" style="width:1em" version="1.1" viewBox="0 0 1024 1024">'
            '<path fill="#383838" d="M1 2z"/>'
            '<path fill="none" stroke="#000" d="M3 4z"/>'
            "</svg>"
        )
        out = clean_svg(svg)
        self.assertNotIn("class=", out)
        self.assertNotIn("style=", out)
        self.assertNotIn("version=", out)
        self.assertNotIn('fill="#383838"', out)
        self.assertIn('fill="none"', out)
        self.assertIn('stroke="#000"', out)
        self.assertIn('viewBox="0 0 1024 1024"', out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest scripts.test_fetch_icons -v`
预期：FAIL，报错 `ModuleNotFoundError: No module named 'fetch_icons'`

- [ ] **步骤 3：编写最小实现 `scripts/fetch_icons.py`**

```python
#!/usr/bin/env python3
"""Fetch chosen iconfont icons as cleaned local SVG assets (build-time only).

Calls the iconfont.cn public search API (no key), picks icons by id from
MAPPING, strips presentation noise and writes
frontend/src/assets/icons/<name>.svg.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://www.iconfont.cn/api/icon/search.json"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

# name -> (search term, iconfont id)  —— 与设计文档 §4.3 映射表一致
MAPPING = {
    "archive": ("档案", 1490623),
    "org": ("组织架构", 29865223),
    "geo": ("地图", 2076231),
    "chem": ("危化品", 13209754),
    "risk": ("风险管控", 32835841),
    "hazard": ("隐患排查", 12820186),
    "rescue": ("应急资源", 45446276),
    "assessment": ("风险评估", 3759366),
    "investigation": ("调查", 4423489),
    "plan-manage": ("应急预案", 8625443),
    "dashboard": ("工作台", 7215957),
    "enterprise": ("企业", 11239041),
    "plan-list": ("应急预案", 2959108),
    "regulations": ("法规", 8329617),
    "data-dict": ("数据字典", 1680700),
    "prompt": ("对话", 2286510),
    "ai": ("机器人", 5387814),
    "law": ("法律", 7991666),
    "standard": ("标准", 3207743),
    "policy": ("政策", 12031078),
    "topic": ("书本", 3522456),
    "safety": ("安全帽", 3029239),
    "notice": ("通知", 577374),
    "location": ("定位", 11372652),
}

OUT_DIR = "frontend/src/assets/icons"
FILL_RE = re.compile(r'\sfill="#[0-9a-fA-F]{3,8}"')
FILL_RGB_RE = re.compile(r'\sfill="rgb\([^"]*\)"')
MAX_PAGES = 5
PAGE_SIZE = 60


def clean_svg(svg: str) -> str:
    svg = re.sub(r' class="[^"]*"', "", svg)
    svg = re.sub(r' style="[^"]*"', "", svg)
    svg = re.sub(r' version="[^"]*"', "", svg)
    svg = FILL_RE.sub("", svg)
    svg = FILL_RGB_RE.sub("", svg)
    return svg


def search(q: str, page: int = 1, limit: int = PAGE_SIZE) -> list[dict]:
    params = {
        "q": q,
        "sortType": "updated_at",
        "page": str(page),
        "pageSize": str(limit),
        "sType": "",
        "fromCollection": "1",
        "fills": "",
        "ctoken": "null",
        "t": str(int(time.time() * 1000)),
    }
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 200:
        raise RuntimeError(
            f"iconfont api error: code={data.get('code')} msg={data.get('message')}"
        )
    return data.get("data", {}).get("icons", [])


def fetch_all() -> dict[str, str]:
    cache: dict[str, list[dict]] = {}
    assets: dict[str, str] = {}
    for name, (term, icon_id) in MAPPING.items():
        if term not in cache:
            needed = {i for n, (t, i) in MAPPING.items() if t == term}
            hits: list[dict] = []
            for attempt in range(3):
                try:
                    for page in range(1, MAX_PAGES + 1):
                        page_hits = search(term, page)
                        hits.extend(page_hits)
                        found = {h.get("id") for h in hits}
                        if needed.issubset(found):
                            break
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        raise
            cache[term] = hits
        hit = next((i for i in cache[term] if i.get("id") == icon_id), None)
        if not hit or not hit.get("show_svg"):
            raise RuntimeError(f"icon {name} (id={icon_id}) not found for term {term!r}")
        assets[name] = clean_svg(hit["show_svg"])
    return assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and clean iconfont SVG assets.")
    parser.add_argument("--verify", action="store_true", help="verify existing assets")
    args = parser.parse_args()

    if args.verify:
        missing = [n for n in MAPPING if not os.path.isfile(f"{OUT_DIR}/{n}.svg")]
        if missing:
            print("MISSING:", ", ".join(missing))
            return 1
        for name in MAPPING:
            raw = open(f"{OUT_DIR}/{name}.svg", encoding="utf-8").read()
            if not raw.strip() or 'fill="#' in raw or 'class="' in raw or ' style="' in raw:
                print("DIRTY:", name)
                return 1
        print(f"OK: {len(MAPPING)} assets verified")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    assets = fetch_all()
    for name, svg in assets.items():
        with open(f"{OUT_DIR}/{name}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"written: {OUT_DIR}/{name}.svg")
    print(f"total: {len(assets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest scripts.test_fetch_icons -v`
预期：PASS（1 个用例）

- [ ] **步骤 5：抓取并落盘 24 个 SVG**

运行：`python scripts/fetch_icons.py`
预期：输出 24 行 `written: frontend/src/assets/icons/<name>.svg`，末尾 `total: 24`；退出码 0

运行：`python scripts/fetch_icons.py --verify`
预期：`OK: 24 assets verified`

若个别图标渲染后不可见（依赖 stroke 的候选），在该文件 `<svg>` 根上补 `stroke="currentColor"` 后再 commit。

- [ ] **步骤 6：Commit**

```bash
git add scripts/fetch_icons.py scripts/test_fetch_icons.py frontend/src/assets/icons
git commit -m "feat(icon-system): fetch and clean 24 iconfont svg assets"
```

---

### 任务 2：AppIcon 组件与 icons.tsx

**文件：**
- 创建：`scripts/gen_icons_tsx.py`
- 创建：`frontend/src/components/common/icons.tsx`（脚本生成）
- 创建：`frontend/src/components/common/AppIcon.tsx`
- 测试：`frontend/src/components/common/AppIcon.test.tsx`

- [ ] **步骤 1：编写失败的测试**

创建 `frontend/src/components/common/AppIcon.test.tsx`：

```tsx
import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import AppIcon from "./AppIcon";

describe("AppIcon", () => {
  it("renders svg with size, viewBox and aria-hidden", () => {
    const html = renderToStaticMarkup(<AppIcon name="risk" size={24} />);
    expect(html).toContain("<svg");
    expect(html).toContain('width="24"');
    expect(html).toContain('height="24"');
    expect(html).toContain('viewBox="0 0 1024 1024"');
    expect(html).toContain('aria-hidden="true"');
  });

  it("forwards className", () => {
    const html = renderToStaticMarkup(<AppIcon name="ai" className="foo" />);
    expect(html).toContain('class="foo"');
  });

  it("warns and renders nothing for unknown name", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const html = renderToStaticMarkup(<AppIcon name={"nope" as never} />);
    expect(html).toBe("");
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`npx vitest run src/components/common/AppIcon.test.tsx`
预期：FAIL，报错 `Cannot find module './AppIcon'` 或 `./icons`

- [ ] **步骤 3：创建生成脚本 `scripts/gen_icons_tsx.py`**

```python
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
```

运行：`python scripts/gen_icons_tsx.py`
预期：`written: frontend/src/components/common/icons.tsx (24 icons)`

创建 `frontend/src/components/common/AppIcon.tsx`：

```tsx
import type { CSSProperties } from "react";
import { ICONS, type AppIconName } from "./icons";

export interface AppIconProps {
  name: AppIconName;
  size?: number;
  className?: string;
  style?: CSSProperties;
}

export default function AppIcon({ name, size = 16, className, style }: AppIconProps) {
  const icon = ICONS[name];
  if (!icon) {
    if (import.meta.env.DEV) {
      console.warn(`[AppIcon] unknown icon name: ${String(name)}`);
    }
    return null;
  }
  return (
    <svg
      className={className}
      style={style}
      width={size}
      height={size}
      viewBox={icon.viewBox}
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      {icon.body}
    </svg>
  );
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npx vitest run src/components/common/AppIcon.test.tsx`
预期：PASS（3 个用例）

- [ ] **步骤 5：类型与 lint 检查**

运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint src/components/common/AppIcon.tsx src/components/common/icons.tsx src/components/common/AppIcon.test.tsx`
预期：exit 0

- [ ] **步骤 6：Commit**

```bash
git add scripts/gen_icons_tsx.py frontend/src/components/common
git commit -m "feat(icon-system): add AppIcon component with 24 local svg icons"
```

---

### 任务 3：驾驶舱模块导航替换（10 项）

**文件：**
- 修改：`frontend/src/components/enterprise/cockpit/ModuleNav.tsx`
- 修改：`frontend/src/styles/cockpit.css:181`

- [ ] **步骤 1：替换 ModuleNav 图标**

`ModuleNav.tsx` 中：删除 `const stroke = {...}` 与 10 个内联 `<svg>...</svg>`，MODULES 每项 `icon` 改为 `<AppIcon name="<key>" size={24} />`，并在文件顶部加 `import AppIcon from "@/components/common/AppIcon";`。映射（key → AppIcon name）：info→archive、org→org、geo→geo、chem→chem、risk→risk、hazard→hazard、rescue→rescue、assessment→assessment、investigation→investigation、plan→plan-manage。

- [ ] **步骤 2：调整驾驶舱图标 CSS 保持渐变光效**

`frontend/src/styles/cockpit.css:181` 由：

```css
.cp-nav svg { width: 26px; height: 26px; stroke: url(#cp-grad); filter: drop-shadow(0 0 5px rgba(0,212,255,.45)); }
```

改为：

```css
.cp-nav svg { width: 26px; height: 26px; fill: url(#cp-grad); stroke: none; filter: drop-shadow(0 0 5px rgba(0,212,255,.45)); }
```

（`cp-grad` 渐变定义在 `EnterpriseCockpitPage.tsx:65`，不动。）

- [ ] **步骤 3：类型与 lint**

运行：`npx tsc -b`、`npx eslint src/components/enterprise/cockpit/ModuleNav.tsx src/styles/cockpit.css`
预期：均 exit 0

- [ ] **步骤 4：现有测试回归**

运行：`npx vitest run`
预期：15 文件 / 127 测试全部通过

- [ ] **步骤 5：截图目检**

运行：`npx playwright test e2e/enterprise-cockpit.spec.ts`
预期：1 passed；并对驾驶舱页截图确认 10 个新图标以渐变描边光效正常渲染、大小无漂移

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/components/enterprise/cockpit/ModuleNav.tsx frontend/src/styles/cockpit.css
git commit -m "feat(icon-system): replace cockpit module nav icons with AppIcon"
```

---

### 任务 4：主导航业务菜单替换（7 项）

**文件：**
- 修改：`frontend/src/layouts/MainLayout.tsx`

- [ ] **步骤 1：替换 7 个业务菜单图标**

`MainLayout.tsx` 顶部加 `import AppIcon from "@/components/common/AppIcon";`。以下菜单项 `icon` 替换（原 AntD import 若无其他使用则从 import 行移除，以 eslint 为准）：

| 行 | 原 icon | 新 icon |
|---|---|---|
| 84（工作台） | `<DashboardOutlined />` | `<AppIcon name="dashboard" size={14} />` |
| 85（企业管理） | `<BankOutlined />` | `<AppIcon name="enterprise" size={14} />` |
| 86（预案列表） | `<FileTextOutlined />` | `<AppIcon name="plan-list" size={14} />` |
| 80（法规库管理） | `<FileTextOutlined />` | `<AppIcon name="regulations" size={14} />` |
| 96（数据字典管理） | `<DatabaseOutlined />` | `<AppIcon name="data-dict" size={14} />` |
| 105（提示词管理） | `<EditOutlined />` | `<AppIcon name="prompt" size={14} />` |
| 79（AI 配置） | `<KeyOutlined />` | `<AppIcon name="ai" size={14} />` |

保留 AntD：用户管理（TeamOutlined）、角色管理（SafetyCertificateOutlined）、系统配置（SettingOutlined）、个人资料（UserOutlined）、退出登录（LogoutOutlined），以及头像下拉菜单里的同名入口。

- [ ] **步骤 2：类型与 lint**

运行：`npx tsc -b`、`npx eslint src/layouts/MainLayout.tsx`
预期：均 exit 0

- [ ] **步骤 3：现有测试回归**

运行：`npx vitest run`
预期：15 文件 / 127 测试全部通过

- [ ] **步骤 4：截图目检**

登录后截图首页与设置页，确认侧边菜单 7 个新图标渲染正常、尺寸与原有图标一致。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/layouts/MainLayout.tsx
git commit -m "feat(icon-system): replace main menu business icons with AppIcon"
```

---

### 任务 5：法规库类型图标替换（4 项）

**文件：**
- 修改：`frontend/src/components/regulation/RegulationList.tsx`

- [ ] **步骤 1：替换 TYPE_CONFIG 图标**

`RegulationList.tsx` 顶部加 `import AppIcon from "@/components/common/AppIcon";`。TYPE_CONFIG（27-30 行）：

| 行 | 原 icon | 新 icon |
|---|---|---|
| 27（法律） | `<AuditOutlined />` | `<AppIcon name="law" />` |
| 28（标准） | `<SafetyCertificateOutlined />` | `<AppIcon name="standard" />` |
| 29（政策） | `<FlagOutlined />` | `<AppIcon name="policy" />` |
| 30（主题） | `<BookOutlined />` | `<AppIcon name="topic" />` |

统计条（68 行 `法规总数` 的 `<BookOutlined />`）保持 AntD 不动；import 中仅移除不再使用的 `AuditOutlined`、`FlagOutlined`（`BookOutlined` 68 行仍用，`SafetyCertificateOutlined` 若其他文件无引用则从本文件 import 移除，以 eslint 为准）。

- [ ] **步骤 2：类型与 lint**

运行：`npx tsc -b`、`npx eslint src/components/regulation/RegulationList.tsx`
预期：均 exit 0

- [ ] **步骤 3：测试回归**

运行：`npx vitest run`
预期：15 文件 / 127 测试全部通过

- [ ] **步骤 4：截图目检**

打开法规库页面，确认 4 个类型图标在彩色标签中正常渲染。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/regulation/RegulationList.tsx
git commit -m "feat(icon-system): replace regulation type icons with AppIcon"
```

---

### 任务 6：AI 标识统一（12 处 RobotOutlined → AppIcon ai）

**文件（修改）：**
- `frontend/src/pages/Chat/index.tsx:292,438`
- `frontend/src/pages/Hazard/HazardPlanPage.tsx:416`
- `frontend/src/components/plan/RichTextEditor.tsx:139`
- `frontend/src/pages/Hazard/HazardTemplatePage.tsx:328`
- `frontend/src/pages/Hazard/HazardRecordDetailPage.tsx:782,785`
- `frontend/src/components/plan/AIGenerateButton.tsx:157`
- `frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx:158`
- `frontend/src/components/enterprise/RiskEventForm.tsx:459,773`
- `frontend/src/components/enterprise/RiskSourceForm.tsx:119`
- `frontend/src/components/enterprise/EmergencyResourceForm.tsx:80`
- `frontend/src/components/enterprise/RiskMeasureForm.tsx:154`

- [ ] **步骤 1：逐文件替换**

每个文件顶部加 `import AppIcon from "@/components/common/AppIcon";`，将 `<RobotOutlined ... />` 替换为 `<AppIcon name="ai" ... />`，保留原有 `style` 等 props，并按尺寸调整：

| 位置 | 原写法 | 新写法 |
|---|---|---|
| Chat/index.tsx:292 | `<RobotOutlined style={{ fontSize: 36, marginBottom: 12 }} />` | `<AppIcon name="ai" size={36} style={{ marginBottom: 12 }} />` |
| Chat/index.tsx:438 | `<RobotOutlined style={{ fontSize: 48, marginBottom: 16, color: "#d9d9d9" }} />` | `<AppIcon name="ai" size={48} style={{ marginBottom: 16, color: "#d9d9d9" }} />` |
| 其余 10 处按钮 | `<RobotOutlined />` | `<AppIcon name="ai" />` |

替换后若某文件不再使用 `RobotOutlined`，将其从 import 行移除（eslint 报 unused 为准）。

- [ ] **步骤 2：类型与 lint**

运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint src/pages/Chat/index.tsx src/pages/Hazard/HazardPlanPage.tsx src/components/plan/RichTextEditor.tsx src/pages/Hazard/HazardTemplatePage.tsx src/pages/Hazard/HazardRecordDetailPage.tsx src/components/plan/AIGenerateButton.tsx src/pages/Enterprise/HazardousChemicalsTab.tsx src/components/enterprise/RiskEventForm.tsx src/components/enterprise/RiskSourceForm.tsx src/components/enterprise/EmergencyResourceForm.tsx src/components/enterprise/RiskMeasureForm.tsx`
预期：exit 0

- [ ] **步骤 3：测试回归**

运行：`npx vitest run`
预期：15 文件 / 127 测试全部通过

- [ ] **步骤 4：截图目检**

抽查预案编辑页（RichTextEditor AI 按钮）、AI 生成按钮、隐患详情页 AI 按钮，确认按钮图标尺寸视觉一致（必要时给按钮场景补 `size={14}`）。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Chat/index.tsx frontend/src/pages/Hazard/HazardPlanPage.tsx frontend/src/components/plan/RichTextEditor.tsx frontend/src/pages/Hazard/HazardTemplatePage.tsx frontend/src/pages/Hazard/HazardRecordDetailPage.tsx frontend/src/components/plan/AIGenerateButton.tsx frontend/src/pages/Enterprise/HazardousChemicalsTab.tsx frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/components/enterprise/RiskSourceForm.tsx frontend/src/components/enterprise/EmergencyResourceForm.tsx frontend/src/components/enterprise/RiskMeasureForm.tsx
git commit -m "feat(icon-system): unify AI icons with AppIcon ai"
```

---

### 任务 7：位置 / 通知 / 安全图标替换

**文件（修改）：**
- 位置（EnvironmentOutlined → `AppIcon name="location"`，保留原有 style/props）：
  - `frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx:105`
  - `frontend/src/components/enterprise/RiskZoneForm.tsx:129`
  - `frontend/src/components/enterprise/FloorPlanPicker.tsx:99`
  - `frontend/src/components/enterprise/RiskSourceForm.tsx:72,149`
  - `frontend/src/components/enterprise/RiskObjectForm.tsx:180`
  - `frontend/src/components/enterprise/EnterpriseInfoWorkspace.tsx:245`
  - `frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx:30`
- 通知：`frontend/src/pages/Enterprise/RiskManagementTab.tsx:367`（`<NotificationOutlined />` → `<AppIcon name="notice" />`）
- 安全：`frontend/src/layouts/AuthLayout.tsx:30`（`<SafetyOutlined style={{ fontSize: 64, marginBottom: 24 }} />` → `<AppIcon name="safety" size={64} style={{ marginBottom: 24 }} />`）

- [ ] **步骤 1：逐文件替换**

每个文件顶部加 `import AppIcon from "@/components/common/AppIcon";`，按上表替换；替换后若某文件不再使用对应 AntD 图标，从 import 行移除（eslint 报 unused 为准）。

- [ ] **步骤 2：类型与 lint**

运行：`npx tsc -b`
预期：exit 0

运行：`npx eslint src/pages/Enterprise/EnterpriseCreatePage.tsx src/components/enterprise/RiskZoneForm.tsx src/components/enterprise/FloorPlanPicker.tsx src/components/enterprise/RiskSourceForm.tsx src/components/enterprise/RiskObjectForm.tsx src/components/enterprise/EnterpriseInfoWorkspace.tsx src/components/enterprise/riskMapping/WorkbenchToolbar.tsx src/pages/Enterprise/RiskManagementTab.tsx src/layouts/AuthLayout.tsx`
预期：exit 0

- [ ] **步骤 3：测试回归**

运行：`npx vitest run`
预期：15 文件 / 127 测试全部通过

- [ ] **步骤 4：截图目检**

抽查登录页安全盾、四色图工作台工具栏定位图标、楼层平面图红色定位标记、企业编辑页 GIS 按钮，确认渲染正常（保留原 props 的颜色/阴影样式）。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx frontend/src/components/enterprise/RiskZoneForm.tsx frontend/src/components/enterprise/FloorPlanPicker.tsx frontend/src/components/enterprise/RiskSourceForm.tsx frontend/src/components/enterprise/RiskObjectForm.tsx frontend/src/components/enterprise/EnterpriseInfoWorkspace.tsx frontend/src/components/enterprise/riskMapping/WorkbenchToolbar.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/layouts/AuthLayout.tsx
git commit -m "feat(icon-system): replace location notice and safety icons with AppIcon"
```

---

### 任务 8：全量门禁与收尾

- [ ] **步骤 1：全量前端门禁**

运行：`npx tsc -b`、`npx eslint src`、`npx vitest run`
预期：均 exit 0（127 测试通过）

- [ ] **步骤 2：驾驶舱 e2e**

运行：`npx playwright test e2e/enterprise-cockpit.spec.ts`
预期：1 passed

- [ ] **步骤 3：全仓残留检查**

运行：`rg "RobotOutlined|EnvironmentOutlined|NotificationOutlined" frontend/src -g "*.tsx" -g "*.ts"`（排除 mobile 目录）
预期：仅保留设计文档 §5「保留 AntD」清单内的场景；若有遗漏按任务 6/7 表格补替换

运行：`rg "<AppIcon" frontend/src -g "*.tsx" | Measure-Object`
预期：与 25 个用途场景吻合

- [ ] **步骤 4：更新文档与台账**

- 更新 `TASKS.md` 当前状态快照（工作区 `.worktrees/icon-system`、提交链、门禁结果）；
- 更新 `docs/superpowers/specs/2026-08-16-icon-system-design.md` 的实现状态（如无偏差可只加一行「已实现」备注）；
- 按项目惯例沉淀记忆：`project-decisions`（AppIcon 双轨制与 SVG 清洗规则）、`global/patterns`（fetch → gen → AppIcon 接入流程）。

- [ ] **步骤 5：图谱同步与收尾**

运行：`graphify update .`（主工作区图谱已过期）、`codegraph sync .`

不推远程：分支合并 / `git finish`（推 GitHub + Gitee）由用户确认后执行。

---

## 自检记录

**规格覆盖度：** 规格 §4（资产层+映射表）→ 任务 1/2；§5（AppIcon）→ 任务 2；§6 批次 1-4 → 任务 1-7；§7（验证）→ 任务 2/3/4/8；§8（风险对策）→ 任务 1 抽查与任务 3 CSS 渐变适配；§9（后续事项）→ 任务 8。无遗漏。

**占位符扫描：** 无「待定/TODO/后续实现」；所有代码步骤均含完整代码或精确的 file:line 替换表。

**类型一致性：** `AppIconName` 联合类型由任务 2 生成脚本按资产目录自动产出（24 个名字，kebab-case），任务 3-7 全部使用该联合中的名字；`AppIcon` props（name/size/className/style）在任务 2 定义，后续任务只消费，无改名。`fetch_icons.py` 的 MAPPING 键与 `AppIconName` 一一对应。
