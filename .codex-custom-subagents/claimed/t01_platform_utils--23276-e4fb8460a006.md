# Codex Custom Subagents task handoff v1

Task: t01_platform_utils

## 任务：部署可交付性计划任务 1 —— platform.ts 新增 APP_BASE / stripAppBase（TDD）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

这是 git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。前端命令在 `frontend/` 子目录执行。基线：`npx tsc -b` 退出码 0，`npx vitest run` 48 passed。

### 背景

系统将支持部署在 nginx 子路径（如 `/emergency-plan-migration/`）。前端需要统一的子路径常量 `APP_BASE` 与剥离函数 `stripAppBase`，供路由 basename、菜单 key、移动端路径判断使用。开发环境（base 为 `/`）下两者必须保持现状行为（不剥任何前缀）。

### 步骤 1：编写失败的测试

创建 `frontend/src/utils/platform.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import { APP_BASE, stripAppBase } from "./platform";

describe("stripAppBase", () => {
  it("appBase 为空时原样返回 pathname", () => {
    expect(stripAppBase("/m/login", "")).toBe("/m/login");
  });

  it("剥离子路径前缀", () => {
    expect(
      stripAppBase("/emergency-plan-migration/m/login", "/emergency-plan-migration"),
    ).toBe("/m/login");
  });

  it("前缀不匹配时原样返回", () => {
    expect(stripAppBase("/other/m/login", "/emergency-plan-migration")).toBe(
      "/other/m/login",
    );
  });
});

describe("APP_BASE", () => {
  it("始终为字符串（根路径构建时为空串）", () => {
    expect(typeof APP_BASE).toBe("string");
  });
});
```

### 步骤 2：运行测试验证失败

```bash
cd frontend
npx vitest run src/utils/platform.test.ts
```

预期：FAIL，报错 `does not provide an export named 'stripAppBase'`（platform.ts 尚无该导出）。

### 步骤 3：实现 platform.ts

在 `frontend/src/utils/platform.ts` 末尾追加：

```ts
/** 应用部署子路径前缀（生产为 /emergency-plan-migration，开发为 ""） */
export const APP_BASE = import.meta.env.BASE_URL.replace(/\/+$/, "");

/** 从 pathname 中剥离应用子路径前缀，如 /emergency-plan-migration/m/login -> /m/login */
export function stripAppBase(pathname: string, appBase: string = APP_BASE): string {
  if (!appBase) return pathname;
  return pathname.startsWith(appBase) ? pathname.slice(appBase.length) : pathname;
}
```

### 步骤 4：运行测试验证通过

```bash
npx vitest run src/utils/platform.test.ts
```

预期：PASS（4 项全过）。

### 步骤 5：Commit

```bash
git add frontend/src/utils/platform.ts frontend/src/utils/platform.test.ts
git commit -m "feat(deploy): add APP_BASE and stripAppBase for subpath deployment"
```

### 门禁

1. `npx vitest run` 全量通过（基线 48 + 新增 4 = 52）；
2. `npx tsc -b` 退出码 0；
3. `npx eslint frontend/src/utils/platform.ts frontend/src/utils/platform.test.ts` 无新增 error；
4. `git diff --check` 干净；新增行不超 100 字符（软约定）；
5. 提交只含上述 2 个文件，提交消息精确匹配步骤 5。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你实现了什么；测试结果（含 vitest 数量）；修改的文件；自审发现；任何疑虑。遇到疑问先以 NEEDS_CONTEXT 或 BLOCKED 汇报，不要猜测。
