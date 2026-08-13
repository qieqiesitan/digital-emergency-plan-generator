# Codex Custom Subagents task handoff v1

Task: task_06_review_spec

## 规格合规审查：任务 6（列表/详情 API 路由）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 6 规格 + 设计规格 §9）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\risk_notice_card.py`
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\routers\public_risk_notice.py`（占位空 router）
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\main.py`（注册 2 路由，prefix /api/v1）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_api.py`

**端点要求**（设计规格 §9）：
* GET `/enterprises/{eid}/risk-notice-cards`：列表摘要（id/name/zone_name/level/level_color/accident_types/signs/responsible_unit/snapshot/public_url/stale），支持 level/zone_id/keyword 筛选
* GET `/enterprises/{eid}/risk-notice-cards/{oid}`：单卡 CardData（快照优先）
* 归属校验：企业不存在 404；风险点不存在 404

**范围限制**：只创建 2 路由 + main.py 注册 + API 测试；不实现导出/AI/快照/token 端点；commit 消息 `feat(risk-notice-card): add list and detail endpoints`。

### 实现者声称构建了什么

* commit `661476d`（4 文件），7 个 API 测试 passed + 18 回归 passed
* 列表含 level/zone_id/keyword 筛选，企业对象只查一次复用
* 详情归属校验 + build_card_data
* 占位公开路由 + main.py 注册

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 661476d` 逐行核对。
2. 核对：
* 端点路径与方法、响应模型（ApiResponse[list[CardSummary]] / ApiResponse[CardData]）
* 筛选参数 level/zone_id/keyword 是否正确应用
* 归属校验（企业 404、风险点 404）
* main.py 注册正确（prefix /api/v1）
* 占位公开路由存在且不影响启动
* 提交范围与消息
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v`（预期全 PASS）+ 回归测试
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-5 已过审；任务 7-9 会在本路由文件追加 AI/快照/导出/token 端点。
