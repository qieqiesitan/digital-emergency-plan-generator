# Codex Custom Subagents task handoff v1

Task: review_spec_t8_regulations

## 任务：规格合规审查 — 法规库补充 GB 6441-2025（commit cba91ea）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件（实现者领到的原始任务，含全部文件内容与验收标准）：
`.codex-custom-subagents\claimed\regulations_gb6441_2025--17612-14e5c0db9dd1.md`

### 实现者声称构建了什么

- 新建 `backend/app/regulations/data/texts/gb6441_2025.md`（113 行）
- `gb6441_1986.md` 插入废止标注
- `index.yaml` optional 追加 `gb6441_2025`
- 索引重建失败（chromadb 缺失，环境问题），commit cba91ea 未含 bm25_index.json，状态 DONE_WITH_CONCERNS

### 关键：不要信任报告

必须独立验证：

- 用 `git show cba91ea` 阅读实际改动
- 逐行对比 gb6441_2025.md 与规格文件中的完整文本（27 行表 1 名称/说明、前言、编码章节）
- 确认 gb6441_1986.md 标注插入位置与内容正确
- 确认 index.yaml 追加条目正确且 gb6441_1986 保留
- 确认提交恰 3 文件（bm25_index.json 未提交符合 DONE_WITH_CONCERNS 说明）

### 检查清单

- gb6441_2025.md 表 1 是否完整 27 行、名称与序号准确（注意第 17 类为「可燃液体蒸气爆炸」）
- 废止标注是否为规范引用块且位置在 `## 2 事故类别` 之前
- index.yaml 缩进与同级一致
- 是否有规格外改动

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 逐项核验结果摘要
- task_id、claim_id、path（claim_task.py 输出）
