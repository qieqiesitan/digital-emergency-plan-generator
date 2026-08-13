# Codex Custom Subagents task handoff v1

Task: task_08_review_spec

## 规格合规审查：任务 8（docx 导出 + 二维码）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 8 规格 + 设计规格 §11/§13）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\services\risk_notice_card_docx.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\risk_notice_card.py`（POST /export）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\requirements.txt`（qrcode）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_docx.py`

**docx 要求**（设计规格 §11）：
* A4 竖版、每卡一页（分页符）
* 头部三区：企业名 / 居中标题「{name}安全风险告知卡」/ 右上角二维码 PNG
* 左栏：等级色带 + 键值表格（名称/编号/等级/责任单位/责任人/电话）+ 安全标志 PNG
* 右栏：四信息块（危险因素/事故类型【GB 6441】/管控措施/应急处置）
* 页脚：签发单位 / 编制日期 / 版本
* 文件名 `risk-notice-{enterprise_id[:8]}-{YYYYMMDDHHMMSS}.docx`，落 EXPORT_DIR，下载走 /export/download
* 二维码内容 = 公开页 URL（/r/{token}）

**导出端点**（设计规格 §9/§13）：
* POST /export body {object_ids} → {file_key}；个别卡异常跳过 + warnings 列表；全部无效 400

**实现者主动变更**：`ExportResponse` 增加 `warnings: list[str] = []`（规格 §13 要求响应返回 warnings，超出任务清单 4 文件的第 5 个文件）。请核实此变更合理且与规格一致。

**范围限制**：commit 消息 `feat(risk-notice-card): add docx export with qr code`。

### 实现者声称构建了什么

* commit `61458ff`（5 文件），全量 400 passed
* make_qr_png + svg_to_png（复用 render_svg_to_png，失败占位回退）+ render_cards_docx
* POST /export + ExportResponse.warnings
* 5 个测试（QR 头、2 卡 docx、集成 SVG→PNG、混合缺失 id、全无效 400）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 61458ff` 逐行核对。
2. 核对：
* docx 版式要素（头部三区/左栏/右栏/页脚/分页）
* 二维码内容 = public_url
* SVG→PNG 处理与占位回退
* 导出端点：归属校验、跳过+warnings、全无效 400、文件名、EXPORT_DIR
* warnings 字段变更与规格 §13 一致性
* 提交范围与消息
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_docx.py tests/test_risk_notice_card_api.py -v`（预期全 PASS）+ 全量回归
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-7 已过审；任务 9 会追加公开 API 与 token 重置。
