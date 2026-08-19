# Codex Custom Subagents task handoff v1

Task: task_org_06_review_quality

## 目标

对「企业组织与成员管理」计划任务 6 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`963dab2` + `1419272` → HEAD=`1419272`
- 文件：`frontend/src/types/enterpriseOrg.ts`、`frontend/src/services/enterpriseOrgService.ts`、`enterpriseOrgService.test.ts`、`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`、`frontend/src/routes/index.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`、后端补充端点（template/search）+ 测试

## 审查要点

1. 组织页组件复杂度（树编辑/AI/成员/导入多状态）、localNodes 覆盖层、事件处理、可维护性；
2. service 一致性、类型；
3. 后端补充端点（template/search）：安全（ilike 注入/越权/暴露范围）、测试；
4. 已知债务评估：成员 name 非字符串 TypeError、环校验缺失、AI 预览 buildTreeData 无防环——确认并给出优先级建议；
5. 无过度工程、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_06_review_quality --claim-id <claim_id> --exit-code 0 --summary "组织任务6质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest/tsc/eslint、git log/show/diff）；任务池命令在任务池目录执行。
