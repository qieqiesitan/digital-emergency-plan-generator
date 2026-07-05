## 🔴 当前状态快照（压缩恢复用）
- 正在做什么：AI 生成增强功能迭代完成，等待验证
- 刚完成的动作：
  - 设计文档：docs/superpowers/specs/2026-07-05-ai-generation-enhancement-design.md
  - 后端：backend/app/routers/generation.py — 新增 regenerate_selection SSE 端点
  - 后端：backend/app/schemas/plan.py — 新增 RegenerateRequest schema
  - 前端：frontend/src/components/plan/AIGenerateButton.tsx — 重构为 Modal+快捷指令+双模式
  - 前端：frontend/src/components/plan/RichTextEditor.tsx — 新增选区监听+AI重写浮动按钮+AI标记
  - 前端：frontend/src/services/generationService.ts — 新增 regenerateSelectionStream
  - 前端：frontend/src/utils/quickPrompts.ts — 新增快捷指令模板（6预设+localStorage）
  - 前端：frontend/src/styles/global.css — 新增 ai-generated-section / ai-regenerated-highlight 样式
  - 前端：frontend/src/pages/Plan/PlanEditorPage.tsx — 传递新 props
- 下一步：前端 TypeScript 编译检查 / 后端启动测试
- 关键上下文：
  - 所有新 props 均为可选，向后兼容
  - 选区重生成仅桌面端（TipTap），移动端 textarea 降级隐藏
  - 0 新依赖

## 进行中的任务
- 🟢 AI 生成增强（自定义提示词+局部重生成+快捷指令） ✅