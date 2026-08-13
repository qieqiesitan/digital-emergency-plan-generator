# Codex Custom Subagents task handoff v1

Task: task_final_fix

## 修复任务：最终审查发现的二维码完整 URL 问题（重要）

### 背景

最终整体审查发现 1 项重要问题：`backend/app/services/risk_notice_card_docx.py` 的 `_render_header` 用 `make_qr_png(card.public_url)` 生成二维码，`public_url` 是相对路径 `/r/{token}`。设计规格 §11 要求二维码内容为「公开页完整 URL（{APP_BASE}/r/{public_token}）」——手机扫码相对路径无法解析主机，现场扫码场景实际不可用。

### 修复内容

1. 二维码内容改为完整 URL。推荐方案：导出端点从请求推导 base（`str(request.base_url).rstrip("/") + card.public_url`，随部署主机动态正确，无需新增配置）；或在 settings 增加 `APP_BASE` 配置（从环境变量读，默认空则回退请求 base）。选择你认为最稳健的方案，保持与前端复制链接（`location.origin + public_url`）一致。
2. 调整 `render_cards_docx` / `make_qr_png` 调用链：二维码使用完整 URL。
3. 补测试：docx 渲染路径断言内嵌二维码实际内容为完整 URL（现有测试只测了传绝对 URL 的纯函数，未覆盖渲染路径真实传参）。

### 范围与限制

* 只改 `backend/app/services/risk_notice_card_docx.py`、`backend/app/routers/risk_notice_card.py`、`backend/tests/test_risk_notice_card_docx.py`（如需 settings 改动则含 `backend/app/config.py` / `.env.example`）。
* 不修改前端。

### 验证

* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_risk_notice_card_docx.py tests/test_risk_notice_card_api.py -v` 全部 PASS。
* `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/ -q` 无回归（408+ passed）。
* `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净。
* 提交新 commit（不要 amend 9cbd30b），消息：`fix(risk-notice-card): embed full public url in exported qr code`，只含上述文件。

### 汇报

* 状态：DONE | BLOCKED | NEEDS_CONTEXT
* 方案说明（请求 base vs settings）
* 修改的文件与行
* 测试结果
* 新提交 SHA
