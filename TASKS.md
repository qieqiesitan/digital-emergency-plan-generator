
## 当前状态快照（压缩恢复用）
- 正在做什么：修复风险分级管控测试反馈的 4 个问题
- 已完成：git save/codegraph 可用；npm run build 基线失败，其中包含本批相关错误：RiskHierarchyTree Props 缺 onAction、RiskManagementTab 传 onAction、未使用导入等
- 下一步：创建保存点，再按 TDD 写失败测试/验证；随后修路由、RiskHierarchyTree 图标和操作栏
- 关键上下文：前端构建当前有大量既有 TS 错误，不能以全量 build 作为唯一绿灯；修复目标至少要让风险相关 TS 错误消失

