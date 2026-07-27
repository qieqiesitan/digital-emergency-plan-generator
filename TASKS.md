## 当前状态快照（压缩恢复用）
- 正在做什么：全部代码质量优化实施完成
- 已完成：
  Phase 1 — LLM 调用统一、CRUD 泛化基础设施、SSE 统一、文件清理
  Phase 2 — 延迟导入消除、Mermaid 管道合并
  Phase 3 — Enterprise Schema 字段消除、ReportBase 模型合并、重复 venv 清理
  Phase 4 — 前端空壳组件确认（完整实现，非空壳）
  本次追加 — Enterprise/Plan CRUD 泛化扩展（+5 个函数迁移）、RiskAssessment/ResourceInvestigation ReportBase 合并、全部 9 个关键文件语法验证通过
- 待处理（低优先级 / 需测试覆盖）：
  - generation.py 批量生成合并（generate_batch / generate_batch_background ~80% 重复代码）
  - chat_dispatch.py 中 regulation/search/export 等特殊函数可选择性泛化
- 关键上下文：
  - 9 个关键文件全部通过 compile() 语法检查
  - 新增: services/sse_utils.py, services/llm_client.py, models/report_base.py
  - 30+ 文件归档到 scripts/archive/
  - 当前 HEAD: $hash
