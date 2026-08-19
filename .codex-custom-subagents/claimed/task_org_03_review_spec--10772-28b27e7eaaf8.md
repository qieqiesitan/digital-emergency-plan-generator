# Codex Custom Subagents task handoff v1

Task: task_org_03_review_spec

## 目标

对「企业组织与成员管理」计划任务 3 的实现做**只读规格合规审查**（对照计划任务 3 契约），输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`7a28f35`（父 `11b6ae5`）
- 文件：`backend/app/schemas/enterprise_org.py`、`backend/app/routers/enterprise_org.py`、`backend/app/main.py`、`backend/tests/test_enterprise_org.py`
- 计划：`docs/superpowers/plans/2026-08-15-enterprise-org-members.md` 任务 3

## 审查要点

1. schema：字段/枚举/默认值与契约一致；
2. 端点：6 个端点语义（nodes 读取/写入校验 422 ORG_TREE_INVALID、members 创建 201/404/409、更新 exclude_unset、删除、列表 join email/name）；写权限仅企业主（403）、读归属校验；
3. main.py 注册；
4. 测试：14 端点用例覆盖（含 403/404/409/422），断言有效；
5. 写权限取舍说明合理性（读也按企业主校验的取舍）；
6. 无越界改动：提交仅含上述 4 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_03_review_spec --claim-id <claim_id> --exit-code 0 --summary "组织任务3规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
