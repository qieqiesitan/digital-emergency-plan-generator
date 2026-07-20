## 当前状态快照（压缩恢复用）
- 正在做什么：全部代码质量优化完成
- 刚完成的动作：
  Phase 1 (代码层)：
    - services/sse_utils.py 新建 + chat.py/generation.py 迁移
    - services/llm_client.py 新建 + 统一 LLM 调用 (decrypt_api_key, llm_chat_completion, llm_collect_all)
    - generation.py 流式函数重构: 消除直接 httpx 调用
    - chat_dispatch.py 泛化 CRUD 基础设施: _generic_list/create/update/delete + ENTITY_REGISTRY
    - 8 个风险源/应急资源 CRUD 函数从 15 行/set 缩减到 5 行委托
  Phase 2 (模块重构)：
    - 消除 chat.py + chat_dispatch.py 中所有 12 处延迟导入
    - Mermaid 渲染管道合并: render_mermaid_worker.py + render_svg_worker.py 归档
  Phase 3 (模型清理)：
    - Enterprise schema 重构成 EnterpriseBase → Create/Update/Response 继承体系
    - 消除 ~60 行字段重复定义
  Phase 4 (文件清理)：
    - backend/scripts/ 18 个历史修复脚本归档到 archive/
    - 根目录 6 个测试/修复脚本归档到 scripts/archive/
    - render_mermaid_worker.py + render_svg_worker.py 归档（未使用）
    - -w 遗留文件删除
    - backend/venv 重复虚拟环境删除（保留 .venv 含 271 包）
- 待处理(低优先级)：
  - Phase 2.3: generation.py 批量生成函数合并（generate_batch/generate_batch_background）- 高影响需独立验证
  - chat_dispatch.py 中 Enterprise CRUD + Plan CRUD 泛化
  - RiskAssessment/ResourceInvestigation 模型合并
  - python -c "compile(...)" syntax check across all files
- 关键上下文：
  - 6 个 savepoint: de341d7 → ce3c872 → 1477e73 → b793833 → 3d01b0c → 38b7cbe → 16c9e8f → a90461d → 505d0b4
  - 4 个文件新增: sse_utils.py, llm_client.py, docs/codebase-optimization-plan.md
  - 26 个文件归档到 scripts/archive/
  - 1 个文件: -w 删除
