# 重大危险源辨识报告导出实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把「单元台账 + 品种存量 + 计算快照 + 档案备案 + 法规依据」装配成一份可交付的《危险化学品重大危险源辨识报告》DOCX，并可从界面一键导出。

**架构：** 复用现有公文版式能力——`app/services/report_docx.py` 的 `generate_report_docx(*, company_name, report_kind, chapters, report_title)` 接收 `[{"key","title","content"}]` 输出 `Document`，导出走 `settings.EXPORT_DIR` + `FileResponse`（照 `routers/export.py:396-407`）。本计划只新增「装配章节」这一层，**不重写版式**。

**技术栈：** Python 3.12 / FastAPI / python-docx / pytest。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §6.6

**依赖：** 计划 1（已完成并合入 master）。计划 3 非必需（后端可独立验证），但前端入口按钮在计划 3 里。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/services/major_hazard_report_data.py`（新建） | 装配报告章节数据：拉单元/品种/快照/档案/依据，产 `chapters` |
| `backend/app/routers/major_hazard.py`（修改） | 新增 `GET /units/{unit_id}/report.docx` |
| `backend/tests/test_major_hazard_report_data.py`（新建） | 章节装配的纯逻辑测试 |
| `backend/tests/test_major_hazard_report_api.py`（新建） | 导出端点测试 |

**既有约定**

- 复用 `app/services/report_docx.py:141` 的 `generate_report_docx`，不要新写版式代码
- 章节 content 支持 markdown/HTML 混合（表格用 markdown 表格即可，`docx_template.build_table` 会转）
- 导出目录 `settings.EXPORT_DIR`，文件名做非法字符替换（照 `export.py:398` 的 `re.sub(r'[\/*?:"<>|]', "_", ...)`）

---

## 报告章节设计（先定内容，再写代码）

| key | 标题 | 内容来源 |
|---|---|---|
| `basic` | 一、企业基本情况 | `Enterprise.name`、档案里的包保责任人 |
| `basis` | 二、辨识依据与方法 | 固定文本 + `evidence_refs` 的条文锚点列表 |
| `units` | 三、重大危险源单元清单 | `major_hazard_units`（名称/类型/位置/责任部门·人） |
| `chemicals` | 四、单元内危险化学品与临界量 | `major_hazard_unit_chemicals`（名称/设计最大量/Q/β/来源） |
| `metrics` | 五、辨识指标计算 | 最近快照的 `s_value` + 逐品种 `q/Q` 明细 |
| `grading` | 六、分级判定 | 最近快照的 `alpha` / `r_value` / `level`；**不构成时明确写"不构成"** |
| `conclusion` | 七、辨识结论 | 由快照结论生成的一句话结论 |
| `responsible` | 八、包保责任人 | `major_hazard_records` 的三组责任人 |
| `appendix` | 附录：法规依据条文 | `evidence_refs` 的 `article_anchor` 列表（按 created_at 排序） |

**两条内容规则（务必遵守）：**

1. **没有计算快照就不允许导出**——没有结论的报告是废纸，且会让"未计算"被误读成"不构成"。导出端点返回 422 并提示"该单元尚未进行辨识计算，请先在计算与分级页固化一次结果"。
2. **不构成时，`grading` 与 `conclusion` 必须显式写"不构成危险化学品重大危险源"**，而不是留空或写"—"。空着会被当成"没做"。

---

## 任务 1：报告数据装配服务

**文件：**

- 创建：`backend/app/services/major_hazard_report_data.py`
- 测试：`backend/tests/test_major_hazard_report_data.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""报告章节装配：纯逻辑测试，不连数据库。"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.major_hazard_report_data import (
    ReportNotReadyError,
    build_chapters,
    conclusion_sentence,
)


def _unit(name="罐区A", unit_type="storage"):
    u = MagicMock()
    u.name = name
    u.unit_type = unit_type
    u.address = "厂区北侧"
    u.department = "生产部"
    u.responsible_person = "张峰"
    u.responsible_phone = "13800000000"
    u.unit_type = unit_type
    u.boundary_desc = "以罐区防火堤为界"
    return u


def _chem(name, q, Q, beta, source="table3"):
    c = MagicMock()
    c.chemical_name = name
    c.q_design_max = Decimal(str(q))
    c.critical_quantity_t = Decimal(str(Q))
    c.beta = Decimal(str(beta))
    c.beta_source = source
    c.physical_state = "液态"
    c.storage_location = "罐区A"
    return c


def _snapshot(is_major=True, level="四级", s=1.5, r=7.5, alpha=1.5, pop=60):
    return {
        "seq": 1,
        "s_value": s,
        "r_value": r,
        "alpha": alpha,
        "exposed_population": pop,
        "is_major_hazard": is_major,
        "level": level,
        "formula_version": "GB18218-2018",
        "chemicals": [
            {"name": "氯", "q": 5.0, "Q": 5.0, "beta": 4.0, "q_over_Q": 1.0,
             "beta_times_q_over_Q": 4.0},
            {"name": "氨", "q": 5.0, "Q": 10.0, "beta": 2.0, "q_over_Q": 0.5,
             "beta_times_q_over_Q": 1.0},
        ],
    }


def _record():
    r = MagicMock()
    r.hazard_code = "TYKJ001"
    r.filing_status = "已备案"
    r.chief_name = "李总"
    r.tech_name = "王工"
    r.oper_name = "张峰"
    return r


def test_conclusion_sentence_for_major_hazard():
    s = conclusion_sentence(_snapshot(), "罐区A")
    assert "罐区A" in s
    assert "构成" in s
    assert "四级" in s
    assert "GB 18218" in s


def test_conclusion_sentence_for_non_major():
    s = conclusion_sentence(_snapshot(is_major=False, level=None, s=0.4, r=2.0), "锅炉房")
    assert "不构成" in s
    assert "未达到" in s
    assert "四级" not in s


def test_build_chapters_requires_snapshot():
    """没有快照就不允许出报告——空报告会被误读成"不构成"。"""
    with pytest.raises(ReportNotReadyError) as ei:
        build_chapters(
            enterprise_name="某公司",
            unit=_unit(),
            chemicals=[_chem("氯", 5, 5, 4)],
            snapshot=None,
            record=None,
            evidences=[],
        )
    assert "尚未进行辨识计算" in str(ei.value)


def test_build_chapters_has_all_sections_in_order():
    chapters = build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4), _chem("氨", 5, 10, 2)],
        snapshot=_snapshot(),
        record=_record(),
        evidences=[{"article_anchor": "GB 18218-2018 4.2.1", "relation": "依据"}],
    )
    keys = [c["key"] for c in chapters]
    assert keys == [
        "basic", "basis", "units", "chemicals",
        "metrics", "grading", "conclusion", "responsible", "appendix",
    ]
    for c in chapters:
        assert c["title"] and c["content"]


def test_chemicals_chapter_contains_q_and_beta():
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4), _chem("氨", 5, 10, 2)],
        snapshot=_snapshot(),
        record=None,
        evidences=[],
    )}
    assert "氯" in chapters["chemicals"]["content"]
    assert "5" in chapters["chemicals"]["content"]
    assert "4" in chapters["chemicals"]["content"]  # β


def test_grading_chapter_explicit_for_non_major():
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(name="锅炉房"),
        chemicals=[_chem("氯", 1, 5, 4)],
        snapshot=_snapshot(is_major=False, level=None, s=0.2, r=0.8),
        record=None,
        evidences=[],
    )}
    assert "不构成" in chapters["grading"]["content"]
    assert "不构成" in chapters["conclusion"]["content"]


def test_appendix_lists_evidence_anchors():
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4)],
        snapshot=_snapshot(),
        record=None,
        evidences=[
            {"article_anchor": "GB 18218-2018 4.2.1", "relation": "依据"},
            {"article_anchor": "GB 18218-2018 4.3.2", "relation": "依据"},
        ],
    )}
    assert "GB 18218-2018 4.2.1" in chapters["appendix"]["content"]
    assert "GB 18218-2018 4.3.2" in chapters["appendix"]["content"]


def test_responsible_chapter_omitted_when_no_record():
    """没建档时该章留占位说明，不能整章消失（章节完整性会被审查）。"""
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4)],
        snapshot=_snapshot(),
        record=None,
        evidences=[],
    )}
    assert "responsible" in chapters
    assert "尚未建立" in chapters["responsible"]["content"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_report_data.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.major_hazard_report_data'`

- [ ] **步骤 3：编写实现**

```python
"""重大危险源辨识报告：章节装配（纯数据，不碰 docx）。

把版式与内容分开：本模块只产 [{"key","title","content"}]，
交给 app/services/report_docx.generate_report_docx 渲染。
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Iterable, Optional

logger = logging.getLogger("major_hazard_report_data")

STANDARD_LABEL = "GB 18218-2018《危险化学品重大危险源辨识》"

UNIT_TYPE_LABEL = {"production": "生产单元", "storage": "储存单元"}


class ReportNotReadyError(ValueError):
    """报告所需数据不完整（最常见：还没固化过计算快照）。"""


def _num(value: Any, digits: int = 6) -> str:
    """Decimal/float → 去尾零字符串；None → '—'。"""
    if value is None:
        return "—"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return str(round(n, digits)).rstrip("0").rstrip(".") or "0"


def conclusion_sentence(snapshot: dict, unit_name: str) -> str:
    """生成辨识结论一句话。不构成时也要显式写出来，不能留空。"""
    if snapshot.get("is_major_hazard"):
        return (
            f"经辨识，本单位「{unit_name}」内危险化学品的数量已等于或超过 "
            f"{STANDARD_LABEL} 表1/表2 规定的临界量，构成危险化学品重大危险源，"
            f"分级指标 R = {_num(snapshot.get('r_value'))}，"
            f"判定为**{snapshot.get('level') or '（未定级）'}重大危险源**。"
        )
    return (
        f"经辨识，本单位「{unit_name}」内危险化学品的数量未达到 "
        f"{STANDARD_LABEL} 表1/表2 规定的临界量，"
        f"不构成危险化学品重大危险源（辨识指标 s = {_num(snapshot.get('s_value'))} < 1）。"
    )


def _basic_chapter(enterprise_name: str, unit, record) -> dict:
    lines = [
        f"- 单位名称：{enterprise_name}",
        f"- 单元名称：{unit.name}",
        f"- 单元类型：{UNIT_TYPE_LABEL.get(unit.unit_type, unit.unit_type)}",
    ]
    if getattr(unit, "boundary_desc", None):
        lines.append(f"- 单元边界：{unit.boundary_desc}")
    if getattr(unit, "address", None):
        lines.append(f"- 所在位置：{unit.address}")
    if getattr(unit, "department", None) or getattr(unit, "responsible_person", None):
        lines.append(
            f"- 责任部门及责任人：{getattr(unit, 'department', None) or '—'} / "
            f"{getattr(unit, 'responsible_person', None) or '—'}"
        )
    if record is not None and getattr(record, "hazard_code", None):
        lines.append(f"- 重大危险源编码：{record.hazard_code}")
    return {"key": "basic", "title": "一、企业基本情况", "content": "\n".join(lines)}


def _basis_chapter(evidences: Iterable[dict]) -> dict:
    anchors = [e.get("article_anchor") for e in evidences if e.get("article_anchor")]
    lines = [
        f"本报告依据 {STANDARD_LABEL} 编制。",
        "",
        "辨识方法：单元内存在危险化学品的数量等于或超过表1、表2 规定的临界量时，"
        "即定为重大危险源。多品种按式(1) 计算，s ≥ 1 即构成；"
        "分级按式(2) R = α × Σ βi × (qi/Qi) 计算，按表6 判定级别。",
    ]
    if anchors:
        lines += ["", "具体引用条文："] + [f"- {a}" for a in anchors]
    return {"key": "basis", "title": "二、辨识依据与方法", "content": "\n".join(lines)}


def _units_chapter(unit) -> dict:
    rows = [
        "| 单元名称 | 单元类型 | 所在位置 | 责任部门 | 责任人 |",
        "|---|---|---|---|---|",
        f"| {unit.name} | {UNIT_TYPE_LABEL.get(unit.unit_type, unit.unit_type)} | "
        f"{getattr(unit, 'address', None) or '—'} | {getattr(unit, 'department', None) or '—'} | "
        f"{getattr(unit, 'responsible_person', None) or '—'} |",
    ]
    return {"key": "units", "title": "三、重大危险源单元清单", "content": "\n".join(rows)}


def _chemicals_chapter(chemicals: list) -> dict:
    rows = [
        "| 危险化学品 | 物理状态 | 设计最大量 q(t) | 临界量 Q(t) | 校正系数 β | β 来源 |",
        "|---|---|---|---|---|---|",
    ]
    for c in chemicals:
        source_label = {
            "table3": "表3（按名称）",
            "table4": "表4（按危险性类别）",
            "manual": "人工指定",
        }.get(getattr(c, "beta_source", "manual"), "人工指定")
        rows.append(
            f"| {c.chemical_name} | {getattr(c, 'physical_state', None) or '—'} | "
            f"{_num(c.q_design_max)} | {_num(c.critical_quantity_t)} | "
            f"{_num(c.beta, 3)} | {source_label} |"
        )
    rows += [
        "",
        "注：设计最大量按 GB 18218-2018 4.2.2 确定——储罐及其他容器、设备或仓储区的"
        "危险化学品实际存在量按设计最大量计，非台账登记的日常储存量。",
    ]
    return {"key": "chemicals", "title": "四、单元内危险化学品与临界量", "content": "\n".join(rows)}


def _metrics_chapter(snapshot: dict) -> dict:
    rows = [
        "| 危险化学品 | qi(t) | Qi(t) | qi/Qi | βi | βi×qi/Qi |",
        "|---|---|---|---|---|---|",
    ]
    for item in snapshot.get("chemicals", []):
        rows.append(
            f"| {item['name']} | {_num(item['q'])} | {_num(item['Q'])} | "
            f"{_num(item['q_over_Q'])} | {_num(item['beta'], 3)} | "
            f"{_num(item['beta_times_q_over_Q'])} |"
        )
    rows += [
        "",
        f"按式(1)：**s = Σqi/Qi = {_num(snapshot.get('s_value'))}**",
        f"结论：{'构成' if snapshot.get('is_major_hazard') else '不构成'}重大危险源"
        f"（{'s ≥ 1' if snapshot.get('is_major_hazard') else 's < 1'}）。",
    ]
    return {"key": "metrics", "title": "五、辨识指标计算", "content": "\n".join(rows)}


def _grading_chapter(snapshot: dict) -> dict:
    if not snapshot.get("is_major_hazard"):
        return {
            "key": "grading",
            "title": "六、分级判定",
            "content": (
                f"该单元辨识指标 s = {_num(snapshot.get('s_value'))} < 1，"
                "**不构成危险化学品重大危险源**，故不进行分级判定。"
            ),
        }
    return {
        "key": "grading",
        "title": "六、分级判定",
        "content": "\n".join(
            [
                f"- 厂区外 500m 范围内可能暴露人员数量：{snapshot.get('exposed_population')} 人",
                f"- 暴露人员校正系数 α：{_num(snapshot.get('alpha'), 2)}（GB 18218-2018 表5）",
                f"- 分级指标 R = α × Σβi×(qi/Qi) = **{_num(snapshot.get('r_value'))}**",
                f"- 判定级别：**{snapshot.get('level') or '（未定级）'}**（GB 18218-2018 表6）",
                "",
                "分级标准：一级 R≥100；二级 100>R≥50；三级 50>R≥10；四级 R<10。",
            ]
        ),
    }


def _conclusion_chapter(snapshot: dict, unit) -> dict:
    return {
        "key": "conclusion",
        "title": "七、辨识结论",
        "content": conclusion_sentence(snapshot, unit.name),
    }


def _responsible_chapter(record) -> dict:
    if record is None:
        return {
            "key": "responsible",
            "title": "八、包保责任人",
            "content": "该单元**尚未建立档案**，包保责任人信息待补充后另行报备。",
        }
    rows = [
        "| 职责 | 姓名 | 职务 | 联系电话 |",
        "|---|---|---|---|",
    ]
    for label, prefix in (("主要负责人", "chief"), ("技术负责人", "tech"), ("操作负责人", "oper")):
        rows.append(
            f"| {label} | {getattr(record, f'{prefix}_name', None) or '—'} | "
            f"{getattr(record, f'{prefix}_post', None) or '—'} | "
            f"{getattr(record, f'{prefix}_phone', None) or '—'} |"
        )
    return {"key": "responsible", "title": "八、包保责任人", "content": "\n".join(rows)}


def _appendix_chapter(evidences: Iterable[dict]) -> dict:
    items = list(evidences)
    if not items:
        content = "本报告未单独挂载法规条文依据。"
    else:
        lines = []
        for e in items:
            note = f"（{e['note']}）" if e.get("note") else ""
            relation = e.get("relation") or "依据"
            lines.append(f"- {e['article_anchor']} — {relation}{note}")
        content = "\n".join(lines)
    return {"key": "appendix", "title": "附录：法规依据条文", "content": content}


def build_chapters(
    *,
    enterprise_name: str,
    unit,
    chemicals: list,
    snapshot: Optional[dict],
    record: Optional[Any],
    evidences: Iterable[dict],
) -> list[dict]:
    """装配全部章节。没有计算快照时直接拒绝——没有结论的报告是废纸。"""
    if snapshot is None:
        raise ReportNotReadyError(
            "该单元尚未进行辨识计算，请先在「计算与分级」页固化一次结果后再导出报告"
        )
    evidence_list = list(evidences)
    return [
        _basic_chapter(enterprise_name, unit, record),
        _basis_chapter(evidence_list),
        _units_chapter(unit),
        _chemicals_chapter(chemicals),
        _metrics_chapter(snapshot),
        _grading_chapter(snapshot),
        _conclusion_chapter(snapshot, unit),
        _responsible_chapter(record),
        _appendix_chapter(evidence_list),
    ]
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_report_data.py -v
```

预期：`8 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/major_hazard_report_data.py backend/tests/test_major_hazard_report_data.py
git commit -m "feat(major-hazard): 辨识报告章节装配（无快照拒绝导出、不构成显式措辞）（任务 1/3）"
```

---

## 任务 2：导出端点

**文件：**

- 修改：`backend/app/routers/major_hazard.py`
- 测试：`backend/tests/test_major_hazard_report_api.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""报告导出端点测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import major_hazard
from app.services.major_hazard_report_data import ReportNotReadyError


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _client(handler):
    app = FastAPI()
    app.include_router(major_hazard.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_report_returns_422_when_no_snapshot():
    """没有快照时返回 422 + 可读原因，而不是 500，也不要出一个空报告。"""
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    enterprise = MagicMock()
    enterprise.name = "某公司"

    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit])
        if "enterprises" in text:
            return _Result([enterprise])
        if "major_hazard_unit_chemicals" in text:
            return _Result([MagicMock()])
        if "major_hazard_calculations" in text:
            return _Result([])  # 没有快照
        return _Result([])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units/u1/report.docx")
    assert resp.status_code == 422
    assert "辨识计算" in resp.json()["detail"]


def test_report_returns_docx_when_ready(tmp_path):
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.name = "罐区A"
    enterprise = MagicMock()
    enterprise.name = "某公司"
    snap = MagicMock()
    snap.inputs_snapshot = {
        "s_value": 1.5,
        "r_value": 7.5,
        "alpha": 1.5,
        "exposed_population": 60,
        "is_major_hazard": True,
        "level": "四级",
        "chemicals": [{"name": "氯", "q": 5.0, "Q": 5.0, "beta": 4.0,
                       "q_over_Q": 1.0, "beta_times_q_over_Q": 4.0}],
    }
    written = {}

    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit])
        if "enterprises" in text:
            return _Result([enterprise])
        if "major_hazard_unit_chemicals" in text:
            chem = MagicMock()
            chem.chemical_name = "氯"
            chem.q_design_max = 5
            chem.critical_quantity_t = 5
            chem.beta = 4
            chem.beta_source = "table3"
            chem.physical_state = "液态"
            return _Result([chem])
        if "major_hazard_calculations" in text:
            return _Result([snap])
        return _Result([])

    class _FakeDoc:
        def save(self, path):
            written["path"] = path
            open(path, "wb").write(b"PK\x03\x04fake")

    with patch(
        "app.routers.major_hazard.generate_report_docx", return_value=_FakeDoc()
    ):
        client = _client(handler)
        resp = client.get("/api/v1/major-hazard/units/u1/report.docx")

    assert resp.status_code == 200
    assert "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert written.get("path"), "必须落盘"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_report_api.py -q
```

预期：FAIL（404，路由不存在）

- [ ] **步骤 3：实现端点**

在 `backend/app/routers/major_hazard.py` 顶部补 import：

```python
import os
import re

from fastapi.responses import FileResponse

from app.config import settings
from app.models.enterprise import Enterprise
from app.services.major_hazard_report_data import ReportNotReadyError, build_chapters
from app.services.report_docx import generate_report_docx
```

文件末尾追加：

```python
@router.get("/units/{unit_id}/report.docx")
async def export_unit_report(unit_id: str, db: AsyncSession = Depends(get_db)):
    """导出《危险化学品重大危险源辨识报告》。没有计算快照时拒绝导出。"""
    unit_res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = unit_res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")

    ent_res = await db.execute(select(Enterprise).where(Enterprise.id == unit.enterprise_id))
    enterprise = ent_res.scalar_one_or_none()
    enterprise_name = getattr(enterprise, "name", "") or "（未填写单位名称）"

    chem_res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    chemicals = list(chem_res.scalars().all())

    calc_res = await db.execute(
        select(MajorHazardCalculation)
        .where(MajorHazardCalculation.unit_id == unit_id)
        .order_by(MajorHazardCalculation.seq.desc())
        .limit(1)
    )
    latest = calc_res.scalar_one_or_none()
    snapshot = latest.inputs_snapshot if latest is not None else None

    rec_res = await db.execute(select(MajorHazardRecord).where(MajorHazardRecord.unit_id == unit_id))
    record = rec_res.scalar_one_or_none()

    evidences = await list_evidence(db, owner_type="major_hazard_unit", owner_id=unit_id)

    try:
        chapters = build_chapters(
            enterprise_name=enterprise_name,
            unit=unit,
            chemicals=chemicals,
            snapshot=snapshot,
            record=record,
            evidences=evidences,
        )
    except ReportNotReadyError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        doc = generate_report_docx(
            company_name=enterprise_name,
            report_kind="major_hazard_identification",
            chapters=chapters,
            report_title="危险化学品重大危险源辨识报告",
        )
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        safe_unit = re.sub(r'[\\/*?:"<>|]', "_", unit.name)
        filename = f"重大危险源辨识报告-{safe_unit}.docx"
        filepath = os.path.join(settings.EXPORT_DIR, filename)
        doc.save(filepath)
    except Exception as exc:  # pragma: no cover - 渲染失败路径
        logger.exception("重大危险源辨识报告生成失败 unit=%s", unit_id)
        raise HTTPException(500, f"报告生成失败: {exc}") from exc

    return FileResponse(
        filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
```

同时确认 `major_hazard.py` 顶部有：

```python
import logging
logger = logging.getLogger("major_hazard")
```

> `report_kind` 传的是 `"major_hazard_identification"`。若 `report_docx.REPORT_KIND_TITLES`
> 里没有这个键，`generate_report_docx` 会回落到传入的 `report_title`，行为正确；
> 若要让它有专门的封面标题，在 `REPORT_KIND_TITLES` 里补一条
> `"major_hazard_identification": "危险化学品重大危险源辨识报告"`（**这是本任务的一部分，别漏**）。

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_report_api.py tests/test_major_hazard_report_data.py -v
```

预期：`10 passed`

- [ ] **步骤 5：跑后端全量**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：失败数不高于 4 个既有失败

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/major_hazard.py backend/app/services/report_docx.py backend/tests/test_major_hazard_report_api.py
git commit -m "feat(major-hazard): 辨识报告 DOCX 导出端点（无快照 422）（任务 2/3）"
```

---

## 任务 3：前端导出按钮 + 真实文档目视验收

**文件：**

- 修改：`frontend/src/services/majorHazardService.ts`
- 修改：`frontend/src/pages/Enterprise/MajorHazardComputePage.tsx`

- [ ] **步骤 1：service 层加下载函数**

项目已有中文文件名下载工具（`frontend/src/utils/download.ts`，处理 RFC5987 `filename*`），直接复用：

```ts
// majorHazardService.ts 追加
/** 下载辨识报告 DOCX。走 blob，避免文件名被 URL 编码破坏。 */
export const downloadUnitReport = async (unitId: string, fallbackName = "重大危险源辨识报告") => {
  const resp = await api.get(`${BASE}/units/${unitId}/report.docx`, {
    responseType: "blob",
    skipGlobalError: true,
  });
  // 复用现有 utils/download.ts 的保存逻辑（它会读 Content-Disposition 的 filename*）
  saveBlobFromResponse(resp, fallbackName);
};
```

> `saveBlobFromResponse` 的确切函数名以 `frontend/src/utils/download.ts` 现有导出为准；
> 若该工具只接受 `(blob, filename)`，则在本函数里解析完响应头再调它。

- [ ] **步骤 2：计算页加导出按钮**

在「固化本次结果」旁加「导出辨识报告」按钮：

- 未固化的单元（快照历史为空）**禁用该按钮**，`Tooltip` 提示"请先固化一次计算结果"
- 点击 → `downloadUnitReport(unitId)`
- 后端 422 时用 `skipGlobalError: true` 拦下，页面自己 `message.warning(detail)`

- [ ] **步骤 3：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
```

预期：`tsc` exit 0；vitest 全绿

- [ ] **步骤 4：真实文档目视验收（必做）**

用「氯 5t / Q=5 / β=4」+「氨 5t / Q=10 / β=2」、暴露人数 60 的单元导出报告，然后：

1. **用 Word 打开**（或转 PDF 后渲染成图片），逐页目视检查
2. 确认封面、页眉页脚、章节编号、表格边框都正常（复用现有版式，不应有明显错位）
3. 确认「六、分级判定」里 R=7.5、级别**四级**，与页面显示一致
4. 确认「附录：法规依据条文」列出了挂载的 GB 18218 条文
5. **再把该单元的品种改成 1t（不构成）重新固化并导出**，确认报告写的是"**不构成危险化学品重大危险源**"而不是空白

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/services/majorHazardService.ts frontend/src/pages/Enterprise/MajorHazardComputePage.tsx
git commit -m "feat(major-hazard): 计算页导出辨识报告按钮（任务 3/3）"
```

---

## 验收清单

- [ ] `cd backend && python -m pytest tests/ -q` 失败数不高于 4 个既有失败
- [ ] `docker exec -w /app emergency-plan-frontend npx tsc -b` exit 0，vitest 全绿
- [ ] **无快照时导出返回 422**，不是 500，也不是一份空报告
- [ ] 报告章节齐全且顺序固定为 basic→basis→units→chemicals→metrics→grading→conclusion→responsible→appendix
- [ ] **不构成时报告显式写"不构成危险化学品重大危险源"**（不能留空、不能写"—"）
- [ ] **设计最大量的口径说明出现在「四、单元内危险化学品与临界量」章节的注释里**
- [ ] 真实导出并用 Word/PDF 目视检查，版式无错位、无空章节
- [ ] 报告中的 R 值与页面显示一致（同一个快照来源）
- [ ] 未建档时「八、包保责任人」章节仍存在，内容为"尚未建立档案"提示

## 未纳入本计划

- 批量导出多个单元/整厂的合并报告（属 P1 场景）
- 报告在线预览页（现有 `RiskAssessmentPreview` 是 HTML 预览，本计划只做 DOCX 下载）
- 报告版本管理与审批流转（现有 `report_versions` 体系未接入本报告）
