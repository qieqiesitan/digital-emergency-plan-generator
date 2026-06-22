# Mermaid 流程图 DOCX 导出优化方案

## 排查结论

- 数据库中 Mermaid 代码语法正确
- `render_mermaid_png` 独立调用时全部渲染成功
- **根因**：每个图启动新 Chromium 实例，FastAPI 异步上下文下 user-data-dir 锁冲突导致后续浏览器启动失败

## 优化方案

### 方案 B（快速止血）— 当前实施

**文件**：`backend/app/services/mermaid_renderer.py`

1. **共享单例浏览器**：模块级 `_browser` 变量，所有渲染复用同一实例
2. **本地 Mermaid.js**：将 CDN JS 下载到本地 `backend/app/services/mermaid.min.js`，HTML 模板内联
3. **重试逻辑**：渲染失败自动重试最多 3 次，每次间隔 1 秒
4. **启动超时**：浏览器启动超时从 15s 提高到 30s

### 方案 A（长期优化）— 后续实施

1. `PlanSection` 新增 `mermaid_svgs` JSON 字段
2. AI 生成 section 内容时同步渲染 Mermaid → SVG
3. DOCX 导出时直接读取缓存 SVG 转 PNG
4. 渲染一次，永久复用

### 方案 C（备选）

前端 `MermaidRenderer` 已渲染 SVG，导出时前端收集所有 SVG 传给后端。

---

创建时间：2026-06-08
