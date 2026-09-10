# 化学品库字段富集实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 用离线批处理从 ChemBlink + PubChem 抓取可溯源的理化性质与 GHS 危害分类，为 `chemical_library` 2831 条有 CAS 的条目补齐 UN 号、物理状态、闪点、爆炸极限、引燃温度、密度、沸点、健康危害、火灾爆炸危险，产出幂等迁移 SQL 随版本部署。

**架构：** 一次性离线流水线：导出条目 → 抓取（本地缓存 + 限速 + 重试 + 断点续跑）→ 解析（区分实验值/计算值）→ 合并（冲突规则、只填空字段）→ 生成幂等 `UPDATE ... COALESCE(NULLIF(...))` SQL + JSON 快照 + 报告。不改前端、不改 API、不新增库列；公司内网部署不需要外网。

**技术栈：** Python 3.12（requests + BeautifulSoup 已具备）、pytest；PostgreSQL（容器 emergency-plan-db）、FastAPI 后端容器 emergency-plan-backend 的 migration_runner 自动应用 SQL。

**规格：** `docs/superpowers/specs/2026-09-10-chemical-library-enrichment-design.md`

**运行环境（先读）：**

- 抓取脚本在宿主执行，需要外网访问 `pubchem.ncbi.nlm.nih.gov` 与 `www.chemblink.com`。
- 后端测试文件不在 bind mount：改完需 `docker cp backend/tests/<file>.py emergency-plan-backend:/app/tests/<file>.py`，再 `docker exec emergency-plan-backend python -m pytest tests/<file>.py -q`。
- 迁移 SQL 不在 bind mount：`docker cp backend/db_migration_20260910_chemical_library_enrich.sql emergency-plan-backend:/app/` 后 `docker restart emergency-plan-backend`，由 migration_runner 应用（失败 fail-fast）。
- 数据库只读查询：`docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "..."`。
- git：`TASKS.md` 永不 `git add`；工作区有他人/历史未提交文件，每任务只 `git add` 本任务列出的精确路径；commit 前 `git status --short` 核对；如遇 `.git/index.lock`，先 `Get-Process git*` 确认无 git 进程再删除 0 字节残留。

---

## 文件结构

- 创建 `backend/tools/chemical_enrichment/__init__.py`：包标记
- 创建 `backend/tools/chemical_enrichment/fetch.py`：HTTP 客户端（磁盘缓存、限速、重试）
- 创建 `backend/tools/chemical_enrichment/chemblink.py`：ChemBlink 产品页解析（理化性质 + GHS 分类 + UN）
- 创建 `backend/tools/chemical_enrichment/pubchem.py`：PubChem PUG-View 解析（UN / 物理状态 / LEL-UEL / 引燃温度 / 闪点 / 沸点 / 密度）
- 创建 `backend/tools/chemical_enrichment/merge.py`：字段映射、冲突与缺失规则、只填空
- 创建 `backend/tools/chemical_enrichment/sqlgen.py`：生成幂等 SQL、JSON 快照
- 创建 `backend/tools/enrich_chemical_library.py`：CLI 编排（导出 → 抓取 → 解析 → 合并 → 产出）
- 创建 `backend/tests/test_chemical_library_enrichment.py`：解析器/合并/幂等 SQL 单测
- 创建 `backend/tests/fixtures/chemical_enrichment/`：离线样页夹具
- 任务 6 产出 `backend/data/chemical_library_enrichment_20260910.json`、`backend/db_migration_20260910_chemical_library_enrich.sql`、`docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md`

---

### 任务 1：抓取客户端（缓存 / 限速 / 重试 / 断点续跑）

**文件：**
- 创建：`backend/tools/chemical_enrichment/__init__.py`
- 创建：`backend/tools/chemical_enrichment/fetch.py`
- 创建：`backend/tests/test_chemical_library_enrichment.py`

- [ ] **步骤 1：编写失败的测试**

```python
from pathlib import Path

import pytest

from backend.tools.chemical_enrichment.fetch import CachedFetcher

FIXTURES = Path(__file__).parent / "fixtures" / "chemical_enrichment"


class _FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_fetcher_caches_response(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return _FakeResponse(200, "hello")

    fetcher = CachedFetcher(cache_dir=tmp_path, delay=0.0, get=fake_get)
    assert fetcher.text("https://example.com/a") == "hello"
    assert fetcher.text("https://example.com/a") == "hello"
    assert len(calls) == 1  # 第二次命中缓存
    assert fetcher.text("https://example.com/a", refresh=True) == "hello"
    assert len(calls) == 2


def test_fetcher_retries_then_raises(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        return _FakeResponse(503, "")

    fetcher = CachedFetcher(cache_dir=tmp_path, delay=0.0, retries=3, get=fake_get)
    with pytest.raises(RuntimeError):
        fetcher.text("https://example.com/flaky")
    assert len(calls) == 3
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k fetch`
预期：FAIL，`ModuleNotFoundError: No module named 'backend.tools.chemical_enrichment.fetch'`

- [ ] **步骤 3：编写最少实现代码**

```python
# backend/tools/chemical_enrichment/fetch.py
import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class CachedFetcher:
    """带磁盘缓存 / 限速 / 重试的 HTTP 客户端；缓存命中即断点续跑。"""

    def __init__(self, cache_dir, delay: float = 0.3, retries: int = 3, get=None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.retries = retries
        self._get = get or self._requests_get
        self._last_call = 0.0

    def _requests_get(self, url: str):
        return requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})

    def _cache_path(self, url: str) -> Path:
        host = urlparse(url).netloc.replace(":", "_")
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{host}__{digest}.txt"

    def text(self, url: str, refresh: bool = False) -> str:
        path = self._cache_path(url)
        if path.exists() and not refresh:
            return path.read_text(encoding="utf-8")
        last_error = None
        for _ in range(self.retries):
            wait = self.delay - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            try:
                resp = self._get(url)
            except Exception as exc:  # 网络异常同样重试
                last_error = exc
                continue
            if resp.status_code == 200:
                path.write_text(resp.text, encoding="utf-8")
                return resp.text
            last_error = RuntimeError(f"HTTP {resp.status_code}: {url}")
            if resp.status_code in (400, 404):
                break  # 资源不存在，无需重试
        raise last_error or RuntimeError(f"fetch failed: {url}")
```

```python
# backend/tools/chemical_enrichment/__init__.py
"""化学品库字段富集：ChemBlink + PubChem 离线批处理。"""

__all__ = ["fetch", "chemblink", "pubchem", "merge", "sqlgen"]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k fetch`
预期：`2 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/tools/chemical_enrichment/__init__.py backend/tools/chemical_enrichment/fetch.py backend/tests/test_chemical_library_enrichment.py
git commit -m "feat(chemical-enrichment): 抓取客户端（缓存/限速/重试/断点续跑）"
```

---

### 任务 2：ChemBlink 解析器（理化性质 + GHS 分类 + 实验值判定）

**文件：**
- 创建：`backend/tools/chemical_enrichment/chemblink.py`
- 创建：`backend/tests/fixtures/chemical_enrichment/chemblink_75-18-3.html`（甲硫醚：实验值 + 计算值并存）
- 创建：`backend/tests/fixtures/chemical_enrichment/chemblink_2050-92-2.html`（二正戊胺：无标注实测值 + UN 2841）
- 测试：`backend/tests/test_chemical_library_enrichment.py`（追加）

- [ ] **步骤 1：保存离线夹具**

```bash
python - <<'PY'
import pathlib, requests
d = pathlib.Path("backend/tests/fixtures/chemical_enrichment"); d.mkdir(parents=True, exist_ok=True)
for cas in ["75-18-3", "2050-92-2"]:
    r = requests.get(f"https://www.chemblink.com/zh/products/{cas}C.htm", timeout=30,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    (d / f"chemblink_{cas}.html").write_bytes(r.content)
    print(cas, len(r.content))
PY
```

预期：打印两个文件字节数（各约 20–60 KB）

- [ ] **步骤 2：编写失败的测试**

```python
from backend.tools.chemical_enrichment.chemblink import parse_product_page


def test_chemblink_prefers_experimental_value():
    html = (FIXTURES / "chemblink_75-18-3.html").read_text(encoding="utf-8")
    data = parse_product_page(html)
    assert data["flash_point"] == "-36℃"
    assert data["boiling_point"] == "38℃"
    assert data["density"] == "0.846 g/mL"


def test_chemblink_plain_value_and_un():
    html = (FIXTURES / "chemblink_2050-92-2.html").read_text(encoding="utf-8")
    data = parse_product_page(html)
    assert data["flash_point"] == "52℃"
    assert data["un_no"] == "2841"


def test_chemblink_ghs_split_into_health_and_fire():
    html = (FIXTURES / "chemblink_75-18-3.html").read_text(encoding="utf-8")
    data = parse_product_page(html)
    assert "易燃液体" in data["fire_hazard"]
```

- [ ] **步骤 3：运行测试验证失败**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k chemblink`
预期：FAIL，`ModuleNotFoundError: No module named 'backend.tools.chemical_enrichment.chemblink'`

- [ ] **步骤 4：编写最少实现代码**

```python
# backend/tools/chemical_enrichment/chemblink.py
import re

from bs4 import BeautifulSoup

FIELD_LABELS = [
    "密度", "熔点", "沸点", "折射率", "闪点", "蒸汽压", "溶解性", "外观", "性状",
    "安全数据", "危险品标志", "危害分类", "分子量", "CAS",
]
FIRE_KEYWORDS = ("易燃", "爆炸", "氧化", "自燃", "自热", "遇水放出", "有机过氧化物", "加压气体")
HEALTH_KEYWORDS = ("急性毒性", "皮肤腐蚀", "皮肤刺激", "严重眼损伤", "眼刺激", "致敏",
                   "致突变", "致癌", "生殖毒性", "特定目标器官毒性", "吸入危害")


def _lines(html: str) -> list[str]:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = BeautifulSoup(text, "lxml").get_text("\n")
    return [x.strip() for x in text.split("\n") if x.strip()]


def _block(lines: list[str], label: str) -> str:
    if label not in lines:
        return ""
    out = []
    for line in lines[lines.index(label) + 1:]:
        if line in FIELD_LABELS:
            break
        out.append(line)
    return " ".join(out)


def _normalize(value: str) -> str:
    value = value.replace("−", "-").replace("°C", "℃").strip(" ,;|*")
    return re.sub(r"\s+", " ", value)


VALUE_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:\s*[-~]\s*-?\d+(?:\.\d+)?)?\s*(?:℃|g/cm\s*3|g/mL))")


def _pick_value(block: str) -> str:
    """优先实验值；无标注实测值次之；只有计算值则返回空串。"""
    if not block:
        return ""
    experimental = re.search(r"([^,;|]*\(实验值\))", block)
    if experimental:
        found = VALUE_RE.search(experimental.group(1))
        if found:
            return _normalize(found.group(1))
    if "计算值" in block and "实验值" not in block:
        return ""
    found = VALUE_RE.search(block)
    return _normalize(found.group(1)) if found else ""


def parse_product_page(html: str) -> dict:
    lines = _lines(html)
    data = {
        "flash_point": _pick_value(_block(lines, "闪点")),
        "boiling_point": _pick_value(_block(lines, "沸点")),
        "density": _pick_value(_block(lines, "密度")),
        "un_no": "",
        "health_hazard": "",
        "fire_hazard": "",
    }
    match = re.search(r"\bUN\s*(\d{4})\b", " ".join(lines))
    if match:
        data["un_no"] = match.group(1)
    health, fire = [], []
    for line in lines:
        is_health = line.startswith(HEALTH_KEYWORDS) and "类别" in line
        is_fire = line.startswith(FIRE_KEYWORDS) and "类别" in line
        if is_health or is_fire:
            (fire if is_fire else health).append(line)
    data["health_hazard"] = "；".join(dict.fromkeys(health))
    data["fire_hazard"] = "；".join(dict.fromkeys(fire))
    return data
```

- [ ] **步骤 5：运行测试验证通过**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k chemblink`
预期：`3 passed`（若夹具实际文案与断言单位有出入，按夹具真实值修正断言并在提交信息中说明）

注意：`VALUE_RE` 要求数值带单位（℃ / g/cm3 / g/mL）；无单位的裸数值（如某些页面的
`密度 0.777`）按「不可溯源」留空处理，符合甲口径。

- [ ] **步骤 6：Commit**

```bash
git add backend/tools/chemical_enrichment/chemblink.py backend/tests/fixtures/chemical_enrichment/chemblink_75-18-3.html backend/tests/fixtures/chemical_enrichment/chemblink_2050-92-2.html backend/tests/test_chemical_library_enrichment.py
git commit -m "feat(chemical-enrichment): ChemBlink 解析器（实验值优先 + GHS 分类分流）"
```

---

### 任务 3：PubChem 解析器（UN / 物理状态 / 爆炸极限 / 引燃温度）

**文件：**
- 创建：`backend/tools/chemical_enrichment/pubchem.py`
- 创建：`backend/tests/fixtures/chemical_enrichment/pubchem_887.json`（甲醇）
- 测试：`backend/tests/test_chemical_library_enrichment.py`（追加）

- [ ] **步骤 1：保存离线夹具**

```bash
python - <<'PY'
import pathlib, requests
d = pathlib.Path("backend/tests/fixtures/chemical_enrichment"); d.mkdir(parents=True, exist_ok=True)
r = requests.get("https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/887/JSON",
                 timeout=60, headers={"User-Agent": "Mozilla/5.0"})
r.raise_for_status()
(d / "pubchem_887.json").write_bytes(r.content)
print(len(r.content))
PY
```

预期：打印 JSON 字节数（约 200–800 KB）

- [ ] **步骤 2：编写失败的测试**

```python
import json

from backend.tools.chemical_enrichment.pubchem import map_physical_state, parse_pug_view


def test_pubchem_extracts_un_and_state():
    record = json.loads((FIXTURES / "pubchem_887.json").read_text(encoding="utf-8"))
    data = parse_pug_view(record)
    assert data["un_no"] == "1230"
    assert data["physical_state"] == "液态"


def test_pubchem_state_mapping_rules():
    assert map_physical_state("A colorless gas with a pungent odor") == "气态"
    assert map_physical_state("White crystalline solid") == "固态"
    assert map_physical_state("Oily liquid") == "液态"
    assert map_physical_state("") == ""
```

- [ ] **步骤 3：运行测试验证失败**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k pubchem`
预期：FAIL，`ModuleNotFoundError: No module named 'backend.tools.chemical_enrichment.pubchem'`

- [ ] **步骤 4：编写最少实现代码**

```python
# backend/tools/chemical_enrichment/pubchem.py
import re

GAS_WORDS = ("gas", "vapor")
SOLID_WORDS = ("solid", "crystal", "powder", "granul")


def map_physical_state(description: str) -> str:
    text = (description or "").lower()
    if not text:
        return ""
    if "liquid" in text:
        return "液态"
    if any(word in text for word in SOLID_WORDS):
        return "固态"
    if any(word in text for word in GAS_WORDS):
        return "气态"
    return ""


def _sections(node: dict) -> list[dict]:
    out = []
    for section in node.get("Section") or []:
        out.append(section)
        out.extend(_sections(section))
    return out


def _first_string(section: dict) -> str:
    for info in section.get("Information") or []:
        value = info.get("Value", {})
        if "StringWithMarkup" in value:
            return " ".join(x.get("String", "") for x in value["StringWithMarkup"]).strip()
        if "Number" in value:
            return str(value["Number"])
    return ""


def _pick(by_heading: dict, heading: str) -> str:
    return next((v for v in by_heading.get(heading, []) if v), "")


def parse_pug_view(record: dict) -> dict:
    by_heading: dict[str, list[str]] = {}
    for section in _sections(record.get("Record", {})):
        heading = section.get("TOCHeading")
        if heading:
            by_heading.setdefault(heading, []).append(_first_string(section))
    data = {
        "un_no": re.sub(r"\D", "", _pick(by_heading, "UN Number")),
        "physical_state": map_physical_state(_pick(by_heading, "Physical Description")),
        "flash_point": _pick(by_heading, "Flash Point"),
        "boiling_point": _pick(by_heading, "Boiling Point"),
        "density": _pick(by_heading, "Density"),
        "ignition_temp": _pick(by_heading, "Autoignition Temperature"),
        "explosion_limit": "",
    }
    lower = _pick(by_heading, "Lower Explosive Limit (LEL)")
    upper = _pick(by_heading, "Upper Explosive Limit (UEL)")
    if lower and upper:
        data["explosion_limit"] = f"{lower}~{upper}"
    return data
```

- [ ] **步骤 5：运行测试验证通过**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k pubchem`
预期：`2 passed`

- [ ] **步骤 6：Commit**

```bash
git add backend/tools/chemical_enrichment/pubchem.py backend/tests/fixtures/chemical_enrichment/pubchem_887.json backend/tests/test_chemical_library_enrichment.py
git commit -m "feat(chemical-enrichment): PubChem 解析器（UN/物理状态/爆炸极限/引燃温度）"
```

---

### 任务 4：合并规则（冲突留空 + 只填空字段）

**文件：**
- 创建：`backend/tools/chemical_enrichment/merge.py`
- 测试：`backend/tests/test_chemical_library_enrichment.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
from backend.tools.chemical_enrichment.merge import FIELDS, merge_sources


def test_merge_conflicting_un_is_left_blank():
    chemblink = {"un_no": "1230", "flash_point": "12℃"}
    pubchem = {"un_no": "1993", "flash_point": "11.7 ℃", "physical_state": "液态",
               "explosion_limit": "6%~36%", "ignition_temp": "", "boiling_point": "64.7 ℃",
               "density": ""}
    merged = merge_sources(chemblink, pubchem)
    assert merged["un_no"] == ""             # 双源冲突 → 留空
    assert merged["flash_point"] == "12℃"    # ChemBlink 优先
    assert merged["physical_state"] == "液态"
    assert merged["explosion_limit"] == "6%~36%"
    assert merged["boiling_point"] == "64.7 ℃"
    assert "un_no" in merged["conflicts"]


def test_merge_does_not_overwrite_existing_values():
    chemblink = {"flash_point": "12℃"}
    pubchem = {"physical_state": "液态"}
    merged = merge_sources(chemblink, pubchem, existing={"flash_point": "管理员手改值"})
    assert merged["flash_point"] == "管理员手改值"
    assert merged["physical_state"] == "液态"
    assert set(merged) >= set(FIELDS) | {"conflicts"}
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k merge`
预期：FAIL，`ModuleNotFoundError: No module named 'backend.tools.chemical_enrichment.merge'`

- [ ] **步骤 3：编写最少实现代码**

```python
# backend/tools/chemical_enrichment/merge.py
import re

FIELDS = [
    "un_no", "physical_state", "flash_point", "explosion_limit", "ignition_temp",
    "density", "boiling_point", "health_hazard", "fire_hazard",
]


def _number(value: str):
    match = re.search(r"-?\d+(?:\.\d+)?", value or "")
    return float(match.group(0)) if match else None


def _conflict(field: str, left: str, right: str) -> bool:
    if field == "un_no":
        return left != right
    a, b = _number(left), _number(right)
    if a is None or b is None:
        return False
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base > 0.10


def merge_sources(chemblink: dict, pubchem: dict, existing: dict | None = None) -> dict:
    """合并两源取值：已有值不动；冲突留空并计入 conflicts；其余按 ChemBlink → PubChem 优先。"""
    existing = existing or {}
    merged: dict = {}
    conflicts: list[str] = []
    for field in FIELDS:
        current = (existing.get(field) or "").strip()
        if current:
            merged[field] = current
            continue
        left = (chemblink.get(field) or "").strip()
        right = (pubchem.get(field) or "").strip()
        if left and right and _conflict(field, left, right):
            merged[field] = ""
            conflicts.append(field)
            continue
        merged[field] = left or right
    merged["conflicts"] = conflicts
    return merged
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k merge`
预期：`2 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/tools/chemical_enrichment/merge.py backend/tests/test_chemical_library_enrichment.py
git commit -m "feat(chemical-enrichment): 合并规则（冲突留空 + 只填空字段）"
```

---

### 任务 5：幂等 SQL 生成器

**文件：**
- 创建：`backend/tools/chemical_enrichment/sqlgen.py`
- 测试：`backend/tests/test_chemical_library_enrichment.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
from backend.tools.chemical_enrichment.sqlgen import render_update_sql


def test_sql_uses_coalesce_nullif_and_only_present_fields():
    row = {"id": "11111111-1111-1111-1111-111111111111",
           "values": {"un_no": "1230", "flash_point": "12℃", "boiling_point": ""}}
    sql = render_update_sql([row])
    assert "COALESCE(NULLIF(un_no,''), '1230')" in sql
    assert "flash_point" in sql
    assert "boiling_point" not in sql
    assert sql.strip().endswith(";")


def test_sql_skips_rows_without_any_value():
    row = {"id": "22222222-2222-2222-2222-222222222222",
           "values": {"un_no": "", "flash_point": "  "}}
    assert render_update_sql([row]).strip() == ""


def test_sql_escapes_single_quotes():
    row = {"id": "33333333-3333-3333-3333-333333333333",
           "values": {"health_hazard": "眼刺激；3,3'-二甲基"}}
    assert "3,3''-二甲基" in render_update_sql([row])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k sqlgen`
预期：FAIL，`ModuleNotFoundError: No module named 'backend.tools.chemical_enrichment.sqlgen'`

- [ ] **步骤 3：编写最少实现代码**

```python
# backend/tools/chemical_enrichment/sqlgen.py
import json
from pathlib import Path

HEADER = """-- 2026-09-10 化学品库字段富集（ChemBlink + PubChem，只填空不覆盖）
-- 生成脚本：backend/tools/enrich_chemical_library.py
-- 口径：只采实验值/无标注实测值；纯计算值留空；双源冲突留空并记录在报告中。
-- 幂等：逐字段 COALESCE(NULLIF(字段,''), 新值)，可重复执行。
"""


def build_row(row_id: str, values: dict) -> dict:
    return {"id": row_id, "values": dict(values)}


def _escape(value: str) -> str:
    return value.replace("'", "''")


def render_update_sql(rows: list[dict]) -> str:
    lines: list[str] = []
    for row in rows:
        values = {k: v.strip() for k, v in row["values"].items() if (v or "").strip()}
        if not values:
            continue
        assignments = ", ".join(
            f"{field} = COALESCE(NULLIF({field},''), '{_escape(value)}')"
            for field, value in values.items()
        )
        lines.append(f"UPDATE chemical_library SET {assignments} WHERE id = '{row['id']}';")
    if not lines:
        return ""
    return HEADER + "\n" + "\n".join(lines) + "\n"


def write_outputs(rows: list[dict], sql_path: Path, json_path: Path) -> None:
    sql_path.write_text(render_update_sql(rows), encoding="utf-8", newline="\n")
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m pytest backend/tests/test_chemical_library_enrichment.py -q -k sqlgen`
预期：`3 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/tools/chemical_enrichment/sqlgen.py backend/tests/test_chemical_library_enrichment.py
git commit -m "feat(chemical-enrichment): 幂等 SQL/JSON 生成器"
```

---

### 任务 6：CLI 编排 + 全量抓取（2831 条）

**文件：**
- 创建：`backend/tools/enrich_chemical_library.py`
- 产出：`backend/data/chemical_library_enrichment_20260910.json`
- 产出：`backend/db_migration_20260910_chemical_library_enrich.sql`
- 产出：`docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md`

- [ ] **步骤 1：编写 CLI**

```python
# backend/tools/enrich_chemical_library.py
"""化学品库字段富集 CLI。

用法：
  python backend/tools/enrich_chemical_library.py --from-db --limit 30 --out-dir /tmp/smoke
  python backend/tools/enrich_chemical_library.py --from-db --out-dir backend
"""
import argparse
import json
import subprocess
import sys
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


def load_rows_from_db() -> list[list[str]]:
    sql = ("SELECT id::text || chr(9) || name || chr(9) || cas_no FROM chemical_library "
           "WHERE cas_no IS NOT NULL AND cas_no <> '' ORDER BY id")
    out = subprocess.run(
        ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
         "-tAc", sql],
        capture_output=True, text=True, encoding="utf-8", check=True)
    return [line.split("\t") for line in out.stdout.splitlines() if line.strip()]


def resolve_pubchem(fetcher: CachedFetcher, cas: str) -> dict:
    cid = json.loads(fetcher.text(PUBCHEM_CID.format(cas=cas)))["IdentifierList"]["CID"][0]
    record = json.loads(fetcher.text(PUBCHEM_VIEW.format(cid=cid)))
    return parse_pug_view(record), cid


def build_report(rows, results, failed, conflicts, same_cas_groups) -> str:
    total = len(rows)
    lines = ["# 化学品库字段富集报告（2026-09-10）", "",
             f"- 条目总数：{total}", f"- 成功富集：{len(results)}", f"- 抓取失败：{len(failed)}",
             f"- 双源冲突（已留空）：{len(conflicts)}", "",
             "## 字段覆盖率", "", "| 字段 | 有值条数 | 占比 |", "|---|---|---|"]
    for field in FIELDS:
        filled = sum(1 for r in results if (r["values"].get(field) or "").strip())
        lines.append(f"| {field} | {filled} | {filled * 100 / max(total, 1):.1f}% |")
    lines += ["", "## 抓取失败清单", ""]
    lines += [f"- {f['name']}（{f['cas']}）：{f['error']}" for f in failed[:200]] or ["- 无"]
    lines += ["", "## 双源冲突清单（相关字段已留空）", ""]
    lines += [f"- {c['name']}（{c['cas']}）：{', '.join(c['fields'])}" for c in conflicts[:200]] or ["- 无"]
    lines += ["", "## 同 CAS 多规格条目（共享同一组数值）", ""]
    lines += [f"- CAS {cas}：{', '.join(names)}" for cas, names in same_cas_groups[:200]] or ["- 无"]
    lines += ["", "## 人工复核抽样（30 条）", "",
              "| 品名 | CAS | UN号 | 物理状态 | 闪点 | 沸点 | 密度 | 源链接 |", "|---|---|---|---|---|---|---|---|"]
    for r in results[:30]:
        v = r["values"]
        lines.append(
            f"| {r['name']} | {r['cas']} | {v.get('un_no','')} | {v.get('physical_state','')} | "
            f"{v.get('flash_point','')} | {v.get('boiling_point','')} | {v.get('density','')} | "
            f"[ChemBlink](https://www.chemblink.com/zh/products/{r['cas']}C.htm) |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", help="TSV：id\\tname\\tcas（与 --from-db 二选一）")
    parser.add_argument("--from-db", action="store_true")
    parser.add_argument("--out-dir", default="backend")
    parser.add_argument("--cache-dir", default=".cache/chemical_enrichment")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = load_rows_from_db() if args.from_db else [
        line.split("\t") for line in Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    fetcher = CachedFetcher(Path(args.cache_dir))
    results, failed, conflicts = [], [], []
    for index, (row_id, name, cas) in enumerate(rows, 1):
        try:
            pubchem, _cid = resolve_pubchem(fetcher, cas)
            chemblink = parse_product_page(fetcher.text(CHEMBLINK_PAGE.format(cas=cas)))
        except Exception as exc:
            failed.append({"id": row_id, "name": name, "cas": cas, "error": str(exc)[:200]})
            continue
        merged = merge_sources(chemblink, pubchem)
        if merged["conflicts"]:
            conflicts.append({"id": row_id, "name": name, "cas": cas, "fields": merged["conflicts"]})
        results.append({"id": row_id, "name": name, "cas": cas,
                        "values": {field: merged[field] for field in FIELDS}})
        if index % 100 == 0:
            print(f"progress {index}/{len(rows)}", flush=True)

    out = Path(args.out_dir)
    (out / "data").mkdir(parents=True, exist_ok=True)
    write_outputs(results, out / "db_migration_20260910_chemical_library_enrich.sql",
                  out / "data" / "chemical_library_enrichment_20260910.json")
    grouped: dict[str, list[str]] = {}
    for row in results:
        grouped.setdefault(row["cas"], []).append(row["name"])
    same_cas = [(cas, names) for cas, names in grouped.items() if len(names) > 1]
    report = build_report(rows, results, failed, conflicts, same_cas)
    report_path = Path("docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print(f"rows={len(rows)} enriched={len(results)} failed={len(failed)} conflicts={len(conflicts)}")


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：小批量冒烟（30 条）**

运行：`python backend/tools/enrich_chemical_library.py --from-db --limit 30 --out-dir /tmp/enrich_smoke`
预期：输出 `rows=30 enriched>=25 failed<=5 conflicts>=0`；`/tmp/enrich_smoke/db_migration_20260910_chemical_library_enrich.sql` 含 `COALESCE(NULLIF(`

- [ ] **步骤 3：全量抓取（约 40–60 分钟）**

运行：`python backend/tools/enrich_chemical_library.py --from-db --out-dir backend`
预期：`rows=2831 enriched>=2600 failed<=200`；产出 SQL（1–2 MB）、JSON、报告三个文件；中断后重跑命中缓存

- [ ] **步骤 4：核对报告内容**

打开 `docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md`，确认包含：字段覆盖率表、失败清单、冲突清单、同 CAS 多规格清单、30 条人工复核抽样（含源链接）。覆盖率应与规格第 2.3 节区间大体一致（偏差大时在报告中说明原因）。

- [ ] **步骤 5：Commit**

```bash
git add backend/tools/enrich_chemical_library.py backend/data/chemical_library_enrichment_20260910.json backend/db_migration_20260910_chemical_library_enrich.sql docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md
git commit -m "feat(chemical-enrichment): 全量富集产出（2831 条 + 幂等 SQL + 报告）"
```

---

### 任务 7：开发环境落库 + 幂等与抽样验证

**文件：**
- 无新增文件

- [ ] **步骤 1：应用迁移**

```bash
docker cp backend/db_migration_20260910_chemical_library_enrich.sql emergency-plan-backend:/app/
docker restart emergency-plan-backend
sleep 8
docker logs --tail 20 emergency-plan-backend
docker exec emergency-plan-db psql -U postgres -d emergency_plan -tAc "SELECT script_name FROM schema_migrations WHERE script_name LIKE '%enrich%'"
```

预期：日志无 `迁移脚本执行失败`；最后一条返回 `db_migration_20260910_chemical_library_enrich.sql`

- [ ] **步骤 2：覆盖率核对**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) FILTER (WHERE un_no <> '') AS un, count(*) FILTER (WHERE physical_state <> '') AS state, count(*) FILTER (WHERE flash_point <> '') AS flash, count(*) FILTER (WHERE boiling_point <> '') AS boiling, count(*) FILTER (WHERE density <> '') AS density, count(*) FILTER (WHERE explosion_limit <> '') AS limits, count(*) FILTER (WHERE ignition_temp <> '') AS ignition, count(*) FILTER (WHERE health_hazard <> '') AS health, count(*) FILTER (WHERE fire_hazard <> '') AS fire FROM chemical_library;"
```

预期：un 1400–1900、state 2000–2500、flash 1200–1800、boiling/density 1600–2000、limits 500–900、ignition 400–800、health/fire 2000–2500

- [ ] **步骤 3：幂等验证（重放不覆盖已有值）**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -tAc "SELECT count(*) FROM chemical_library WHERE un_no <> ''"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "UPDATE chemical_library SET un_no='哨兵值' WHERE name='甲醇'"
docker cp backend/db_migration_20260910_chemical_library_enrich.sql emergency-plan-db:/tmp/enrich.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -f /tmp/enrich.sql > /dev/null
docker exec emergency-plan-db psql -U postgres -d emergency_plan -tAc "SELECT un_no FROM chemical_library WHERE name='甲醇'"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -tAc "SELECT count(*) FROM chemical_library WHERE un_no <> ''"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "UPDATE chemical_library SET un_no='1230' WHERE name='甲醇'"
```

预期：哨兵值保持 `哨兵值`，计数与第一次相同（说明幂等且不覆盖）

- [ ] **步骤 4：抽样复核 30 条**

```bash
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT name, cas_no, un_no, physical_state, flash_point, boiling_point, density FROM chemical_library WHERE flash_point <> '' ORDER BY md5(id::text) LIMIT 30"
```

逐条对照 ChemBlink 产品页与 PubChem 页面，把差异写入报告「人工复核」小节（含不一致原因）。

- [ ] **步骤 5：Commit 报告修订**

```bash
git add docs/superpowers/reports/2026-09-10-chemical-library-enrichment.md
git commit -m "docs(chemical-enrichment): 落库后覆盖率与 30 条抽样复核结果"
```

---

### 任务 8：回归与交付确认

**文件：**
- 无新增文件

- [ ] **步骤 1：后端回归**

```bash
python -m pytest backend/tests/test_chemical_library_enrichment.py -q
docker exec emergency-plan-backend python -m pytest tests/test_chemical_library.py -q
```

预期：富集测试全部通过（宿主运行，脚本不依赖 `app.*`）；容器内既有化学库用例 10 passed

- [ ] **步骤 2：前端防回归（本次不改前端）**

```bash
docker exec emergency-plan-frontend sh -c 'cd /app && node node_modules/typescript/bin/tsc -b --force > /tmp/tsc.log 2>&1; echo TSC_EXIT=$?; npx vitest run 2>&1 | tail -5'
```

预期：`TSC_EXIT=0`；vitest `32 passed` / `189 passed`

- [ ] **步骤 3：服务健康检查**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8082/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8082/api/v1/health
```

预期：两个 200

- [ ] **步骤 4：最终核对**

```bash
git status --short
git log --oneline -8
```

预期：本任务文件均已提交；`TASKS.md` 与其它并行会话改动保持未提交
