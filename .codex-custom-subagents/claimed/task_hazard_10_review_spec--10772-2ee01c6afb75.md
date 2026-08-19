# Codex Custom Subagents task handoff v1

Task: task_hazard_10_review_spec

## 目标

对隐患任务 10「隐患公示」提交 `e264815`（父 `25e3328`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`e264815`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.10、§11.2、§14、§16）。

## 审查清单（逐项核验并给出证据）

1. **企业内公示**：`GET /publicity`——列表字段（code/title/level/status 中文标签/rectification 摘要/source_type）；scope 口径（ongoing/closed/all，字典 publicity_scope 企业覆盖>系统默认、非法 422、字典缺失兜底三档）；created_at 倒序；权限读=归属 404。
2. **token 生成/重置**：`POST /publicity-token`——secrets.token_hex(32) 64 位、旧链接失效、返回 token+公开链接 `/h/{token}`；仅企业主/启用 admin（403）。
3. **公开脱敏页**：`GET /public/hazard/{token}`——token=enterprises.hazard_public_token、无效 404「链接已失效」；企业名脱敏（首字符+**）；白名单字段（code/title/level/status/rectification/source_type）不含责任人/联系方式/照片/位置/内部备注；masked 标记；generated_at。
4. **口径一致**：企业内与公开页共享同一 scope 函数；整改情况摘要三态（最近整改 content > 治理方案 goal > 未提交整改）。
5. **测试有效性**：18 个测试断言有效无空断言；覆盖 scope 过滤/权限 404/非法 422/token 重置/公开脱敏字段缺失/失效 token 404/generated_at。
6. **无越界**：`git show e264815 --stat` 恰 3 个清单文件（routers/hazard_management.py、routers/public_hazard.py、tests/test_hazard_publicity_api.py），消息精确匹配「feat(hazard): publicity page with desensitized public endpoint」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_publicity_api.py -v`（预期 18 passed）
- `python -m pytest tests/ -q`（预期 885 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check e264815`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_10_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患公示规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
