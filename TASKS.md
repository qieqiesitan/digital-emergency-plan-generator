## 当前状态快照（压缩恢复用）
- 正在做什么：Phase 1 代码质量优化完成
- 刚完成的动作：
  Phase 1.0: 创建 services/sse_utils.py，统一 chat.py 和 generation.py 中的 SSE 函数
  Phase 1.1: backend/scripts/ 中 18 个历史修复脚本归档到 archive/
  Phase 1.2: 根目录 6 个临时脚本归档到 scripts/archive/，删除 -w 遗留文件
  Phase 1.3: 创建 services/llm_client.py，统一 LLM 调用逻辑（decrypt_api_key + llm_chat_completion + llm_collect_all），重构 generation.py 流式函数消除 httpx 重复
  Phase 1.4: 在 chat_dispatch.py 中添加泛化 CRUD 基础设施（_generic_list/create/update/delete + ENTITY_REGISTRY），8 个风险源/应急资源 CRUD 函数改为3行委托
- 下一步：Phase 2+（合并批量生成逻辑、合并 Mermaid 管道、延迟导入消除、模型/Schema 合并、前端空壳组件处理）
- 关键上下文：
  - 34 个文件变更，4 个文件新增（sse_utils.py, llm_client.py），24 个文件归档，1 个文件删除
  - 3 个 savepoint：de341d7(初始) → ce3c872 → 1477e73 → b793833 → 3d01b0c(当前)
  - 新增后端模块：services/sse_utils.py, services/llm_client.py
  - 待处理：Phase 1.4 剩余的 8+ 个 CRUD 函数（enterprise, plan）待泛化
