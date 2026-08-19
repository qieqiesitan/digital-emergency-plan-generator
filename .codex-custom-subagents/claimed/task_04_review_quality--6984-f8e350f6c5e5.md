# Codex Custom Subagents task handoff v1

Task: task_04_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 4 的实现做**只读代码质量审查**（规格审查已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`6a493c9`（父 `54ca7a5`）
- 文件：
  - `backend/app/services/risk_conversion_service.py`
  - `backend/app/services/risk_method_engine.py`
  - `backend/tests/test_risk_conversion.py`
- 可对照：项目既有服务风格（`backend/app/services/risk_method_engine.py`、`backend/app/services/risk_notice_card_data.py`）

## 审查要点

1. `risk_conversion_service.py`：命名、类型注解、正则可读性、边界处理（None/空/0 系数）、docstring；
2. `level_from_score` 在 risk_method_engine 的定位与现有函数风格一致性；`method_type` 参数当前未使用是否可接受（预留）；
3. 测试质量：断言有效性、边界覆盖（可补充：parse_score 无法解析、combine_factor 空集合、未命中阈值兜底——若缺失列为建议）、无脆弱断言；
4. 有无过度工程（YAGNI）、重复代码；
5. 无越界改动、import 规范。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_04_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务4代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
