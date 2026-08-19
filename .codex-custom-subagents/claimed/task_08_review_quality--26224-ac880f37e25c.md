# Codex Custom Subagents task handoff v1

Task: task_08_review_quality

## 目标

对「风险分级管控增强（A 阶段）」任务 8 的实现做**只读代码质量审查**（规格审查与复审已通过），聚焦代码质量与项目模式一致性。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`70c9b57` + `0b9647e` → 当前 HEAD=`0b9647e`
- 文件：
  - `backend/app/services/risk_control_list_service.py`
  - `backend/app/routers/risk_management.py`
  - `backend/app/routers/public_risk.py`
  - `backend/app/main.py`
  - `backend/tests/test_risk_control_list.py`
- 可对照：项目既有服务/路由/测试风格

## 审查要点

1. 清单服务：`flatten_rows`/`_row`/`_COLUMN_MAP`/`build_ledger_workbook` 结构清晰、可读；sheet2 汇总实现；
2. 路由：control-list 筛选/分页、export StreamingResponse、publicity token 生成/重置、`_zone_dual_levels` 复用；`_ZONE_TREE_OPTIONS` 与 public_risk 重复定义评估；
3. 公开端点：脱敏字段白名单、404 语义、generated_at UTC 说明；
4. 测试：16 用例质量（断言有效性、mock 组织、无空断言）；
5. 有无过度工程、越界改动。

## 输出格式

- 结论：✅ 通过 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_08_review_quality --claim-id <claim_id> --exit-code 0 --summary "任务8代码质量审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
