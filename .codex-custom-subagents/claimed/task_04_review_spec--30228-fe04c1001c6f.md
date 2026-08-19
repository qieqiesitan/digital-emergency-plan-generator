# Codex Custom Subagents task handoff v1

Task: task_04_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 4 的实现做**只读规格合规审查**，对照 A 规格 §5.2 方式二（自动折算参考）与任务 4 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`6a493c9`（父 `54ca7a5`）
- 文件：
  - `backend/app/services/risk_conversion_service.py`
  - `backend/app/services/risk_method_engine.py`
  - `backend/tests/test_risk_conversion.py`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §5.2 方式二（工作树内）

## 审查要点

1. `parse_score`：正则解析 `R=…`/`D=…` 数值正确，无法解析返回 None 且 `conversion_reference` 短路返回 note；
2. `combine_factor`：min 默认口径（已配置类别系数最小值）、product 连乘、排除 mode 键、空集合返回 1.0；
3. `conversion_reference`：参考分值 = 固有分值 × 综合系数（round 2 位）、经 `level_from_score` 阈值映射、DIRECT 由调用方短路（本任务不实现调用方，仅工具）；
4. `level_from_score`：阈值区间匹配、未命中兜底「低」；`compute_risk` 行为未被改变；
5. 测试：3 个纯函数用例覆盖解析/合并/参考映射，符合项目约定；
6. 无越界改动：提交仅含上述 3 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_04_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务4规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
