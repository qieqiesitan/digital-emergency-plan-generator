# Codex Custom Subagents task handoff v1

Task: task_org_04_review_quality

## 目标

对「企业组织与成员管理」计划任务 4 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`d02ae13` + `1cb17ba` → HEAD=`1cb17ba`
- 文件：`backend/app/routers/enterprise_org.py`、`backend/app/services/enterprise_org_service.py`、`backend/tests/test_enterprise_org.py`
- 可对照：`backend/app/routers/resources_ext.py`（openpyxl 先例）、`backend/app/routers/risk_sources_ext.py`

## 审查要点

1. 服务：模板/解析函数可读性、正则、常量位置；
2. 导入端点：异常兜底范围（宽 except 评估）、文件大小检查时机（先整读再 413 的评估）、节点查/建逻辑、去重；
3. available：org_path 构建（防环）、查询效率；
4. 测试质量：50 用例断言有效性；
5. 无过度工程、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_04_review_quality --claim-id <claim_id> --exit-code 0 --summary "组织任务4质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
