# Codex Custom Subagents task handoff v1

Task: task_03_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 3 的实现做**只读规格合规审查**，对照 A 规格 §5.1/§5.2/§11 与任务 3 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`c1fcf8c`（父 `a2c393e`）
- 文件：
  - `backend/db_migration_risk_control_enhancement.sql`
  - `backend/app/models/risk_management.py`
  - `backend/app/models/enterprise.py`
  - `backend/app/services/risk_method_engine.py`
  - `backend/app/schemas/risk_management.py`
  - `backend/app/routers/risk_management.py`
  - `backend/tests/test_risk_dual_level.py`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md`（工作树内）：§5.1 字段/迁移、§5.2 双参数评估、§11 错误处理（现有>固有 422）

## 审查要点

1. 迁移：3 个新列 + 回填（固有=现有）+ `public_risk_token` 与部分唯一索引，与 §5.1 一致、幂等；
2. 模型：RiskEvent 3 字段、Enterprise public_risk_token 与迁移一致；
3. 校验：`validate_dual_level` 纯函数（`RISK_LEVEL_ORDER` 顺序 低<一般<较大<重大），路由在 `compute_risk` 后调用、违例 422，覆盖 create_event/create_object_event/update/recalc 全部重算路径；
4. schema：Create/Update/Response 均含 3 个可选字段；
5. 更新路径：仅按提供值更新（exclude_unset），不误清字段；
6. 测试：4 个用例覆盖校验正常/异常、迁移 SQL、schema 字段；
7. 无越界改动：提交仅含列出的 7 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_03_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务3规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
