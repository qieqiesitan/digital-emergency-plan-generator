# Codex Custom Subagents task handoff v1

Task: task_org_05_review_spec

## 目标

对「企业组织与成员管理」计划任务 5 的实现做**只读规格合规审查**（对照计划任务 5），输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`0642101`（父 `9e46acb`）
- 文件：`backend/app/services/enterprise_org_service.py`、`backend/app/routers/enterprise_org.py`、`backend/tests/test_enterprise_org.py`

## 审查要点

1. `suggest_org_tree`：prompt 输入（行业/人数/现有树摘要）与输出契约（nodes 含 id/type/name/parent_id/members[].name/position、不猜邮箱）；`llm_text_completion` 调用；`_parse_ai_json` 复用；缺 nodes 抛错；异常兜底 `available:false`；
2. 端点：写权限 403、`_get_ai_config` 失败转 None、`available:false` 仍 200；
3. 测试：5 条新增用例（服务 2 + 端点 3）断言有效；
4. 无越界改动：提交仅含上述 3 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_05_review_spec --claim-id <claim_id> --exit-code 0 --summary "组织任务5规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
