# Codex Custom Subagents task handoff v1

Task: task_10_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 10 的实现做**只读规格合规审查**，对照 A 规格 §5.4/§6（告知卡双等级）/§10（字典管理页）与任务 10 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`f3d1045` + `4d0ec3c`（父 `73ca31c`）
- 文件：
  - 后端：`backend/app/schemas/risk_notice_card.py`、`backend/app/services/risk_notice_card_service.py`、`backend/tests/test_risk_notice_card_service.py`
  - 前端：`frontend/src/types/riskNoticeCard.ts`、`frontend/src/components/enterprise/RiskNoticeCard.tsx`、`frontend/src/types/dataDict.ts`、`frontend/src/services/dataDictService.ts`、`frontend/src/services/dataDictService.test.ts`、`frontend/src/pages/Settings/DataDictManagePage.tsx`、`frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx`、`frontend/src/routes/index.tsx`、`frontend/src/layouts/MainLayout.tsx`（实现者：系统菜单实际位置）、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §5.4（字典管理界面）、§10（告知卡双等级、字典页）、§14 验收

## 审查要点

1. 告知卡：`CardData.inherent_risk_level`、组装取最大固有等级（对象/单元事件）、快照缺字段回退、前端色带显示（无 inherent 隐藏括号）；
2. 字典 service 7 方法 URL 与后端一致、解包惯例；
3. 系统字典页：dict_type 分组、Table 字段、Drawer 表单（value JSON.parse 校验、非法提示）、系统条目删除禁用说明；
4. 企业覆盖页：合并视图、系统默认 Tag、覆盖（复制为企业 scope）、编辑/删除（恢复默认）、变更后 refetch；
5. 路由/菜单：两个路由 ProtectedRoute 内、系统菜单入口（MainLayout 偏差评估）、RiskManagementTab 入口按钮；
6. 门禁：后端/前端全过；无越界改动；eslint 行内豁免评估。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_10_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务10规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest/tsc/eslint、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
