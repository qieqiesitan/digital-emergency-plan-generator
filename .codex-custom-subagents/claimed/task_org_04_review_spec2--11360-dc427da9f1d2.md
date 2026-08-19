# Codex Custom Subagents task handoff v1

Task: task_org_04_review_spec2

## 目标

对组织任务 4 的**规格修复提交做只读复审**（2 条建议：导入文件异常兜底 + 表头校验）。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`1cb17ba`（父 `d02ae13`）
- 文件：`backend/app/routers/enterprise_org.py`、`backend/tests/test_enterprise_org.py`

## 复审要点

1. 5MB 上限 413、load_workbook 异常 → 400；
2. 表头与 IMPORT_HEADERS 排序比较（忽略顺序/容忍空白）、复用服务层常量、dict(zip) 用去空白表头；
3. 测试 4 条新增用例有效（损坏 400/表头不符 400/乱序带空白成功/>5MB 413）；
4. 无越界改动：提交仅含上述 2 个文件。

## 验证

- `python -m pytest tests/test_enterprise_org.py -v` 预期 50 passed；`git show --check 1cb17ba` 干净。

## 输出格式

- 结论：✅ 通过 / ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_04_review_spec2 --claim-id <claim_id> --exit-code 0 --summary "组织任务4规格复审完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
