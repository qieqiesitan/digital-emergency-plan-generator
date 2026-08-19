# Codex Custom Subagents task handoff v1

Task: cockpit_05_impl

你正在实现「企业驾驶舱重构」实现计划的 任务 5：驾驶舱数据面板组件（环形图/雷达/待办/完成度/动态）。任务 1-4 已完成并通过双审。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（git worktree，分支 codex/enterprise-cockpit。前端命令用 workdir 进入该目录的 frontend 子目录，node_modules 已安装。任务 4 已创建 cockpit.css 与 CockpitBackground/Header/Ticker。）

## 任务描述（完整文本）

**文件：**
- 修改：`frontend/src/types/cockpit.ts`（追加 RISK_LEVEL_COLORS/LABELS 常量）
- 创建：`frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitTodoPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitCompletionPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitActivityPanel.tsx`

步骤 1：追加共享常量

在 `frontend/src/types/cockpit.ts` 末尾追加：

```ts
export const RISK_LEVEL_COLORS: Record<string, string> = {
  major: "#ff4d4f",
  larger: "#ff9f43",
  general: "#ffd666",
  low: "#40a9ff",
};

export const RISK_LEVEL_LABELS: Record<string, string> = {
  major: "重大",
  larger: "较大",
  general: "一般",
  low: "低",
};
```

步骤 2：实现环形图 + 重大风险 TOP 面板

创建 `RiskDonutPanel.tsx`：

```tsx
import type { RiskCounts, TopRisk } from "@/types/cockpit";
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from "@/types/cockpit";

const ORDER: Array<keyof RiskCounts> = ["major", "larger", "general", "low"];

function donutBackground(counts: RiskCounts): string {
  if (counts.total <= 0) return "rgba(255,255,255,.06)";
  let cursor = 0;
  const stops = ORDER.map((key) => {
    const pct = (counts[key] / counts.total) * 100;
    const start = cursor;
    cursor += pct;
    return `${RISK_LEVEL_COLORS[key]} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

interface Props {
  counts: RiskCounts;
  topRisks: TopRisk[];
}

export default function RiskDonutPanel({ counts, topRisks }: Props) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">风险等级分布</div>
      <div className="cp-donut" style={{ background: donutBackground(counts) }} />
      <div className="cp-donut-center">
        <b>{counts.total > 0 ? counts.total : "--"}</b>
        <span>风险事件</span>
      </div>
      <div className="cp-legend">
        {ORDER.map((key) => (
          <div className="cp-lg" key={key}>
            <span><i style={{ background: RISK_LEVEL_COLORS[key] }} />{RISK_LEVEL_LABELS[key]}</span>
            <b>{counts[key]}</b>
          </div>
        ))}
      </div>
      <div className="cp-h" style={{ marginTop: 14 }}>重大风险 TOP</div>
      {topRisks.length === 0 ? (
        <div className="cp-empty">暂无高风险数据</div>
      ) : (
        topRisks.slice(0, 3).map((r) => (
          <div className="cp-todo" style={{ marginBottom: 0 }} key={r.name}>
            <span className="lv" style={{ background: RISK_LEVEL_COLORS[r.level] || "#8aa3c8" }} />
            <div>
              <b>{r.name}</b>
              <span>综合得分 {r.score ?? "--"} · {r.responsible_unit ?? "未指定责任单位"}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
```

步骤 3：实现风险雷达 + 分区分布面板

创建 `RiskRadarPanel.tsx`：

```tsx
import type { ZoneRisk } from "@/types/cockpit";
import { RISK_LEVEL_COLORS } from "@/types/cockpit";

const DOTS = [
  { top: "34%", left: "62%", color: "#ff4d4f", delay: 0 },
  { top: "58%", left: "32%", color: "#ff9f43", delay: 0.5 },
  { top: "24%", left: "40%", color: "#ffd666", delay: 1 },
  { top: "66%", left: "58%", color: "#40a9ff", delay: 1.4 },
  { top: "48%", left: "74%", color: "#ff9f43", delay: 0.8 },
];

interface Props {
  riskIndex: number;
  zoneRisks: ZoneRisk[];
}

const LEVEL_ORDER = ["major", "larger", "general", "low"] as const;

export default function RiskRadarPanel({ riskIndex, zoneRisks }: Props) {
  return (
    <div className="cp-panel" style={{ flex: 1 }}>
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h" style={{ justifyContent: "space-between" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>风险雷达 <b>LIVE</b></span>
        <span className="right">扫描中 · 每 4.2s 刷新</span>
      </div>
      <div className="cp-radar">
        <div className="r r1" /><div className="r r2" /><div className="r r3" /><div className="r r4" />
        <div className="x h" /><div className="x v" />
        <div className="cp-sweep" />
        <div className="cp-orbit"><i /></div>
        <div className="cp-orbit o2"><i /></div>
        {DOTS.map((d, i) => (
          <div
            key={i}
            className="cp-riskdot"
            style={{ top: d.top, left: d.left, background: d.color, color: d.color, boxShadow: `0 0 12px ${d.color}`, animationDelay: `${d.delay}s` }}
          />
        ))}
        <div className="cp-radar-center">
          <b>{riskIndex > 0 ? riskIndex : "--"}</b>
          <span>综合风险指数</span>
        </div>
      </div>
      <div className="cp-radar-cap">风险点实时定位 · 圆心为风险指数 <b>{riskIndex} / 100</b></div>
      <div className="cp-h" style={{ marginTop: 12 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>分区风险分布</span>
        <span className="right">按管控区域</span>
      </div>
      <div className="cp-bars">
        {zoneRisks.length === 0 ? (
          <div className="cp-empty">暂无分区数据</div>
        ) : (
          zoneRisks.slice(0, 4).map((z) => (
            <div className="cp-bar-row" key={z.zone_name}>
              <span className="nm">{z.zone_name}</span>
              <div className="cp-bar">
                {LEVEL_ORDER.map((k) =>
                  z.counts[k] > 0 ? (
                    <i key={k} style={{ width: `${(z.counts[k] / z.total) * 100}%`, background: RISK_LEVEL_COLORS[k] }} />
                  ) : null,
                )}
              </div>
              <span className="tot">{z.total}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

步骤 4：实现待办 / 完成度 / 动态面板

创建 `CockpitTodoPanel.tsx`：

```tsx
import type { CockpitTodo } from "@/types/cockpit";

const PRIORITY_COLORS: Record<string, string> = { high: "#ff4d4f", medium: "#ff9f43", low: "#2f81f7" };

export default function CockpitTodoPanel({ todos }: { todos: CockpitTodo[] }) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">待办提醒 <b style={{ color: "#ff9f43" }}>{todos.length}</b></div>
      {todos.length === 0 ? (
        <div className="cp-empty">暂无待办事项</div>
      ) : (
        todos.map((t) => (
          <div className="cp-todo" key={t.title}>
            <span className="lv" style={{ background: PRIORITY_COLORS[t.priority] || "#2f81f7" }} />
            <div><b>{t.title}</b><span>{t.note}</span></div>
          </div>
        ))
      )}
    </div>
  );
}
```

创建 `CockpitCompletionPanel.tsx`：

```tsx
import type { CockpitCompletion } from "@/types/cockpit";

export default function CockpitCompletionPanel({ completion }: { completion: CockpitCompletion }) {
  const percent = completion.percent ?? 0;
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">数据完成度</div>
      <div className="cp-ringwrap">
        <div className="cp-ring" style={{ background: `conic-gradient(#00d4ff 0 ${percent}%, rgba(255,255,255,.07) ${percent}% 100%)` }}>
          <b>{percent > 0 ? `${percent}%` : "--"}</b>
        </div>
        <div className="cp-modules">
          {completion.modules.length === 0 ? (
            <div className="cp-empty">暂无数据</div>
          ) : (
            completion.modules.map((m) => (
              <div className="cp-mod" key={m.key}>
                {m.label}
                {m.done ? <b>✓</b> : <b className="warn">…</b>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
```

创建 `CockpitActivityPanel.tsx`：

```tsx
import type { ActivityItem } from "@/types/cockpit";

function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function CockpitActivityPanel({ activities }: { activities: ActivityItem[] }) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">最近动态</div>
      <div className="cp-feed">
        {activities.length === 0 ? (
          <div className="cp-empty">暂无动态</div>
        ) : (
          activities.slice(0, 3).map((a, i) => (
            <div className="it" key={i}>
              <span className="dot" />
              <span><b>{a.actor}</b> {a.action}</span>
              <span className="tm">{formatTime(a.time)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

步骤 5：验证
运行：`cd frontend && npx tsc -b && npx eslint src/components/enterprise/cockpit src/types/cockpit.ts`
预期：exit 0

步骤 6：Commit
```bash
git add frontend/src/types/cockpit.ts frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx frontend/src/components/enterprise/cockpit/CockpitTodoPanel.tsx frontend/src/components/enterprise/cockpit/CockpitCompletionPanel.tsx frontend/src/components/enterprise/cockpit/CockpitActivityPanel.tsx
git commit -m "feat(cockpit): cockpit data panels (donut, radar, todo, completion, activity)"
```

## 上下文（场景铺设）
- 任务 4 的 cockpit.css 已定义全部所需类（cp-panel/cp-corner/cp-h/cp-donut/cp-donut-center/cp-legend/cp-lg/cp-radar/cp-sweep/cp-orbit/cp-riskdot/cp-radar-center/cp-radar-cap/cp-bars/cp-bar-row/cp-bar/cp-todo/cp-ring/cp-ringwrap/cp-modules/cp-mod/cp-feed/cp-empty 等），本任务组件直接消费这些类名，样式无需改动。
- 类型契约：`RiskCounts/TopRisk/ZoneRisk/CockpitTodo/CockpitCompletion/ActivityItem` 已在任务 3 定义；本任务追加 RISK_LEVEL_COLORS/LABELS。
- 这些面板由任务 6 的 EnterpriseCockpitPage 组装，本任务无需挂路由。

## 项目规则
- 提交消息遵循 conventional commits；TASKS.md 永不提交；不要修改任务范围外文件；提交前 `git diff --check`。
- 你不是孤立的：同一 worktree 可能有其他会话/代理改动，不要 revert 他人修改；冲突先停下提问。
- 按 AGENTS.md 铁律一，在 TASKS.md 顶部追加「当前状态快照」（不提交）。

## 开始之前
有疑问现在就问，不要猜测。

## 汇报格式
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现内容、验证结果、修改文件清单、commit SHA、自审发现
