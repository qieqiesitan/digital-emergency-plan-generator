# Codex Custom Subagents task handoff v1

Task: icon_01_quality_review

## 目标

你是资深代码审查员，对照需求与代码质量标准审查任务 1 的实现（规格合规性审查已通过，本审查聚焦代码质量）。发现问题要具体、分级、可执行。

## 实现内容（DESCRIPTION）

任务 1：iconfont 图标资产抓取与清洗。新增 `scripts/fetch_icons.py`（168 行，仓库自包含，直接调 iconfont 公开接口，24 项 MAPPING 按 id 抓取、清洗、分页重试、`--verify`）、`scripts/test_fetch_icons.py`（28 行，clean_svg 单测）、`frontend/src/assets/icons/` 24 个清洗后 SVG。

## 需求 / 计划（PLAN_OR_REQUIREMENTS）

计划文件：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system\docs\superpowers\plans\2026-08-16-icon-system.md`（任务 1，含 v2 分页修订与 fills 修正）。核心要求：
- `fetch_icons.py`：MAPPING 24 项（name→(term,id)，与设计文档 §4.3 一致）；`clean_svg` 去 class/style/version/硬编码 fill（hex+rgb），保留 fill="none"/stroke/viewBox；`search` 参数 `fills=""`+`line="1"`+分页；`MAX_PAGES=5`/`PAGE_SIZE=60`，按 term 所需 id 全集判断；失败重试 3 次间隔 2s；`--verify`；仓库自包含（仅标准库）。
- `test_fetch_icons.py`：`CleanSvgTest.test_strips_noise_and_preserves_geometry`。
- 24 个 SVG 资产命名/清洗正确；提交契约（2 脚本+24 SVG，消息精确，--check 干净）。

## 待审查的 Git 范围

- **Base：** `b00fd49`
- **Head：** `ddaed83`
- 工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`

```bash
git -C <worktree> diff --stat b00fd49..ddaed83
git -C <worktree> diff b00fd49..ddaed83
```

## 检查内容

**计划对齐：** 实现是否匹配计划/需求？偏差是有道理的改进还是有问题的偏离？计划功能是否到位？

**代码质量：** 关注点分离；错误处理（接口失败/缺 id/脏文件）；类型/可读性；DRY 但不过度抽象；边界情况（多 id 同 term、分页不足、空响应）。

**架构：** 设计决策合理（fetch 脚本职责单一）；可扩展性；安全（无 secrets、URL 拼接安全）；与仓库现有 `scripts/` 与 `frontend/src/assets` 模式集成是否干净。

**测试：** 测试验证真实行为（clean_svg 断言真实字符串变换）而非 mock；边界情况（rgb fill、fill="none" 保留）；是否有值得补的用例（如 `--verify` 脏文件分支）。

**生产就绪：** 文档（脚本 docstring 与设计文档引用）；无明显 bug；行尾/提交卫生。

**额外检查（subagent-driven-development 要求）：** 每个文件单一职责与清晰接口；实现是否遵循计划文件结构；本次实现是否创建了过大文件（168 行脚本是否合理）。

## 输出格式

### 优点
[具体]

### 问题

#### Critical（必须修复）
#### Important（应该修复）
#### Minor（锦上添花）

每个问题含：File:line、哪里有问题、为什么重要、怎么修（如不明显）。

### 建议

### 评估

**可以合并吗：** [是 | 否 | 修完再合]
**理由：** [1-2 句技术评估]

## 约束

- 只读审查，不修改文件；
- 未实际读代码/跑命令不下结论；不把小事标 Critical；
- 问题要具体到 file:line。

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。
