# Codex Custom Subagents task handoff v1

Task: ai_prompts_seed_2025

## 任务：后端 AI 提示词与种子模板更新为 GB 6441-2025

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；后端命令在 `backend` 子目录执行。前置依赖已提交：`backend/app/services/accident_types.py`（ACCIDENT_TYPES_2025）。

### 背景

AI 提示词多处引用旧国标 GB 6441-1986（含一份 15 类清单和「淹溾」错字），需更新为 GB 6441-2025 27 类；种子模板存于数据库，改完脚本需重新 seed。

### 27 类全文（提示词内嵌用）

`物体打击、厂（场）内车辆致害、道路（轨道）车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他`

### 第 1 步：`backend\app\services\risk_assessment_service.py`

精确替换（保留其他内容与转义）：

1. 技术标准列表：`- 《企业职工伤亡事故分类》（GB 6441-1986）` → `- 《生产安全事故分类与编码》（GB 6441-2025）`（约 :28 与 :367 同文的两处都要改）
2. 术语标准第 2 条（约 :60）：整句替换为：
   `2. 事故类型统一按 GB 6441-2025 分类：物体打击、厂（场）内车辆致害、道路（轨道）车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他。`
   （原句含「淹溾」错字，一并修正）
3. 第 3 条辨识维度句末的 15 类清单（约 :61）：同样替换为 27 类全文
4. 结论示例引文：`《企业职工伤亡事故分类》（GB 6441-1986）` → `《生产安全事故分类与编码》（GB 6441-2025）`；示例正文旧词按新口径更新：`火灾、爆炸` 保持；`中毒和窒息、车辆伤害` → `中毒、厂（场）内车辆致害`；`物体打击、高处坠落、灼伤、淹溺、起重伤害、机械伤害` → `物体打击、高处坠落、灼烫、淹溺、起重致害、机械致害`

### 第 2 步：`backend\app\services\risk_ai_service.py`

1. 两处 system prompt（约 :166/:221）：`精通 GB/T 13861 和 GB 6441` → `精通 GB/T 13861 和 GB 6441-2025`
2. suggest_events 提示词（约 :202）：`- accident_type: 事故类型（按 GB 6441-1986）` → `- accident_type: 事故类型（按 GB 6441-2025 的 27 类：物体打击、厂（场）内车辆致害、道路（轨道）车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他）`

### 第 3 步：`backend\seed_prompts_full.py`

1. :367 system_prompt 内【技术标准】的 GB 6441-1986 → GB 6441-2025（同第 1 步替换 1）
2. :367 术语标准第 2 条 15 类清单 → 27 类全文（同第 1 步替换 2，含淹溾→淹溺）
3. :367 结论示例引文与示例正文 → 同第 1 步替换 4
4. :432/:440 辨识维度句：`按火灾/爆炸、中毒和窒息、灼烧、触电、机械伤害、高处坠落、物体打击、车辆伤害、淹溺、其他伤害等事故类型` → `按 GB 6441-2025 事故类型（物体打击、厂（场）内车辆致害、机械致害、起重致害、触电、淹溺、灼烫、火灾、高处坠落、跌落、坍塌、水害、容器爆炸、管道爆炸、可燃气体爆炸、可燃液体蒸气爆炸、粉尘爆炸、民用爆炸物品爆炸、烟花爆竹爆炸、其他可燃固体爆炸、高温熔融物爆炸、中毒、窒息、滑坡、泄漏、其他等）`

### 第 4 步：重新 seed 同步数据库

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python seed_prompts_full.py
```

预期输出 `Seed complete: 0 new, N updated`（N>0）。

### 第 5 步：测试 + 提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_prompt_templates_onsite_cards.py tests/test_generation_batch_refactor.py -q
```

预期 PASS。若其他测试断言了旧提示词文本导致失败，允许同步更新测试文件（说明即可）。全绿后提交：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/services/risk_assessment_service.py backend/app/services/risk_ai_service.py backend/seed_prompts_full.py
git commit -m "feat(accident-types): update AI prompts and seeds to GB 6441-2025"
```

（若适配了测试文件，一并 add 并说明。）

### 红线

- 只改动上述 3 个文件 + 必要测试适配；只做文本替换，不做无关重构
- 不要更新 TASKS.md；中文保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 各文件替换点数量、seed 输出、测试结果
- commit SHA（git log -1 --format=%h）
