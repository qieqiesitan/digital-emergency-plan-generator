# Codex Custom Subagents task handoff v1

Task: task_05_review_spec2

## 目标

对任务 5 的**规格修复提交做只读复审**。首次规格审查发现 2 条必须修复 + 3 条建议修改，实现者已修复并提交 `6cd1ad4`（后端）+ `26d49e8`（前端），现复审修复是否到位。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`6cd1ad4` + `26d49e8`（父 `9104d4f`；任务 5 整体范围 `a1446b7..26d49e8`）
- 文件：
  - 后端：`backend/app/schemas/risk_management.py`、`backend/app/routers/risk_management.py`、`backend/app/services/risk_method_engine.py`、`backend/tests/test_risk_conversion_api.py`、`backend/tests/test_risk_dual_level.py`
  - 前端：`frontend/src/components/enterprise/RiskEventForm.tsx`、`frontend/src/components/enterprise/RiskHierarchyTree.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`、`frontend/src/types/riskManagement.ts`

## 复审要点（对照首次规格审查问题清单）

1. **必须修复 1**：编辑回显——树 meta/initialValues 携带 method_params/inherent_*/control_level；表单编辑模式「未改动不覆盖」（未改动参数不提交 method_params/risk_level/risk_score/inherent_*，后端 exclude_unset 保持已存值）；新建/改动路径仍正确；
2. **必须修复 2**：采用为现有风险落库——`RiskEventCreate/Update` 显式 `risk_level/risk_score` 覆盖；create/update 提供时不再重算、仍校验；`handleAdoptConversion`→`handleFinish` 消费采用值；DIRECT 固有等级提交正确；
3. **建议 1**：conversion-reference 事件归属校验（链式 object/unit 校验）404；
4. **建议 2**：COAL_LS 默认阈值常量复用，无配置时折算不再恒「低」；
5. **建议 3**：DIRECT 提交 `method_params={"risk_level": 等级}`；LS/LEC/COAL_LS 提交键与后端小写一致；
6. 无越界改动（后端 HierarchyEventResponse 增加固有字段属必要补充，评估合理性）。

## 验证

- backend 目录只读运行 `python -m pytest tests/test_risk_conversion_api.py tests/test_risk_dual_level.py tests/test_risk_conversion.py -v`，预期全部 PASS（21 个）；
- 前端只读运行 `npx vitest run`（service 测试）与 `npx tsc -b`（若耗时可只跑 vitest 并说明）；
- `git show --check 6cd1ad4 26d49e8` 干净。

## 输出格式

- 结论：✅ 通过（必须修复与建议均已解决）/ ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_05_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "任务5规格复审完成"
```

## 规则

- 全程只读；任务池命令在任务池目录执行；代码审查在工作树目录进行。
