# Codex Custom Subagents task handoff v1

Task: task_06_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 6 的实现做**只读代码质量审查**（规格审查已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`f99d4b3` + `98a0c0a` → 当前 HEAD=`98a0c0a`
- 文件：
  - `backend/app/services/risk_mapping_service.py`
  - `backend/app/schemas/risk_management.py`
  - `backend/app/routers/risk_management.py`
  - `backend/tests/test_risk_dual_level.py`
- 可对照：项目既有服务/路由风格（`risk_mapping_service.py`、`risk_management.py`）

## 审查要点

1. `max_risk_level(zone, mode)`：默认参数、双循环一致性、可读性；`mode` 参数语义（内部调用均为字面量）；
2. 路由三处组装点（workbench/overview、hierarchy、list_zones）：是否重复过多、可提取辅助函数；selectinload 使用是否合理；list_zones 行为增强是否带来性能/语义风险；
3. schema 新增字段命名与项目风格一致、默认 None 向后兼容；
4. 测试：对象/单元双分支覆盖、断言有效性；
5. 有无过度工程、无越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_06_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务6代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
