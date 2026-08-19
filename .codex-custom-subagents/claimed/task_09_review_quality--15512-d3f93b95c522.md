# Codex Custom Subagents task handoff v1

Task: task_09_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 9 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`3d3b21e` + `6a40bc1` → 当前 HEAD=`6a40bc1`
- 文件：
  - `frontend/src/services/riskManagementService.ts`、`frontend/src/services/riskManagementService.test.ts`
  - `frontend/src/pages/Enterprise/RiskControlListPage.tsx`
  - `frontend/src/pages/Enterprise/RiskPublicityPage.tsx`
  - `frontend/src/pages/PublicRiskPage.tsx`
  - `frontend/src/routes/index.tsx`
  - `frontend/src/pages/Enterprise/RiskManagementTab.tsx`
  - `backend/app/services/risk_control_list_service.py`、`backend/app/routers/risk_management.py`（配合改动）
- 可对照：项目既有页面/service 风格

## 审查要点

1. 清单页：筛选 state 组织、分页、导出 blob（`new Blob([res.data])` 冗余评估）、rowKey 稳定性、类型（params: object 建议 Record<string, unknown>）；
2. 公示页：SVG 四色图渲染实现质量（坐标换算/标签/图例）、重置 token 的 antd close 模式正确性、打印样式；
3. 公开页：错误分支（404 vs 网络）、retry、脱敏列；
4. service：5+1 方法封装一致性、blob 返回类型；
5. 后端配合改动（location/keep 参数/export 筛选）质量与测试；
6. 有无重复代码、过度工程、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_09_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务9代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 vitest/tsc/eslint/pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
