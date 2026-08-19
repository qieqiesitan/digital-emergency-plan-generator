# Codex Custom Subagents task handoff v1

Task: cockpit_final_review

你正在对「企业驾驶舱」整个实现分支做最终整体审查（规格覆盖 + 整体质量 + 合并建议；只读，不修改代码）。这是子代理驱动开发的收尾审查。

## 审查范围
- 分支：codex/enterprise-cockpit（worktree：C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit）
- BASE：99120f5（分支起点，docs 修正提交）→ HEAD：414a3a1（12 个提交，29 文件 +1705/-313）
- 规格：`docs/superpowers/specs/2026-08-16-enterprise-detail-redesign.md`（工作树内可读）
- 计划：`docs/superpowers/plans/2026-08-16-enterprise-detail-redesign.md`（工作树内可读）

## 审查要点

1. **规格覆盖度**（对照规格 §1-§11 逐节）：
   - 范围（仅驾驶舱深色、模块页保持浅色）；
   - 10 模块 4 组归类与图标导航；
   - 驾驶舱布局（顶栏/跑马灯/左中右三翼/底部导航）、动效规范与 reduced-motion、视觉令牌；
   - 模块页 B 方案（左竖分组导航：风险 9 项两组、隐患 6 项两组；简单模块无导航）；
   - 路由清单与旧路径重定向、?tab 兼容；
   - cockpit-summary 端点（含 risk_index 归一化口径、hazard_counts、todos、completion）；
   - 测试与验收 AC1-AC8 逐条核验是否可满足。
2. **整体质量**：分支提交卫生（每提交消息/范围）、有无遗漏文件、有无死代码/孤儿引用（rg EnterpriseDetailPage / ?tab= / HazardPlaceholderPage）、有无明显架构问题。
3. **门禁复跑**（可选抽查，避免全量耗时；至少跑）：
   - 后端：`C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe -m pytest tests/test_enterprise_cockpit.py -v`（工作目录 worktree\backend）
   - 前端：`npx tsc -b`（工作目录 worktree\frontend）
   - e2e：`npx playwright test e2e/enterprise-cockpit.spec.ts`（工作目录 worktree\frontend）
4. **已知取舍清单**（记录但不阻塞）：壳路由下子页面双头部、旧路径 navigate 依赖 redirect 兜底、recent_activities 为占位、?floor 子串匹配、模块不存在/键盘焦点等。

## 输出格式
- 规格覆盖：逐节 ✅/⚠/❌ 清单
- 质量：优点 / 问题（关键/重要/次要）
- 门禁结果
- 已知取舍清单
- 合并建议：可合并 / 需先修复（列出具体项）

## 汇报格式
- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 完整审查报告
