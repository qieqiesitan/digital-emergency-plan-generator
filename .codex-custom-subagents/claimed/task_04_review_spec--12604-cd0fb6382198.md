# Codex Custom Subagents task handoff v1

Task: task_04_review_spec

## 规格合规审查：任务 4（SVG 标志资产 + 静态挂载）

你正在审查一个实现是否与其规格匹配。**不要信任实现者的报告，必须独立阅读实际代码验证。**

### 要求的内容（任务 4 规格 + 设计规格 §7）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\static\signs\` 下 36 个 SVG
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\main.py`（挂载 /signs）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_static_signs.py`（新建）

**SVG 规范**（设计规格 §7.1）：
* 警告=黄底 #FFD100 黑边正三角黑图形（viewBox 0 0 28 26）
* 禁止=白底红圈 #C8102E 红斜杠黑图形（viewBox 0 0 28 28）
* 指令=蓝底 #005EB8 白图形（viewBox 0 0 28 28）
* 提示=绿底 #009A44 白图形（viewBox 0 0 28 28）

**36 资产清单**（设计规格 §7.2）：warning 16 个（explosion/fire/electric/machinery/fall/falling-object/vehicle/crane/burn/poison/suffocation/drowning/collapse/roof-fall/water-inrush/confined-space）、prohibition 6 个（smoking/hot-work/touch/standing/pass/throwing）、instruction 11 个（helmet/goggles/gloves/insulating-shoes/anti-static-clothes/eliminate-static/seatbelt/gas-mask/lifejacket/ventilate/protective-suit）、notice 3 个（exit/eyewash/shower）

**main.py 挂载**：SIGNS_DIR 指向 backend/app/static/signs，app.mount("/signs", StaticFiles(...), name="signs")

**测试**：test_static_signs.py 含引用存在性 + 形状/颜色抽查

**实现者报告的偏差**：任务文件 warning 清单列了 15 个但写 36 个；实现者按设计规格 §7.2（warning 16 个，含预留 confined-space）补齐，总数 36。**请核实该处理与规格一致。**

**范围限制**：只创建 SVG + main.py + test_static_signs.py；commit 消息 `feat(risk-notice-card): add gb2894 sign svg assets and static mount`。

### 实现者声称构建了什么

* commit `7c744ce`（38 文件 258+），36 个 SVG + main.py 挂载 + test_static_signs.py
* 测试 7 passed；/signs/warning-explosion.svg 与 /signs/notice-exit.svg 实测 200

### 你的工作

1. `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`，`git show 7c744ce --stat` + 检查 signs 目录。
2. 核对：
* 36 个 SVG 文件是否齐全且命名与清单精确一致（含 warning-confined-space）
* 抽查多个 SVG 内容：形状要素（警告 polygon、禁止 circle+line、指令 circle、提示 rect）与颜色（#FFD100/#C8102E/#005EB8/#009A44 + 黑/白对比色）符合规范
* main.py 挂载代码正确（SIGNS_DIR 路径、StaticFiles、name）
* test_static_signs.py 与任务要求一致（SIGN_DIR 用 parents[1]）
* 提交范围与消息
3. 门禁实测：`cd backend && python -m pytest tests/test_static_signs.py tests/test_risk_notice_card_data.py -v`（预期全部 PASS）
4. 报告格式：
* ✅ 符合规格（经代码检查后一切匹配）
* ❌ 发现问题：[具体列出，附带 file:line]

### 上下文

* worktree 独立分支 codex/risk-notice-card，审查只读，不修改文件、不提交。
* 任务 1-3 已过审；任务 5 组装服务将消费标志映射与 SVG。
