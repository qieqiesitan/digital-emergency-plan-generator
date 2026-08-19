# Codex Custom Subagents task handoff v1

Task: task_10_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 10 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`f3d1045` + `4d0ec3c` + `f1940f6` → 当前 HEAD=`f1940f6`
- 文件：
  - 后端：`backend/app/schemas/risk_notice_card.py`、`backend/app/services/risk_notice_card_service.py`、`backend/db_migration_data_dicts_permission.sql`、`backend/tests/test_data_dict.py`
  - 前端：`frontend/src/types/riskNoticeCard.ts`、`frontend/src/components/enterprise/RiskNoticeCard.tsx`、`frontend/src/types/dataDict.ts`、`frontend/src/services/dataDictService.ts`、`frontend/src/services/dataDictService.test.ts`、`frontend/src/pages/Settings/DataDictManagePage.tsx`、`frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx`、`frontend/src/routes/index.tsx`、`frontend/src/layouts/MainLayout.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 可对照：项目既有页面/service/迁移风格

## 审查要点

1. 告知卡：`compute_inherent_level` 实现质量（遍历/取级/None 处理）、与现有取级逻辑去重可能性；
2. 字典两页：组件复杂度（分组/Drawer/JSON 校验/覆盖去重）、状态管理、可维护性；`DataDictManagePage` 与 `EnterpriseDictConfigPage` 重复逻辑评估；
3. service/类型：7 方法一致性、`DataDictItem` 与后端响应匹配；
4. 权限迁移：SQL 幂等/与模型列匹配/角色分配正确；
5. routes/index.tsx 行内 eslint 豁免评估（是否可避免）；MainLayout 菜单项；
6. 有无过度工程、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_10_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务10代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest/tsc/eslint、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
