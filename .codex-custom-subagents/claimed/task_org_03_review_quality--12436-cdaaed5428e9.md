# Codex Custom Subagents task handoff v1

Task: task_org_03_review_quality

## 目标

对「企业组织与成员管理」计划任务 3 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`7a28f35` + `d4bdd58` → HEAD=`d4bdd58`
- 文件：`backend/app/schemas/enterprise_org.py`、`backend/app/routers/enterprise_org.py`、`backend/app/main.py`、`backend/tests/test_enterprise_org.py`
- 可对照：`backend/app/routers/data_dicts.py`、`backend/app/routers/risk_management.py`

## 审查要点

1. router：鉴权/归属校验组织、错误码语义（404 信息隐藏 vs 403）、`exclude_unset`、SQL 查询风格、N+1（GET members join）；
2. schema：Pydantic 用法与项目风格一致、枚举校验；
3. 测试：26 用例质量（mock 组织、断言有效性、无空断言）；GET members join 的断言覆盖；
4. 有无重复代码、过度工程、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_03_review_quality --claim-id <claim_id> --exit-code 0 --summary "组织任务3质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
