# 作业票措施库数据缺陷修复 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把动火 3 个级别与受限空间票的错误措施库（各 106 条、混入其他票种措施）修复为正确的 16 / 15 条，并让种子生成器重放时能自愈。

**架构：** 项目单测不连数据库，因此"生成器自愈"用纯函数测试锁住（`build_sql()` 是纯函数，返回 SQL 字符串）；存量数据修复走独立迁移 SQL + psql 三重核验；另写只读探针产出 JSON 证据。

**技术栈：** Python 3 / pytest / PostgreSQL 16（docker）/ psql

**依据规格：** `docs/superpowers/specs/2026-09-20-work-ticket-smart-prefill-design.md` §0

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/seed_work_ticket_templates.py`（修改） | 每个模板的措施 INSERT 之前先发 `DELETE ... sort_order > N`，使重放可自愈 |
| `backend/db_migration_20260920_work_ticket_measure_fix.sql`（创建） | 存量修复：删除 4 个模板中超出正确条数的措施行 |
| `backend/tests/test_work_ticket_seed_v2.py`（修改） | 新增：清理语句存在性断言 + 每模板条数回归锁 |
| `output/playwright/e2e-20260920/scripts/_work_ticket_measure_probe.py`（创建） | 只读核验探针，产出 JSON 证据 |

**不修改**：`backend/app/services/work_ticket_seed_data.py`（解析逻辑已正确，见规格 §0.2）、`backend/db_migration_20260917_work_ticket_seed_v2.sql`（生成产物，由生成器重写）。

---

## 任务 1：生成器自愈（防止脏数据再次产生）

**文件：**
- 修改：`backend/seed_work_ticket_templates.py:80-95`
- 测试：`backend/tests/test_work_ticket_seed_v2.py`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_work_ticket_seed_v2.py` 末尾追加（`_load()` 已在该文件内定义，直接复用）：

```python
def _build_sql() -> str:
    """调用生成器的纯函数入口，拿 SQL 文本而不写文件。"""
    import importlib.util as _ilu

    spec = _ilu.spec_from_file_location(
        "wt_seed_gen", ROOT / "backend" / "seed_work_ticket_templates.py"
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_sql()


def test_measure_cleanup_statement_emitted_per_template():
    """每个模板的措施 INSERT 之前必须有清理语句。

    背景（2026-09-20 真库发现）：v1 种子把附录A 全部 106 条措施写给了动火与
    受限空间的 4 个模板；v2 用确定性 UUID5 + ON CONFLICT DO NOTHING 修正了
    同 ID 行的文本，但多出的行无人删除。若生成器只 INSERT 不清理，
    任何一次"修复后重放"都无法自愈，故把清理语句锁进测试。
    """
    lines = _build_sql().splitlines()
    inserts = [
        i for i, ln in enumerate(lines)
        if ln.startswith("INSERT INTO work_ticket_template_measures ")
    ]
    assert inserts, "未生成任何措施 INSERT"
    for idx in inserts:
        template_id = lines[idx].split("'")[3]
        prefix = (
            "DELETE FROM work_ticket_template_measures "
            f"WHERE template_id = '{template_id}'"
        )
        assert any(
            ln.startswith(prefix) for ln in lines[max(0, idx - 5):idx]
        ), f"模板 {template_id} 的措施 INSERT 之前缺少清理语句"


def test_measure_counts_per_template_match_appendix_tables():
    """生成产物的措施总数必须等于各章节附录表条数之和（回归锁）。"""
    mod = _load()
    expected_by_chapter = {5: 16, 6: 15, 7: 11, 8: 15, 9: 20, 10: 14, 11: 11, 12: 4}
    actual = sum(
        1 for ln in _build_sql().splitlines()
        if ln.startswith("INSERT INTO work_ticket_template_measures ")
    )
    expected = sum(expected_by_chapter[t["chapter"]] for t in mod.TEMPLATES)
    assert actual == expected == 223, f"措施总数不符：actual={actual} expected={expected}"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend; python -m pytest tests/test_work_ticket_seed_v2.py -v`

预期：`test_measure_cleanup_statement_emitted_per_template` **FAILED**（报错 `模板 <uuid> 的措施 INSERT 之前缺少清理语句`）；`test_measure_counts_per_template_match_appendix_tables` **PASSED**（生成器本身已正确，此条是回归锁）。

- [ ] **步骤 3：编写最少实现代码**

修改 `backend/seed_work_ticket_templates.py`，在 `if not parsed: raise RuntimeError(...)` 之后、`for m in parsed:` 之前插入：

```python
        # 自愈：v1 种子曾把附录A 全部措施（106 条）写给前 4 个模板；
        # v2 的 ON CONFLICT DO NOTHING 只跳过同 ID 行、不删除多出的行。
        # 因此每次生成本模板措施前先清理超额行，保证重放收敛。
        lines.append(
            "DELETE FROM work_ticket_template_measures "
            f"WHERE template_id = {_q(tpl_id)} AND sort_order > {len(parsed)};"
        )
```

清理语句必须是独立一行、以 `DELETE FROM work_ticket_template_measures WHERE template_id = '<id>'` 开头（测试按前缀匹配，且限定在后续 INSERT 的前 5 行内）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend; python -m pytest tests/test_work_ticket_seed_v2.py -v`

预期：全部 PASSED。

- [ ] **步骤 5：重新生成种子 SQL 并核验产物**

```bash
python backend/seed_work_ticket_templates.py
grep -c "^DELETE FROM work_ticket_template_measures" backend/db_migration_20260917_work_ticket_seed_v2.sql
git diff --stat backend/db_migration_20260917_work_ticket_seed_v2.sql
```

预期：生成脚本打印行数；`grep` 输出 `15`；`git diff --stat` 显示该文件新增 15 行、其余不变。

- [ ] **步骤 6：Commit**

```bash
git add backend/seed_work_ticket_templates.py backend/db_migration_20260917_work_ticket_seed_v2.sql backend/tests/test_work_ticket_seed_v2.py
git commit -m "fix(seed): 措施种子重放自愈清理超额行 + 条数回归锁"
```

---

## 任务 2：存量数据修复迁移

**文件：**
- 创建：`backend/db_migration_20260920_work_ticket_measure_fix.sql`

- [ ] **步骤 1：编写迁移 SQL**

```sql
-- 20260920 作业票措施库存量修复
--
-- 问题：v1 种子（db_migration_20260917_work_ticket_seed.sql）把 GB 30871-2022
-- 附录A 表 A.1~A.8 的全部措施（16+15+11+15+20+14+11+4 = 106 条）都写给了
-- 前 4 个模板（DHZY 特级/一级/二级、YXKJ）。v2 种子用确定性 UUID5 +
-- ON CONFLICT (id) DO NOTHING 修正了 sort_order 1~N 的文本，但多出的
-- 第 N+1~106 行无人删除，残留在库中。
--
-- 影响：动火与受限空间票的开票界面要在一个 106 项的措施列表里操作，
-- 其中 90 条属于其他票种（盲板/高处/吊装/临电/动土/断路）。
--
-- 正确条数依据：backend/app/regulations/data/texts/reg_gb_30871_2022.md
--   表 A.1（动火，16 条，第 819~834 行）、表 A.2（受限空间，15 条，第 868~888 行）。
--
-- 幂等：DELETE 基于 sort_order 阈值，重复执行结果一致。

BEGIN;

DELETE FROM work_ticket_template_measures m
USING work_ticket_templates t
WHERE m.template_id = t.id
  AND t.code = 'DHZY'
  AND m.sort_order > 16;

DELETE FROM work_ticket_template_measures m
USING work_ticket_templates t
WHERE m.template_id = t.id
  AND t.code = 'YXKJ'
  AND m.sort_order > 15;

COMMIT;

-- 核验 1：条数（期望 DHZY×3 = 16、YXKJ = 15、其余模板不变）
-- SELECT t.code, t.level, count(m.id) FROM work_ticket_templates t
--   LEFT JOIN work_ticket_template_measures m ON m.template_id = t.id
--  GROUP BY t.code, t.level ORDER BY t.code, t.level;
-- 核验 2：总数（期望 584 - 90*3 - 91 = 223）
-- SELECT count(*) FROM work_ticket_template_measures;
```

- [ ] **步骤 2：记录修复前基线**

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT t.code, t.level, count(m.id) AS measures FROM work_ticket_templates t LEFT JOIN work_ticket_template_measures m ON m.template_id=t.id GROUP BY t.code, t.level ORDER BY t.code, t.level;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) AS total FROM work_ticket_template_measures;"
```

预期基线：DHZY 三级与 YXKJ 各 **106**；`total = 584`。把输出贴进任务记录。

- [ ] **步骤 3：应用迁移**

```powershell
docker cp backend/db_migration_20260920_work_ticket_measure_fix.sql emergency-plan-db:/tmp/wt_measure_fix.sql
docker exec emergency-plan-db psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 -f /tmp/wt_measure_fix.sql
```

预期输出：`DELETE 90`（执行 3 次，每个动火级别一次）、`DELETE 91`（YXKJ）、`BEGIN`、`COMMIT`。

注意：部署手册 §8.0.2 指出的是"容器→容器"的 `docker cp` 不成立；这里是从宿主机拷入 db 容器，合法。

- [ ] **步骤 4：三重核验**

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT t.code, t.level, count(m.id) AS measures FROM work_ticket_templates t LEFT JOIN work_ticket_template_measures m ON m.template_id=t.id GROUP BY t.code, t.level ORDER BY t.code, t.level;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT count(*) AS total FROM work_ticket_template_measures;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT m.sort_order, left(m.measure_text,30) FROM work_ticket_template_measures m JOIN work_ticket_templates t ON t.id=m.template_id WHERE t.code='DHZY' AND t.level='二级' ORDER BY m.sort_order;"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT m.sort_order, left(m.measure_text,30) FROM work_ticket_template_measures m JOIN work_ticket_templates t ON t.id=m.template_id WHERE t.code='YXKJ' ORDER BY m.sort_order;"
```

预期：核验 1 → DHZY×3 = 16、YXKJ = 15、其余 11 个模板条数不变（11/14/15/20/4）；核验 2 → `223`；核验 3 → 16 行、末条为"其他安全措施：  编制人："；核验 4 → 15 行。

- [ ] **步骤 5：老票兼容核验**

```powershell
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "SELECT code, status, jsonb_array_length(values->'confirmed_measures') AS confirmed FROM work_ticket_instances WHERE ticket_type IN ('DHZY','YXKJ') ORDER BY status;"
```

预期：按 106 条确认过的 2 张票（1 approved / 1 approving）`confirmed` 仍为 106——**刻意不清理**（`validate_before_submit` 只校验缺失、忽略多余编号，天然兼容）。把这条结论写进任务记录与 commit message。

- [ ] **步骤 6：Commit**

```bash
git add backend/db_migration_20260920_work_ticket_measure_fix.sql
git commit -m "fix(data): 修复动火/受限空间措施库存量缺陷（106→16/15 条）"
```

---

## 任务 3：真库核验探针与证据留档

**文件：**
- 创建：`output/playwright/e2e-20260920/scripts/_work_ticket_measure_probe.py`

- [ ] **步骤 1：编写探针（只读，不改库）**

```python
"""作业票措施库修复核验探针（只读）。

用法（仓库根目录）：python output/playwright/e2e-20260920/scripts/_work_ticket_measure_probe.py
证据输出：同目录 work-ticket-measure-fix.json
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-measure-fix.json"
STANDARD_TEXT = ROOT / "backend" / "app" / "regulations" / "data" / "texts" / "reg_gb_30871_2022.md"
EXPECTED = {"DHZY": 16, "YXKJ": 15}


def psql(sql: str) -> list[list[str]]:
    """执行只读 SQL，返回以 | 分隔的行（去掉表头与统计行）。"""
    out = subprocess.run(
        ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
         "-d", "emergency_plan", "--no-align", "--tuples-only", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    return [ln.split("|") for ln in out.strip().splitlines() if ln.strip()]


def appendix_measures(table_no: int) -> list[str]:
    """从标准文本抽取表 A.<table_no> 的措施文本（四列行的第 2 列）。"""
    text = STANDARD_TEXT.read_text(encoding="utf-8")
    row = re.compile(rf"^\|\s*(\d+)\s*\|\s*([^|]{{4,}}?)\s*\|")
    header = re.compile(rf"^表A[.．]{table_no}(?:\s|$)")
    in_table, out = False, []
    for line in text.splitlines():
        if re.match(r"^表A[.．][1-8]\b", line.strip()):
            in_table = bool(header.match(line.strip()))
            continue
        if in_table and (m := row.match(line.strip())) and int(m.group(1)) == len(out) + 1:
            out.append(m.group(2).strip())
    return out


def main() -> int:
    counts = {
        code: int(n) for code, n in psql(
            "SELECT t.code, count(m.id) FROM work_ticket_templates t "
            "LEFT JOIN work_ticket_template_measures m ON m.template_id=t.id "
            "GROUP BY t.code;"
        )
    }
    total = int(psql("SELECT count(*) FROM work_ticket_template_measures;")[0][0])
    db_fire = [r[1].strip() for r in psql(
        "SELECT m.sort_order, m.measure_text FROM work_ticket_template_measures m "
        "JOIN work_ticket_templates t ON t.id=m.template_id "
        "WHERE t.code='DHZY' AND t.level='二级' ORDER BY m.sort_order;"
    )]
    db_space = [r[1].strip() for r in psql(
        "SELECT m.sort_order, m.measure_text FROM work_ticket_template_measures m "
        "JOIN work_ticket_templates t ON t.id=m.template_id "
        "WHERE t.code='YXKJ' ORDER BY m.sort_order;"
    )]
    text_fire, text_space = appendix_measures(1), appendix_measures(2)

    checks = {
        "DHZY_measures_is_16": counts.get("DHZY") == 16,
        "YXKJ_measures_is_15": counts.get("YXKJ") == 15,
        "total_is_223": total == 223,
        "fire_text_matches_appendix": db_fire == text_fire,
        "space_text_matches_appendix": db_space == text_space,
    }
    EVIDENCE.write_text(json.dumps({
        "counts_by_code": counts, "total": total,
        "fire_count": len(db_fire), "space_count": len(db_space),
        "fire_first": db_fire[:2], "space_first": db_space[:2],
        "checks": checks, "all_passed": all(checks.values()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **步骤 2：运行探针**

```powershell
python output/playwright/e2e-20260920/scripts/_work_ticket_measure_probe.py
```

预期：五项 checks 全为 `true`，退出码 0，`work-ticket-measure-fix.json` 生成。

注意：`counts_by_code` 按票种聚合（DHZY 三级合计应为 48）。若 `fire_text_matches_appendix` 为 false，先比对探针抽取的附录条数（应为 16/15）——探针的表格抽取逻辑独立于 `work_ticket_seed_data.parse_measures`，两者一致才算交叉验证成立。

- [ ] **步骤 3：Commit**

```bash
git add output/playwright/e2e-20260920/scripts/_work_ticket_measure_probe.py output/playwright/e2e-20260920/scripts/work-ticket-measure-fix.json
git commit -m "test(probe): 措施库修复核验探针 + 证据"
```

---

## 验收清单

- [ ] `cd backend; python -m pytest tests/test_work_ticket_seed_v2.py -v` 全绿
- [ ] `cd backend; python -m ruff check .` 全绿
- [ ] 生成器产物含 15 条 `DELETE FROM work_ticket_template_measures ...`
- [ ] 迁移执行输出 `DELETE 90` ×3 + `DELETE 91` ×1
- [ ] 核验：DHZY×3 = 16、YXKJ = 15、其余 11 个模板条数不变、总数 223
- [ ] 动火保留的 16 条与标准文本表 A.1 逐条一致（探针 `fire_text_matches_appendix=true`）
- [ ] 受限空间保留的 15 条与表 A.2 逐条一致（探针 `space_text_matches_appendix=true`）
- [ ] 老票 28 张全部可读；2 张按 106 条确认的票不被清理且显示正常
- [ ] 开票页第 4 步措施数：动火显示 16 条、受限空间显示 15 条（浏览器实测）
- [ ] 探针 JSON 证据留档

## 不做（本计划范围外）

- 不修改已打印的历史快照（§0.3）
- 不清理老票 `values.confirmed_measures` 中的多余编号（向后兼容，见任务 2 步骤 5）
- 不做措施三态与"是否涉及"判定（属计划 2）
