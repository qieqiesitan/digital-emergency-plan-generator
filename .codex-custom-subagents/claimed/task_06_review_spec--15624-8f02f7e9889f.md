# Codex Custom Subagents task handoff v1

Task: task_06_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 6 的实现做**只读规格合规审查**，对照 A 规格 §5.3/§6 与任务 6 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`f99d4b3`（父 `c05d820`）
- 文件：
  - `backend/app/services/risk_mapping_service.py`
  - `backend/app/schemas/risk_management.py`
  - `backend/app/routers/risk_management.py`
  - `backend/tests/test_risk_dual_level.py`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §5.3（分区四色双模式）、§6（四色图双模式）

## 审查要点

1. `max_risk_level(zone, mode="current")`：双模式取对应字段、默认 current 向后兼容、LEVEL_ORDER 正确；
2. `RiskZoneResponse`/`HierarchyZoneResponse` 增加 `inherent_max_level`/`inherent_effective_color`（默认 None）；
3. 路由组装点（workbench/overview、get_hierarchy、list_zones）是否正确填充双等级与双颜色；`list_zones` 由「等级 None」变为「计算 current+inherent」是否合理且语义兼容（评估）；
4. 四色导入无风险对象分区的 `inherent_effective_color` 对称处理；
5. 测试：`test_max_risk_level_by_mode` 覆盖对象/单元事件双模式；
6. 无越界改动：提交仅含上述 4 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_06_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务6规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
