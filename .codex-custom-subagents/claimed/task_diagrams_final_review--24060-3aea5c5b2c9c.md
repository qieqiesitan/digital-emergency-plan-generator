# Codex Custom Subagents task handoff v1

Task: task_diagrams_final_review

## 任务：预案附图扩展全量最终审查

你是一个最终代码审查子智能体。三批实现已完成，请对整体实现做最终审查（规格覆盖度 + 跨批一致性 + 质量），只报告问题，不要修改任何文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\codex-plan-diagrams`

当前 HEAD 应为 `e8649f9`，分支 `codex/plan-diagrams-enhancement`。

### 审查对象

1. 规格：`docs\superpowers\specs\2026-08-08-plan-diagrams-enhancement-design.md`（全量）
2. 计划：`docs\superpowers\plans\2026-08-08-plan-diagrams-batch1.md` / `batch2.md` / `batch3.md`
3. 实现范围：`git log master..HEAD --oneline`（18 commits）

### 审查重点

**规格覆盖度**：
- batch1：章节图映射（sec_3/4_2/5/9_1）、4 类提示词、org_structure→mermaid、生成注入
- batch2：diagram_svgs 列/迁移、risk_matrix/evacuation 生成器、_attach_diagrams、补图接口、占位 warning
- batch3：前端 DiagramRenderer、缺数据提示条+补图按钮、预览/docx 导出

**跨批一致性**：
- diagram_svgs 结构（key/placeholder/reason/svg）在模型、schema、绘制器、前端类型、导出中一致
- 生成流程两处（单章/批量）都调用 _attach_diagrams
- 占位符在存储、预览、docx、质量校验中一致

**质量**：
- SVG 转义、XSS 防护
- SQLAlchemy JSONB 赋值触发脏标记
- 浏览器实例复用（非每章节启动）
- 无死代码/重复实现

### 输出

```
结论：PASS / FAIL
规格覆盖度：逐节列出（覆盖/缺失/偏差）
跨批一致性问题：...
质量问题（重要）：...
质量问题（轻微）：...
建议（可选）：...
```

不要修改任何文件、不要提交。
