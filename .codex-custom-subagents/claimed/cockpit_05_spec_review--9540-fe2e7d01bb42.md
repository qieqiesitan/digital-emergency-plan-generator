# Codex Custom Subagents task handoff v1

Task: cockpit_05_spec_review

你正在审查「企业驾驶舱」任务 5 的实现是否与其规格匹配（规格合规性审查，只读，不修改代码）。

## 要求的内容（任务 5 规格）

1. `frontend/src/types/cockpit.ts` 末尾追加 `RISK_LEVEL_COLORS`（major #ff4d4f / larger #ff9f43 / general #ffd666 / low #40a9ff）与 `RISK_LEVEL_LABELS`（重大/较大/一般/低）。
2. 新建 5 个面板组件（均消费任务 4 cockpit.css 的 cp- 类）：
   - `RiskDonutPanel.tsx`：props {counts: RiskCounts; topRisks: TopRisk[]}；conic-gradient 环形图（total<=0 时灰底）+ 中心总数/-- + 四等级图例 + 重大风险 TOP（最多 3 条，等级色条，得分/责任单位，空态「暂无高风险数据」）；
   - `RiskRadarPanel.tsx`：props {riskIndex: number; zoneRisks: ZoneRisk[]}；四环+十字+扫描+双轨道点+5 个等级色光点+中心指数（riskIndex>0 显示数字否则 --）+「风险点实时定位…」注脚 + 分区风险分布堆叠条（最多 4 区，按 counts 比例，空态「暂无分区数据」）；
   - `CockpitTodoPanel.tsx`：props {todos}；高/中/低优先级色条（#ff4d4f/#ff9f43/#2f81f7）+ 计数 + 空态；
   - `CockpitCompletionPanel.tsx`：props {completion}；conic-gradient 完成度环（percent>0 显示 % 否则 --）+ 模块清单（done ✓ / 未完成 …）+ 空态；
   - `CockpitActivityPanel.tsx`：props {activities}；最多 3 条，时间格式化（M/D HH:mm）+ 空态。
3. Commit：`feat(cockpit): cockpit data panels (donut, radar, todo, completion, activity)`；只改这 6 个文件；不提交 TASKS.md。

## 实现者声称构建了什么
- 状态 DONE；commit ba95be2（父 eea489d）；6 文件 227+；tsc/eslint exit 0。

## 关键：不要信任报告

独立验证（只读）：

- 工作目录：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit；`git show ba95be2 --stat` / 直接读文件核验；
- 与任务正文代码块逐行比对（如手头无任务正文，可按上面「要求的内容」逐项核验组件 props/渲染分支/空态/格式化）；
- 检查是否有多余内容或范围外改动；
- 实际运行（工作目录 worktree\frontend）：
  - `npx tsc -b`
  - `npx eslint src/components/enterprise/cockpit src/types/cockpit.ts`
- 检查提交只含 6 个目标文件、无 TASKS.md。

## 输出格式
- ✅ 符合规格（经代码检查后一切匹配），或
- ❌ 发现问题：[具体列出缺失/多余/偏差，附 file:line 引用]

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 结论与依据（检查输出、git show 核验、发现的任何问题）
