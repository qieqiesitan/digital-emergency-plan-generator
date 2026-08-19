# Codex Custom Subagents task handoff v1

Task: task_final_review

## 目标

对「风险分级管控增强（A 阶段）」整个分支做**只读最终整体审查**，对照 A 规格与实现计划验收标准，输出结论与遗留问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`929e0dd`）
- 分支范围：`master..HEAD`（自 `e9ce63b` 起的全部提交，约 40 个）
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md`
- 计划：`docs/superpowers/plans/2026-08-14-risk-control-enhancement.md`

## 审查要点

1. **规格覆盖度**：规格 §2 决策（双等级/折算/双模式/清单/公示/告知卡/字典）、§5-§10 功能、§14 验收标准 8 条——逐条核对实现证据（代码/测试/端点）与缺失；
2. **分支完整性**：40 个提交可追踪、无杂物（临时文件/误提交）、TASKS.md 未入提交；
3. **门禁复核**（只读）：后端全量 pytest、前端 tsc/vitest、`git show --check` 关键提交；
4. **一致性**：前后端契约（端点/字段/类型）一致；数据字典/权限种子落地；迁移幂等；
5. **遗留风险**：WorkbenchCanvas 既有 lint 债、menu:data_dicts 部署需执行新迁移、两字典页重复（接受的债务）、手工 UI 冒烟未执行项（建议合并后由用户浏览器验证）等——列出供合并决策参考。

## 输出格式

- 结论：✅ 可合并 / ❌ 需修复（列明）
- 规格覆盖对照表（验收标准 ↔ 证据 ↔ 结论）
- 遗留问题清单（阻塞/非阻塞）
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_final_review --claim-id <claim_id> --exit-code 0 --summary "最终整体审查完成"
```

## 规则

- 全程只读（可运行只读 pytest/vitest/tsc、git log/show/diff）；任务池命令在任务池目录执行。
