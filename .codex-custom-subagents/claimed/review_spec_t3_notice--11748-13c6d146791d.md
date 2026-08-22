# Codex Custom Subagents task handoff v1

Task: review_spec_t3_notice

## 任务：规格合规审查 — 风险告知卡 27 类升级（commit b3324a9）

### 工作目录

审查对象在隔离工作区：
`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

任务池根目录（claim_task 所在）：
`C:\Users\55061\Documents\数字化预案自动生成 2`

### 目的

验证实现者构建的是否为**所要求的内容（不多不少）**。这是只读审查：不要修改任何源码。

### 要求的内容（规格）

完整读取任务规格文件：`.codex-custom-subagents\claimed\notice_cards_2025--17092-10ff174fa1df.md`

### 实现者声称构建了什么

- `risk_notice_card_data.py`：SIGN_GROUPS/EMERGENCY_TEMPLATES 重建为 27 类键全集（16 沿用/更名/承接 + 11 新增），兜底组改「其他」
- `risk_notice_card_service.py`：match_signs 查表入口 normalize 兼容旧值
- 两个测试文件切到新键；目标 76 passed；全量 1040 passed

### 关键：不要信任报告

必须独立验证：

- `git show b3324a9` 阅读实际改动
- 逐键核对 `SIGN_GROUPS` 与 `EMERGENCY_TEMPLATES` 是否**恰为 27 类全集**且与规格文件中的完整内容一致（键全集 = ACCIDENT_TYPES_2025，无旧键残留、无多余键）
- 核对 11 个新键的标志组/处置模板内容与规格一致（跌落/管道爆炸/可燃液体蒸气爆炸/粉尘爆炸/烟花爆竹爆炸/其他可燃固体爆炸/高温熔融物爆炸/窒息/滑坡/泄漏/道路（轨道）车辆致害）
- 核对 `match_signs` 的 normalize 兼容实现（旧值如 瓦斯爆炸 映射到新组）
- 运行：`cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend && python -m pytest tests/test_risk_notice_card_data.py tests/test_risk_notice_card_service.py tests/test_risk_notice_card_api.py -q`
- git show --stat 应恰 4 文件
- 用 `python -c "from app.services.accident_types import ACCIDENT_TYPES_2025; from app.services.risk_notice_card_data import SIGN_GROUPS, EMERGENCY_TEMPLATES; assert set(SIGN_GROUPS)==set(ACCIDENT_TYPES_2025); assert set(EMERGENCY_TEMPLATES)==set(ACCIDENT_TYPES_2025)"` 验证键集

### 汇报格式

- 结论：✅ 符合规格 | ❌ 发现问题（逐条列出，附 file:line）
- 键集核对结果、11 新键逐项结果、match_signs 兼容结果
- 门禁结果（pytest 输出）
- task_id、claim_id、path（claim_task.py 输出）
