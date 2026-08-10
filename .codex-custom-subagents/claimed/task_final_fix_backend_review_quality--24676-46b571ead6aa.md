# Codex Custom Subagents task handoff v1

Task: task_final_fix_backend_review_quality

## 任务：代码质量审查——task_final_fix_backend（规格审查通过后）

你是代码质量审查子智能体。请审查后端收敛修复的代码质量。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 2f3a2f0）。

审查命令：cd 到 worktree 后 `git log ca2e332..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 审查重点

1. 密码重置：token 生成安全性（secrets/random 强度）、过期校验、密码哈希方式与既有注册/重置一致、表索引、事务/错误处理、接口响应不泄露信息。
2. 企业 PUT：exclude_unset 语义是否破坏其他字段更新路径（如 name 显式 null 防护）、前端发送 payload 是否兼容（有无字段被误清空）。
3. 完成度分摊：跳过状态与报告生成状态的联动（跳过后被生成是否自动失效）、compute_completion 权重计算正确性、无报告时默认行为、模块结构兼容。
4. 配置回填：SQL 幂等性、跨库兼容（SQLite/Postgres 方言）、字段完整性（API key 等）。
5. 测试质量：断言有效、无脆弱断言；新增代码无类型逃逸/风格问题。

### 门禁

- `cd backend && .\.venv\Scripts\python -m pytest -q --ignore=_docker_test.py` 全绿
- `git diff --check` 干净

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复

