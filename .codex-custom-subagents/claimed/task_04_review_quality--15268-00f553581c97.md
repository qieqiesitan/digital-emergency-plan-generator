# Codex Custom Subagents task handoff v1

Task: task_04_review_quality

## 代码质量审查：任务 4（SVG 标志资产 + 静态挂载）

你正在审查一个已通过规格合规审查的实现的质量。**独立阅读实际代码，不信任报告。**

### 被审查提交

worktree `C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）的 commit `7c744ce`：

* `backend/app/static/signs/` 36 个 SVG
* `backend/app/main.py`（/signs 挂载）
* `backend/tests/test_static_signs.py`

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 7c744ce` 通读。
2. 检查：
* SVG 资产质量：图形是否可辨识（如当心爆炸有爆炸符号、禁止烟火有烟/火图形、必须戴安全帽有头盔图形）、是否有明显画错的图形（如所有 warning 都一样、图形与名称不符）、XML 是否合法（能解析）、是否有冗余属性
* main.py 改动是否符合项目模式（对比 /icons /assets 挂载写法）
* test_static_signs.py 测试质量
* `git show --check` 是否干净
3. 报告格式：
* 结论：✅ 通过 或 ❌ 需修复
* 优点摘要
* 问题列表（每条带 file:line、级别【关键/重要/次要】、修复建议）

### 上下文

* 审查只读，不修改文件、不提交。
* 任务 8 docx 导出会把 SVG 转 PNG 嵌入 Word；前端 `<img>` 引用。
* 图形「无需像素级复刻」是已确认的规格约束，但「图形可辨识、与名称匹配」是质量底线（例如 warning-fire 应能看出是火）。
