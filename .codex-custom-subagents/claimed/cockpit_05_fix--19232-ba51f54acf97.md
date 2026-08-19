# Codex Custom Subagents task handoff v1

Task: cockpit_05_fix

你正在修复「企业驾驶舱」任务 5 质量审查发现的 1 项重要缺陷（+1 项顺带文案）。只改下面列出的内容，提交单独 commit。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（git worktree，分支 codex/enterprise-cockpit。前端命令用 workdir 进入 frontend 子目录。）

## 缺陷 1（重要）：重大风险 TOP 色条恒为灰色

文件：`frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx`

根因：`RISK_LEVEL_COLORS` 的键是英文（major/larger/general/low），但后端 `top_risks[].level` 实际是中文（"重大/较大/一般/低"，见 `backend/app/services/enterprise_cockpit_service.py` 的 `_event_level`），导致 `RISK_LEVEL_COLORS[r.level]` 恒为 undefined，兜底灰色。

修复（保持后端契约中文不变，前端加中文映射）：

1. 在文件顶部 import 处，保留 `RISK_LEVEL_COLORS` 供环形图图例使用（图例键是英文 key，正常）；
2. 新增中文等级色映射常量并用于 TOP 色条：

```tsx
const LEVEL_CN_COLORS: Record<string, string> = {
  重大: "#ff4d4f",
  较大: "#ff9f43",
  一般: "#ffd666",
  低: "#40a9ff",
};
```

3. 把 TOP 色条那行改为：

```tsx
<span className="lv" style={{ background: LEVEL_CN_COLORS[r.level] || "#8aa3c8" }} />
```

## 缺陷 2（次要，顺带）：雷达注脚与圆心口径不一致

文件：`frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx`

当 `riskIndex` 为 0 时圆心显示 `--`，但注脚仍显示 `0 / 100`。将注脚改为：

```tsx
<div className="cp-radar-cap">风险点实时定位 · 圆心为风险指数 <b>{riskIndex > 0 ? riskIndex : "--"} / 100</b></div>
```

## 验证

运行（工作目录 worktree\frontend）：
- `npx tsc -b` → exit 0
- `npx eslint src/components/enterprise/cockpit/RiskDonutPanel.tsx src/components/enterprise/cockpit/RiskRadarPanel.tsx` → exit 0
- `git diff --check` 干净

## Commit

```bash
git add frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx
git commit -m "fix(cockpit): map chinese risk level to colors in top risks and align radar caption"
```

## 项目规则
- TASKS.md 永不提交；不要修改任务范围外文件；你不是孤立的，不要 revert 他人修改。
- 按 AGENTS.md 铁律一，在 TASKS.md 顶部追加「当前状态快照」（不提交）。

## 汇报格式
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修复内容、验证结果、commit SHA、自审发现
