# Codex Custom Subagents task handoff v1

Task: review_spec_t1_backend

## 任务：规格合规审查 — 后端事故类型共享模块（commit 8682923）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件（实现者领到的原始任务，含全部代码与验收标准）：
`.codex-custom-subagents\claimed\accident_types_backend--11864-9db2611b7115.md`

### 实现者声称构建了什么

创建 `backend/app/services/accident_types.py`（27 类清单 + 22 项映射 + normalize/split）与 `backend/tests/test_accident_types.py`（4 用例），TDD 红绿通过，commit 8682923。

### 关键：不要信任报告

必须独立验证：

- 用 `git show 8682923` / `git diff a703301..8682923` 阅读实际代码
- 逐行对比实际实现与规格文件中的代码：清单顺序、映射表键值、函数签名与行为是否完全一致
- 检查实现者是否遗漏需求或添加了规格外内容
- 运行 `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -m pytest tests/test_accident_types.py -q` 验证 4 passed

### 检查清单

- 27 类清单是否与 GB 6441-2025 表 1 顺序完全一致（特别注意：厂（场）内车辆致害、道路（轨道）车辆致害、可燃液体蒸气爆炸、其他）
- LEGACY_TO_NEW_MAP 是否恰为 22 项且值与规格一致（瓦斯爆炸→可燃气体爆炸、锅炉爆炸→容器爆炸、爆炸→其他、中毒窒息→中毒）
- normalize_accident_type / split_accident_values 行为是否与规格一致（空值/None→""；未知值原样保留；顿号/逗号拆分）
- 测试是否覆盖规格要求的全部断言
- 是否有规格外文件改动（git show --stat 应恰 2 文件）

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 逐项核验结果摘要
- 门禁结果（pytest 输出）
- task_id、claim_id、path（claim_task.py 输出）
