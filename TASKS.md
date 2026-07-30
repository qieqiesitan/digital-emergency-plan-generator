## 当前状态快照（压缩恢复用）
- 正在做什么：风险评估方法管理页面开发 — 两个 React 页面组件已创建
- 已完成：
  1. frontend/src/pages/Enterprise/RiskMethodListPage.tsx — 卡片网格列表页（316行），Row+Col 3列布局，含系统/企业方法分组、5x5矩阵缩略图、模板选择新建弹窗
  2. frontend/src/pages/Enterprise/RiskMethodEditorPage.tsx — 双栏编辑器（439行），左70%参数/阈值编辑+区间重叠验证，右30%实时LS评估面板（Slider+矩阵高亮）
  3. 集成现有类型 riskManagement.ts、服务 riskManagementService.ts、引擎 riskMethodEngine.ts
- 下一步：验证 TypeScript 编译、添加路由配置、连接后端 API 联调
