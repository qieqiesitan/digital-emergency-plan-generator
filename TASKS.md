## 🔴 当前状态快照（压缩恢复用）
- 正在做什么：法规知识图谱 GraphRAG 模块实施 ✅
- 刚完成的动作：
  - 后端：7个Python模块 + regulations路由 + generation/main集成（14个API已注册）
  - 前端：types + service + 5组件 + 管理页 + 路由（/settings/regulations）
  - 新增18文件，修改4文件，总计75KB代码
  - 后端导入验证通过，FastAPI应用加载成功
  - 依赖已安装：chromadb, networkx, pyyaml, PyMuPDF
- 下一步：整理30条核心法规条文 → 冷启动入库 → 端到端测试
- 关键上下文：
  - 图谱数据文件在 data/graph.json（空骨架，待冷启动填充）
  - 法规条文需整理为 data/texts/*.md 格式
  - 冷启动命令：python -m app.regulations.sync --bootstrap
  - 法规模块异常时自动降级，不影响预案生成

## 进行中的任务
- 🟢 法规模块后端 ✅
- 🟢 法规模块前端 ✅
- 🟡 冷启动数据准备（30条法规条文）
- ⬜ 端到端测试
