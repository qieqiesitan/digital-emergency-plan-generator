# Codex Custom Subagents task handoff v1

Task: task_09_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 9 的实现做**只读规格合规审查**，对照 A 规格 §7/§8/§10/§11 与任务 9 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`3d3b21e`（父 `f96160b`）
- 文件：
  - `frontend/src/services/riskManagementService.ts`
  - `frontend/src/pages/Enterprise/RiskControlListPage.tsx`
  - `frontend/src/pages/Enterprise/RiskPublicityPage.tsx`
  - `frontend/src/pages/PublicRiskPage.tsx`
  - `frontend/src/routes/index.tsx`（实现者：路由实际位置）
  - `frontend/src/pages/Enterprise/RiskManagementTab.tsx`
  - `frontend/src/services/riskManagementService.test.ts`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §7（清单页）、§8（公示页/公开页）、§11（错误处理 404 文案、公开脱敏）

## 审查要点

1. service 5 方法 URL 与后端端点一致、类型正确；
2. 清单页：筛选参数名（floor_id/zone_id/level/control_level/keyword）与后端一致、分页、等级 Tag 色、导出 blob、返回按钮；
3. 公示页：四色图（SVG 最小适配评估——未复用 RiskDistributionStage 的偏差是否可接受）、重大清单表、公开链接复制/重置 Modal、generated_at 本地化、打印样式；
4. 公开页：token 取参、404「链接已失效」/网络错误 warning+重试、脱敏列、公开提示条；
5. 路由：3 条路由注册位置与守卫正确（/p/risk/:token 无守卫）；
6. Tab 按钮入口；
7. 无越界改动；eslint 债务（routes/index.tsx react-refresh）确认为提交前既有。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_09_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务9规格审查完成"
```

## 规则

- 全程只读（可运行只读 vitest/tsc/eslint、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
