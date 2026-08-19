# Codex Custom Subagents task handoff v1

Task: cockpit_04_spec_review

你正在审查「企业驾驶舱」任务 4 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 4 规格）

1. 新建 `frontend/src/styles/cockpit.css`：完整设计系统，包含页面/背景/顶栏/跑马灯/三栏网格/面板+角标/面板标题/环形图/雷达（环/十字/扫描/轨道/风险点/中心/说明）/分区柱条/待办/完成度环+模块/动态/底部导航/空态/错误态，7 个关键帧（cp-scan/cp-stream/cp-rise/cp-blink/cp-tick/cp-spin/cp-pulse），`prefers-reduced-motion` 降级，1240/860 响应式断点，与计划任务 4 步骤 1 代码块一致。
2. 新建 3 个组件：
   - `CockpitBackground.tsx`：grid/aurora×2/floor/scan/stream×2 + 7 个粒子（PARTICLES 数组），aria-hidden；
   - `CockpitHeader.tsx`：返回按钮（antd Button，青色）、企业名 + Enterprise Cockpit 副标、系统运行状态灯、行业标签、重大风险红色标签（majorCount>0 时显示）、编辑企业按钮；
   - `CockpitTicker.tsx`：items 双份内联渲染实现无缝滚动。
3. Commit：`feat(cockpit): cockpit design system css, background, header, ticker`；只改这 4 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit eea489d；4 文件 +279 行；tsc exit 0；eslint exit 0。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；`git show eea489d --stat` / 直接读文件核验；
- 与任务正文代码块逐行比对（尤其 CSS 关键帧、reduced-motion、响应式断点；组件 props/JSX 结构）；
- 检查是否有多余内容或范围外改动；
- 实际运行（工作目录 worktree\frontend）：
  - `npx tsc -b`
  - `npx eslint src/components/enterprise/cockpit`
- 检查提交只含 4 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（测试/检查输出、git show 核验、发现的任何问题）
