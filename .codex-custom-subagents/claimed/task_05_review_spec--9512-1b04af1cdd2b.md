# Codex Custom Subagents task handoff v1

Task: task_05_review_spec

## 规格合规审查：任务 5（schemas + CardData 组装服务）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 5 规格）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\schemas\risk_notice_card.py`
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\services\risk_notice_card_service.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_service.py`（追加 5 个测试）

**schemas 要求**：SignItem（category Literal 四类）、RightColumn（hazard_description/accident_types/control_measures/emergency_measures）、CardData(RightColumn)（object_id/enterprise_name/name/code/level/level_color/responsible_unit/responsible_person/contact_phone/fallback_used/signs/snapshot/stale/public_url/generated_at）、CardSummary、ExportRequest/ExportResponse、AiOptimizeResponse、SnapshotSaveRequest

**service 要求**（设计规格 §9 + 计划任务 5）：
* compute_level：LEVEL_ORDER 取最高，空返回"未评估"
* resolve_responsible：对象字段优先 + 企业兜底，返回 (unit, person, phone, fallback)
* compute_code：FX-{序号:03d}
* build_right_column：快照优先；危险因素归并；事故类型去重；管控措施=engineering/management/ppe 编号；应急处置=emergency 优先+模板兜底（不足 2 条补模板，按事故类型取，仍空用通用模板）
* match_signs：SIGN_GROUPS 合并去重，SIGN_CATEGORY_ORDER 排序，每类别最多 2 个
* is_stale / get_snapshot / load_events_and_measures / build_card_data / save_snapshot

**实现者报告的 2 处修正**（请核实合理性）：
1. compute_code：id 为 None 时用对象身份匹配兜底（修正 None==None 误匹配第 1 个对象）
2. match_signs：返回 dict 列表而非 list[SignItem]（pydantic v2 模型不支持下标访问；CardData 校验时自动转 SignItem）

**范围限制**：只创建 schemas、service、追加测试；不创建路由；commit 消息 `feat(risk-notice-card): add card assembly service`。

### 实现者声称构建了什么

* commit `3b4709a`（3 文件），7 passed（含既有 2 模型测试），test_risk_notice_card_data.py 5 passed 无回归
* 容器验证（2-backend 镜像 + host backend 挂载）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 3b4709a` 逐行核对。
2. 核对：
* schemas 字段与设计规格 §9 一致（CardData 继承 RightColumn、signs/snapshot/stale/public_url/generated_at）
* service 各函数行为与规格一致（等级取最高、兜底逻辑、应急处置 emergency 优先+模板兜底、标志匹配顺序、快照优先与 stale 判定、编号 FX-{03d}）
* 2 处修正是否合理且不改变规格语义
* 提交范围与消息
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_service.py tests/test_risk_notice_card_data.py -v`（预期全 PASS）
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-4 已过审；任务 6 路由将使用本服务与 schemas。
