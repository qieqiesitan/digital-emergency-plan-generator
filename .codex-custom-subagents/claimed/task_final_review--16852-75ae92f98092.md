# Codex Custom Subagents task handoff v1

Task: task_final_review

## 任务：最终整体审查（易用性优化全量）

你是最终代码审查子智能体。本任务是「数字化应急预案自动生成系统」易用性整体优化的最终审查。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD ca2e332）。必须 cd 到该目录操作。

- 规格：`docs/superpowers/specs/2026-08-08-usability-enhancement-design.md`
- 计划（6 份）：`docs/superpowers/plans/2026-08-09-usability-foundation.md`（A）、`usability-backend-core.md`（B）、`usability-backend-onboarding.md`（B2）、`usability-frontend-onboarding.md`（C1）、`usability-frontend-refactor.md`（C2）、`usability-mobile.md`（D）
- 实现：`git log 4ec3523..ca2e332 --oneline`（53 个提交），重点通读全量 diff 与关键文件实际代码

### 审查重点

1. **规格覆盖度**：规格文档全部章节（含第 13 节移动端）是否都有对应实现？逐节对照，列出每节的实现落点（文件/提交）或缺失项。
2. **计划完成度**：A1-A6、B1-B3、B2-1~B2-4、C1-1~C1-6、C2-1~C2-4、D-1~D-4 是否全部落地？用 `rg` 检查各计划文件中未勾选的 checkbox 与规格占位符。
3. **整体一致性**：跨提交的缓存 key（completion/plans/enterprises）、路由（桌面 /settings/ai-config 与移动端 /m/chat、/m/settings/*）、后端 API 契约（onboarding/candidates/completion/import）、文案中文化是否自洽？有无死链/孤立文件/未接线组件（如 ImportDrawer）？
4. **回归风险**：桌面端核心流程（登录→企业列表/详情→新建预案→AI 生成→导出预览→版本管理）是否被 C1/C2 改动破坏？重点抽查被大改的页面（OnboardingPage/PlanEditorPage/PlanCardsPage/EnterpriseDetailPage/MainLayout）。
5. **累积待办核实**（逐项确认是否仍存在，给出 file:line）：
   - completion 端点 IDOR 测试缺失（B3 复审建议）
   - 企业编辑页 GIS/平面图「清除」不持久化（后端 exclude_none）
   - 报告徽标同窗不刷新（merge 后未 invalidate）
   - ImportDrawer 未接线（单文件反馈/多文件 batch/模块归属）
   - chroma.sqlite3 tracked 二进制（git rm --cached + .gitignore）
   - PlanEditorPage 既有 lint 债
   - extract_candidates 类型守卫、PlanCardsPage 搜索防抖、双份表格逻辑
   - 移动端 SettingsScreen 导航路径不匹配（/m/profile vs /m/settings/profile）
   - 桌面端 AIGenerateButton「去配置」引导未改「联系管理员」
6. **关键流程走查**：首次引导（/onboarding）三步态、企业卡片+完成度、预案两步创建、样章确认、移动端 Dashboard 完成度卡片与 AI 助手聊天页——按代码路径通读一遍确认闭环。

### 汇报格式

```
结论：PASS / FAIL（附理由）
一、规格覆盖度（逐节：实现落点/缺失）
二、计划完成度（逐任务：落地/未落地）
三、整体一致性（问题清单，带 file:line）
四、回归风险（桌面端核心流程抽查结论）
五、累积待办核实（逐项：仍存在/已修复/范围外，带 file:line）
六、关键流程走查结论
七、阻塞性问题（若有）
```

### 注意

- 全程只读；如需临时副本对比，用完立即清理，不得留下任何痕迹。
- 不修改源码、不提交、不运行任何破坏性命令。

