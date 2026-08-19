# Codex Custom Subagents task handoff v1

Task: task_08_fix

## 目标

修复任务 8 规格审查的 2 条必须修复 + 1 条建议修改，提交后复审。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`70c9b57`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 修复清单

**1（必须修复）：export 增加 sheet2 汇总**（`backend/app/services/risk_control_list_service.py`）

`build_ledger_workbook(rows)` 在 sheet1「风险管控清单」外新增 sheet2「等级/层级汇总」：

- sheet2 表头：`["固有等级", "数量"]`（按固有等级计数）+ 空行 + `["管控层级", "数量"]`（按管控层级计数）；或两个区域并排。选择清晰可读的实现；
- 汇总顺序按 RISK_LEVEL_ORDER（低/一般/较大/重大）与默认层级顺序；
- 更新测试：`test_build_ledger_workbook` 断言 `wb.sheetnames` 含两 sheet，且 sheet2 汇总计数正确（给定 rows 后断言具体值）。

**2（必须修复）：risk-publicity 响应补四色图数据**（`backend/app/routers/risk_management.py`）

`GET /risk-publicity` 响应增加 `zones`（企业内公示页四色图数据源）：

```python
zones = [{
    "id": z.id, "floor_id": z.floor_id, "floor_name": (z.floor.name if z.floor else None),
    "name": z.name,
    "floor_plan_polygon": z.floor_plan_polygon,
    "max_level": cur, "effective_color": cur_color,
    "inherent_max_level": inh, "inherent_effective_color": inh_color,
} for z, (cur, cur_color, inh, inh_color) in ...]  # 复用 _zone_dual_levels
```

查询已含 selectinload floor/objects/events（现有 zone 树查询基础上补 `selectinload(RiskZone.floor)`）。响应 `{token, enterprise_name, items, zones}`。补测试断言 zones 结构与字段存在。

**3（建议修改）：公开端点补生成时间**（`backend/app/routers/public_risk.py`）

响应增加 `generated_at`（ISO 时间字符串，`datetime.now(timezone.utc).isoformat()`）；企业内 risk-publicity 响应也补 `generated_at`。补测试断言存在且可解析。

## 验证

- 在 `backend` 目录 `python -m pytest tests/test_risk_control_list.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/services/risk_control_list_service.py backend/app/routers/risk_management.py backend/app/routers/public_risk.py backend/tests/test_risk_control_list.py
git commit -m "feat(risk): publicity zones and ledger summary sheet with generated time"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_08_fix --claim-id <claim_id> --exit-code 0 --summary "任务8公示图数据+汇总sheet修复完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、修复说明。

## 规则

- 用 `apply_patch` 编辑；只改列出的 4 个文件；阻塞时停下汇报。
