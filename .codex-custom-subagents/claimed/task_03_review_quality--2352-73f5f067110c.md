# Codex Custom Subagents task handoff v1

Task: task_03_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 3 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交范围：`c1fcf8c` + `54ca7a5` → 当前 HEAD=`54ca7a5`
- 文件：
  - `backend/db_migration_risk_control_enhancement.sql`
  - `backend/app/models/risk_management.py`
  - `backend/app/models/enterprise.py`
  - `backend/app/services/risk_method_engine.py`
  - `backend/app/schemas/risk_management.py`
  - `backend/app/routers/risk_management.py`
  - `backend/tests/test_risk_dual_level.py`
- 可对照：项目既有模型/路由/迁移风格（`backend/app/models/enterprise.py`、`backend/app/routers/risk_management.py`、`backend/tests/test_public_risk_notice.py`）

## 审查要点

1. `validate_dual_level` 纯函数：命名、位置（risk_method_engine）、`RISK_LEVEL_ORDER` 语义、None 短路是否清晰；
2. 路由：4 处重算路径校验与持久化是否一致、无重复代码可提取；`update_event` 无条件校验的实现是否可读、异常转 422 是否统一；
3. 模型/迁移一致性：RiskEvent 3 字段、Enterprise `__table_args__` 部分唯一索引与迁移一致；风格与项目一致；
4. schema：3 个类字段是否一致、是否向后兼容；
5. 测试：5 个用例质量（含路由级 mock 的组织方式、断言有效性、路径锚定、import 置顶）；有无脆弱断言；
6. 无越界改动、无过度工程。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_03_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务3代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
