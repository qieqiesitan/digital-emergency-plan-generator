# Codex Custom Subagents task handoff v1

Task: task_09_review_spec2

## 目标

对任务 9 的**规格修复提交做只读复审**。首次规格审查提出 5 条建议修改，实现者已修复并提交 `6a40bc1`，现复审修复是否到位。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`6a40bc1`（父 `3d3b21e`）
- 文件：
  - `backend/app/services/risk_control_list_service.py`
  - `backend/app/routers/risk_management.py`
  - `backend/tests/test_risk_control_list.py`
  - `frontend/src/pages/Enterprise/RiskPublicityPage.tsx`
  - `frontend/src/pages/Enterprise/RiskControlListPage.tsx`
  - `frontend/src/pages/PublicRiskPage.tsx`
  - `frontend/src/services/riskManagementService.ts`
  - `frontend/src/services/riskManagementService.test.ts`

## 复审要点（对照 5 条建议）

1. 公示表「位置」「告知卡入口」：后端 `location` 输出 + `_strip_internal_keys(keep=object_id)`（仅公示保留，control-list 仍剥离）；前端两列与链接路由正确；
2. 清单页「联系电话」列；
3. 导出透传筛选：后端 export 对齐 control-list 参数并过滤；前端 handleExport 传 filters；测试断言过滤后行数；
4. 重置 token：onOk try/catch（antd close 模式），失败不关闭 Modal 且无未处理 rejection；
5. 公开页文案改为实时生成；
6. 无越界改动：提交仅含上述 8 个文件。

## 验证

- backend 目录只读运行 `python -m pytest tests/test_risk_control_list.py -v`，预期全部 PASS（21 个）；
- frontend 只读运行 `npx vitest run`（75 个）与 `npx tsc -b` 通过；
- `git show --check 6a40bc1` 干净。

## 输出格式

- 结论：✅ 通过（5 条建议均已解决）/ ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_09_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "任务9规格复审完成"
```

## 规则

- 全程只读；任务池命令在任务池目录执行；代码审查在工作树目录进行。
