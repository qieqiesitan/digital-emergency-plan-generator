# Codex Custom Subagents task handoff v1

Task: task_org_06_review_spec

## 目标

对「企业组织与成员管理」计划任务 6 的实现做**只读规格合规审查**（对照计划任务 6 契约），输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`963dab2`（父 `1f153db`）
- 文件：`frontend/src/types/enterpriseOrg.ts`、`frontend/src/services/enterpriseOrgService.ts`、`enterpriseOrgService.test.ts`、`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`、`frontend/src/routes/index.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx` + 后端补充 2 端点（template/search）

## 审查要点

1. 类型/service：与后端契约一致、解包惯例、10 条 URL 断言；
2. 组织页：树编辑（增删改/前端校验/localNodes 覆盖层）、AI 建树预览/降级、成员 Table/添加（邮箱搜索）/编辑/删除/停用、Excel 导入（模板下载/Upload/汇总 Modal）、返回；
3. 后端补充端点：template 下载（StreamingResponse/xlsx/读权限）、member search（ilike/排除本企业/limit 20）——评估必要性、安全（注入/越权）与测试；
4. 路由/入口正确；
5. 门禁：后端 545、前端 97、eslint 0、tsc 0；
6. 无越界改动。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_06_review_spec --claim-id <claim_id> --exit-code 0 --summary "组织任务6规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest/tsc/eslint、git log/show/diff）；任务池命令在任务池目录执行。
