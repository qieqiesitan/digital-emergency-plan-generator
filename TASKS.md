## 🔴 当前状态快照（压缩恢复用）
- 正在做什么：PROTEGO 商城接入——已备份到 GitHub
- 备份到 GitHub：codex/protego-integration → PR #1 (draft)
- 刚完成的动作：
  - `backend/app/config.py`：新增 EXTERNAL_API_HMAC_SECRET, PROTEGO_CALLBACK_URL
  - `backend/app/middleware/hmac_auth.py`：新建 HMAC-SHA256 签名验证中间件，保护 /api/external/*
  - `backend/app/services/external_file_store.py`：新建外部文件下载服务（URL → 本地 uploads）
  - `backend/app/services/external_service.py`：新建回调服务（HMAC 签名 + 3次重试）
  - `backend/app/routers/external.py`：新建外部 API 路由器，3个端点：
    - POST /api/external/plans — 接收订单→建用户/企业→建预案→后台AI生成→DOCX导出→回调
    - GET /api/external/plans/{taskId}/status — 查询生成进度
    - GET /api/external/plans/{taskId}/files/{fileId} — 下载 DOCX 文件
  - `backend/app/main.py`：注册 HmacAuthMiddleware + external 路由器
- 下一步：PR #1 待审核合并；设置 EXTERNAL_API_HMAC_SECRET 后启动测试
- 关键上下文：
  - /api/external/* 端点不依赖现有用户认证，走独立 HMAC 签名
  - 外部用户通过 ywt_user_id 字段映射到本地 User 表
  - 后台生成复用现有的 _stream_llm、generate_plan_docx 等核心逻辑
  - 生成完成后自动回调 PROTEGO callback_url（HMAC 签名 + 最多3次重试）

## 进行中的任务
- 🟢 修复一键生成卡死问题 ✅
- 🟢 修复新建预案报错 ✅
- 🟢 修复 DOCX 下载/渲染 ✅
- 🟢 修复侧边栏状态更新 ✅
- 🟢 修复提示词管理显示 ✅
- 🟢 提示词全局优化 ✅
- 🟢 PROTEGO 商城接入——预案系统侧 ✅
