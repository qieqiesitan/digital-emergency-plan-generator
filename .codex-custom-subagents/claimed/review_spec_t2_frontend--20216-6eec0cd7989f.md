# Codex Custom Subagents task handoff v1

Task: review_spec_t2_frontend

## 任务：规格合规审查 — 前端事故类型共享模块（commit c9713d5）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件（实现者领到的原始任务，含全部代码与验收标准）：
`.codex-custom-subagents\claimed\accident_types_frontend--26704-5cde1ea56456.md`

### 实现者声称构建了什么

创建 `frontend/src/utils/accidentTypes.ts` 与 `frontend/src/utils/accidentTypes.test.ts`，TDD 红绿通过，commit c9713d5。已知偏差：测试文件首行补了 `import { describe, expect, it } from "vitest"`（仓库未开 vitest globals，仓库既有测试均显式 import）。

### 关键：不要信任报告

必须独立验证：

- 用 `git show c9713d5` 阅读实际代码
- 逐行对比实际实现与规格文件中的代码：清单顺序、映射表键值、函数签名与行为是否完全一致
- 评估已知偏差（vitest import）是否合理且必要（读仓库既有测试如 frontend/src/utils/riskHierarchyEvents.test.ts 确认惯例）
- 检查是否遗漏需求或添加规格外内容
- 运行 `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\frontend && npx vitest run src/utils/accidentTypes.test.ts` 验证 3 passed

### 检查清单

- ACCIDENT_TYPES_2025 是否 27 类且顺序与规格一致
- LEGACY_TO_NEW_ACCIDENT_TYPE_MAP 是否恰 22 项且值与规格一致
- normalizeAccidentType 行为与规格一致
- 测试覆盖规格全部断言
- git show --stat 应恰 2 文件（不含 lockfile 等意外改动）

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 对已知偏差（vitest import）的独立评估结论
- 逐项核验结果摘要
- 门禁结果（vitest 输出）
- task_id、claim_id、path（claim_task.py 输出）
