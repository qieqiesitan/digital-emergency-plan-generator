# Codex Custom Subagents task handoff v1

Task: task_hazard_01_review_quality2

## 目标

对隐患任务 1 的**质量修复提交做只读复审**（2 条建议：3 索引 + 留痕 SET NULL）。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`eae50b4`（父 `076e4f9`）
- 文件：`backend/db_migration_hazard_management.sql`、`backend/app/models/hazard_management.py`、`backend/tests/test_hazard_models.py`

## 复审要点

1. 3 条索引幂等追加且与模型 index=True 对齐；
2. rectifications/reviews/approvals user_id 改 SET NULL（模型 ondelete + nullable 同步），notifications 保持 CASCADE+NOT NULL 的取舍说明合理；
3. 迁移兼容既有库（DROP NOT NULL + 重建 FK 幂等 DO 块）；本地复跑两遍验证；
4. 测试 26 断言（含 FK 语义与索引断言）；
5. 无越界改动：提交仅含上述 3 个文件。

## 验证

- `python -m pytest tests/test_hazard_models.py -v` 预期 26 passed；`git show --check eae50b4` 干净。

## 输出格式

- 结论：✅ 通过 / ❌ 仍有问题（列明）
- 新问题标注严重级：**必须修复 / 建议修改 / 仅供参考**
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_01_review_quality2 --claim-id <claim_id> --exit-code 0 --summary "隐患任务1质量复审完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；任务池命令在任务池目录执行。
