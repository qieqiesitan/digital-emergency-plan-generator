# Codex Custom Subagents task handoff v1

Task: task_final_review2

## 任务：最终整体复审（收敛修复后全量）

你是最终代码审查子智能体。前序最终审查发现 4 个阻塞性缺口，已分 3 批次修复（后端/前端/杂项）。请做最终整体复审，确认全部解决、无回归、全量测试通过。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 4d1f273）。

审查命令：cd 到 worktree 后 `git log ca2e332..HEAD --oneline`（收敛修复提交）逐提交 `git show`，必要时回溯 `git log 4ec3523..HEAD` 全量。

### 复审重点

1. **4 个阻塞性缺口已解决**：
   - 规格 11.2 密码找回骨架（password_reset_tokens 表 + /auth/forgot-password + /auth/reset-password + 测试）
   - 规格 6.3/6.4 资料包导入与每步导入/手动填写入口（ImportDrawer 接线、候选分流、_key 唯一、skipped 统计）
   - 规格 10 风险事件危化品关联（前端下拉 + payload chemical_id + schema 同步）
   - 移动端设置死导航（/m/profile → /m/settings/profile）
2. **其余遗留收敛**：GIS 清除持久化、完成度跳过分摊、AI 配置回填、报告徽标刷新、AIGenerateButton 文案、chroma 卫生、搜索防抖、计划 checkbox。
3. **全量验证**：
   - `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
   - `cd frontend && npx vitest run` 全绿
   - `cd backend && .\.venv\Scripts\python -m pytest -q --ignore=_docker_test.py` 全绿（预期 ≥315）
   - `git diff --check` 干净
4. **工作区卫生**：`git status --short` 仅 TASKS.md 未暂存（chroma.sqlite3 已解除跟踪，本地文件保留）；`git ls-files backend/app/regulations/data/chroma_db/` 仅 README。
5. **提交历史**：`git log --oneline 4ec3523..HEAD` 汇总本次全部提交（预计 53 + 12 收敛修复）。
6. **残余问题**：确认最终审查遗留清单中哪些已修、哪些记录为后续迭代（如 PlanEditorPage lint 债、双份表格、模糊去重兜底等非阻塞项），给出最终判断。

### 汇报格式

```
结论：PASS / FAIL（附理由）
一、4 个阻塞缺口逐项核验
二、遗留收敛项逐项核验
三、全量验证输出
四、工作区卫生与提交历史
五、残余问题清单（阻塞/非阻塞）
```

### 注意

- 全程只读；不修改源码、不提交、不运行破坏性命令；临时副本用完即清理。

