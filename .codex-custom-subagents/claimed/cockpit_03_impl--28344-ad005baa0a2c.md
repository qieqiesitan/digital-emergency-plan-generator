# Codex Custom Subagents task handoff v1

Task: cockpit_03_impl

你正在实现「企业驾驶舱重构」实现计划的 任务 3：前端类型 + cockpitService + 契约测试。任务 1/2（后端）已完成并通过双审。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（git worktree，分支 codex/enterprise-cockpit。前端命令用 workdir 进入该目录的 frontend 子目录，node_modules 已安装。）

## 任务描述（完整文本）

**文件：**
- 创建：`frontend/src/types/cockpit.ts`
- 创建：`frontend/src/services/cockpitService.ts`
- 创建：`frontend/src/services/cockpitService.test.ts`

步骤 1：编写失败的测试

创建 `frontend/src/services/cockpitService.test.ts`（沿用 riskManagementService.test.ts 的 mock 惯例）：

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/services/api", () => ({
  default: { get: vi.fn() },
}));

import api from "@/services/api";
import { getCockpitSummary } from "@/services/cockpitService";
import type { CockpitSummary } from "@/types/cockpit";

const mockedGet = vi.mocked(api.get);

describe("cockpitService", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("requests cockpit-summary with the enterprise id", async () => {
    const summary: CockpitSummary = {
      risk_counts: { major: 1, larger: 1, general: 1, low: 1, total: 4 },
      zone_risks: [],
      top_risks: [],
      risk_index: 55,
      hazard_counts: { open: 3, due: 2, overdue: 0 },
      todos: [],
      completion: { percent: 50, modules: [] },
      recent_activities: [],
    };
    mockedGet.mockResolvedValue({ data: { data: summary } });

    const result = await getCockpitSummary("e1");

    expect(mockedGet).toHaveBeenCalledWith("/enterprises/e1/cockpit-summary");
    expect(result).toEqual(summary);
  });
});
```

步骤 2：运行测试确认失败
运行：`cd frontend && npx vitest run src/services/cockpitService.test.ts`
预期：FAIL，`Cannot find module '@/services/cockpitService'`（或类型缺失）

步骤 3：实现类型与服务

创建 `frontend/src/types/cockpit.ts`：

```ts
export interface RiskCounts {
  major: number;
  larger: number;
  general: number;
  low: number;
  total: number;
}

export interface TopRisk {
  name: string;
  level: string;
  score: number | null;
  responsible_unit: string | null;
}

export interface ZoneRisk {
  zone_name: string;
  counts: RiskCounts;
  total: number;
}

export interface CockpitTodo {
  priority: "high" | "medium" | "low";
  title: string;
  note: string;
}

export interface CompletionModule {
  key: string;
  label: string;
  done: boolean;
}

export interface CockpitCompletion {
  percent: number;
  modules: CompletionModule[];
}

export interface ActivityItem {
  actor: string;
  action: string;
  time: string;
}

export interface HazardCounts {
  open: number;
  due: number;
  overdue: number;
}

export interface CockpitSummary {
  risk_counts: RiskCounts;
  zone_risks: ZoneRisk[];
  top_risks: TopRisk[];
  risk_index: number;
  hazard_counts: HazardCounts;
  todos: CockpitTodo[];
  completion: CockpitCompletion;
  recent_activities: ActivityItem[];
}
```

创建 `frontend/src/services/cockpitService.ts`：

```ts
import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { CockpitSummary } from "@/types/cockpit";

export const getCockpitSummary = (enterpriseId: string): Promise<CockpitSummary> =>
  api
    .get<ApiResponse<CockpitSummary>>(`/enterprises/${enterpriseId}/cockpit-summary`)
    .then((r) => r.data.data);
```

步骤 4：运行测试确认通过
运行：`cd frontend && npx vitest run src/services/cockpitService.test.ts`
预期：1 passed

再运行类型检查：
运行：`cd frontend && npx tsc -b`
预期：exit 0

步骤 5：Commit
```bash
git add frontend/src/types/cockpit.ts frontend/src/services/cockpitService.ts frontend/src/services/cockpitService.test.ts
git commit -m "feat(cockpit): cockpit summary frontend service"
```

## 上下文（场景铺设）
- 后端契约已定：`GET /enterprises/{id}/cockpit-summary` 返回 `{code, message, data: CockpitSummary}`；CockpitSummary 字段见上面类型（与后端 schema 一一对应，risk_index 为归一化加权平均）。
- 项目前端 service 惯例（近几个任务已统一）：箭头函数 + `.then((r) => r.data.data)` 解包；测试用 `vi.mock("@/services/api")` mock get 并断言 URL 与返回值。可参考 `frontend/src/services/dataDictService.ts` 与 `dataDictService.test.ts`。
- 注意：`types/cockpit.ts` 暂不含 RISK_LEVEL_COLORS 常量（任务 5 追加），本任务不要加。

## 项目规则
- 提交消息遵循 conventional commits；TASKS.md 永不提交；不要修改任务范围外文件；提交前 `git diff --check`。
- 你不是孤立的：同一 worktree 可能有其他会话/代理改动，不要 revert 他人修改；冲突先停下提问。
- 按 AGENTS.md 铁律一，在 TASKS.md 顶部追加「当前状态快照」（不提交）。

## 开始之前
有疑问现在就问，不要猜测。

## 汇报格式
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现内容、测试命令与结果、修改文件清单、commit SHA、自审发现
