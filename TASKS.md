## 当前状态快照（压缩恢复用）
- 正在做什么：等待用户测试验证
- 刚完成的动作：
  - chat_dispatch.py `_generate_report`:
    1. prompt 从硬编码四段式 → 灵活结构（LLM 自主选图表类型和组织方式）
    2. 新增 system_prompt 注入"应急管理专业分析师"角色（行业背景 + 写作原则）
  - chat.py 报告处理: `_collect_llm` 调用前注入 system_prompt
- 下一步：用户重启后端 → 测试报告输出是否差异化
- 关键上下文：
  - 第一次改动失败原因：topic 驱动数据收集中 `_get_regulation_stats` 触发 `get_graph()` 懒加载，`threading.Lock` 在 async 上下文中可能导致事件循环阻塞
  - 本次采用保守策略：只改 prompt 灵活性 + system_prompt，不碰数据收集逻辑
  - 影响文件：chat_dispatch.py:530-565, chat.py:294-297
