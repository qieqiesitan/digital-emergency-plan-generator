# Codex Custom Subagents task handoff v1

Task: task_03_review_spec

## 规格合规审查：任务 3（常量数据：标志映射 + 应急处置模板）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 3 规格）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\services\risk_notice_card_data.py`
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_data.py`

**常量模块要求**（设计规格 §7/§8）：
* SIGN_CATEGORY_ORDER = ["warning", "prohibition", "instruction", "notice"]
* W/P/I/N 四个 helper 生成 {category, name, svg_name}
* GB6441_ACCIDENT_TYPES 含 20 类事故
* SIGN_GROUPS 覆盖全部 20 类；每类标志按 警告→禁止→指令→提示 顺序（同类别可多个，每类最多 2 个）；svg_name 全部在规格 §7.2 的 36 个资产清单内；DEFAULT_SIGN_GROUP = SIGN_GROUPS["其他伤害"]
* EMERGENCY_TEMPLATES 覆盖 20 类，每类至少 2 条标准步骤
* LEVEL_ORDER = ["重大","较大","一般","低"]；LEVEL_COLORS 含 重大/较大/一般/低/未评估 五色

**测试要求**：4 个测试：①20 类全覆盖 ②非空且顺序正确 ③每个标志引用存在的 SVG ④默认标志组与火灾模板非空且 >=2 条

**实现者报告的偏差**：原计划的排序断言 `cats == ordered` 对同类别含 2 个标志的类型（触电/灼烫/中毒和窒息/瓦斯爆炸）会误判失败（cats 含重复类别，ordered 是去重后的类别列表）。实现者将断言修正为「类别索引按 SIGN_CATEGORY_ORDER 单调不减」。**请核实该修正是否保留原校验意图（顺序 警告→禁止→指令→提示）且不弱化校验。**

**范围限制**：只改这 2 个文件；不创建服务/SVG；commit 消息精确 `feat(risk-notice-card): add sign mapping and emergency templates`。

### 实现者声称构建了什么

* commit `94960e9`（worktree `.worktrees\risk-notice-card`），2 文件 119 行
* SIGN_GROUPS 33 个 svg 引用，全部在规格 36 资产清单内
* 测试：3 passed + 1 failed（test_every_sign_refers_to_known_svg，SVG 未创建属预期）
* 测试断言修正（见上）

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 94960e9` 通读 diff。
2. 核对：
* SIGN_GROUPS 20 类全覆盖、顺序正确（警告→禁止→指令→提示，同类别最多 2 个）、svg_name 均在规格 §7.2 清单内（warning: explosion/fire/electric/machinery/fall/falling-object/vehicle/crane/burn/poison/suffocation/drowning/collapse/roof-fall/water-inrush；prohibition: smoking/hot-work/touch/standing/pass/throwing；instruction: helmet/goggles/gloves/insulating-shoes/anti-static-clothes/eliminate-static/seatbelt/gas-mask/lifejacket/ventilate/protective-suit；notice: exit/eyewash/shower）
* EMERGENCY_TEMPLATES 20 类全覆盖、每类 >=2 条、与设计规格 §8 语义一致
* LEVEL_ORDER/LEVEL_COLORS 与规格一致（#ff4d4f/#fa8c16/#fadb14/#52c41a/#bfbfbf）
* 测试断言修正是否合理（验证修正后仍能捕获「类别乱序」的错误实现——可手动构造反例推演）
* 提交范围与消息
3. 门禁实测：`cd backend && python -m pytest tests/test_risk_notice_card_data.py -v`（预期 3 passed 1 failed）
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配，含断言修正结论）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-2 已过审；任务 4 将创建 SVG 资产使第 3 个测试转绿。
* 测试文件 test_risk_notice_card_service.py 的 2 个测试应无回归。
