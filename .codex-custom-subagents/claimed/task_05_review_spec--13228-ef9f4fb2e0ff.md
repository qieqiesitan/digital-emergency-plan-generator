# Codex Custom Subagents task handoff v1

Task: task_05_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 5 的实现做**只读规格合规审查**，对照 A 规格 §5.2/§9/§10 与任务 5 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`a1446b7`（后端）+ `9104d4f`（前端），父 `09d5b0a`
- 文件：
  - 后端：`backend/app/schemas/risk_management.py`、`backend/app/routers/risk_management.py`、`backend/tests/test_risk_conversion_api.py`
  - 前端：`frontend/src/types/riskManagement.ts`、`frontend/src/services/riskManagementService.ts`、`frontend/src/services/riskManagementService.test.ts`、`frontend/src/components/enterprise/RiskEventForm.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`（实现者越界最小接线，需评估）
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §5.2 方式一/方式二、§9 接口（conversion-reference）、§10 前端（RiskEventForm 固有参数区块/管控层级/折算参考按钮）

## 审查要点

1. 后端端点：`GET /events/{event_id}/conversion-reference` 组装（get_dict_map measure_factors → factor_map/mode → get_active_method_config thresholds → conversion_reference）正确；404 分支；`MethodPreviewRequest/Response` scenario 透传且向后兼容；
2. 前端类型/service：RiskEvent/RiskEventCreate/RiskEventFormValues 3 字段；previewRiskMethod scenario 可选透传、previewRiskConversion URL 正确；旧 previewMethod 签名兼容；
3. 表单：LS/LEC/COAL_LS 固有参数组、DIRECT 固有等级 Select、管控层级 Select、折算参考按钮/结果卡片/采用回填/降级文案；保存透传 inherent_* 与 control_level；
4. 越界评估：`RiskManagementTab.tsx` 的最小接线是否必要、是否破坏既有行为；
5. 测试：后端端点测试（成功/404/scenario）、前端 service 测试覆盖；
6. 无其他越界改动。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_05_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务5规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
