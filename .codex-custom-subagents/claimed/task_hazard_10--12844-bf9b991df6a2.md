# Codex Custom Subagents task handoff v1

Task: task_hazard_10

## 目标

实现隐患管理任务 10「隐患公示（企业内 + 公开脱敏）」并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`25e3328`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：`backend/app/routers/hazard_management.py`（追加企业内公示 + token）、`backend/app/routers/public_hazard.py`（追加公开脱敏 GET）、新建 `backend/tests/test_hazard_publicity_api.py`。公开路由已挂载（任务 5），无需改 main.py。

**1. 企业内公示** `GET /publicity`（router 既有前缀 `/enterprises/{enterprise_id}/hazard-inspection`）

- 列表字段：编号（code）/标题（title）/等级（level，无则空）/状态（status 中文标签，复用字典 record_status_label 或映射表，报告取舍）/整改情况（rectification 摘要：最近整改记录 content 或治理方案目标摘要，未整改显示「未提交整改」）/排查来源（source_type 标签，可选）。
- 口径过滤：query `scope`（ongoing/closed/all，来自字典 `publicity_scope`，默认 all）；ongoing=status != closed、closed=status == closed；scope 非法 422；企业可覆盖字典（企业配置优先级）。
- 排序：按 created_at 倒序；分页或全量按既有惯例（报告说明）。
- 权限：读=归属（企业主/启用成员，404）。

**2. token 生成/重置** `POST /publicity-token`

- 生成/重置 `enterprises.hazard_public_token`（UUID/随机 64 位，报告生成方式）；首次生成与重置统一端点；返回 token 与完整公开链接（`/h/{token}`）。
- 权限：仅企业主/启用 enterprise_admin（403）。

**3. 公开脱敏页** `GET /public/hazard/{token}`（免登录）

- token = `enterprises.hazard_public_token`；无效 → 404「链接已失效」。
- 响应：企业名称（脱敏——如首字符+**，报告规则）、公示列表（编号/标题/等级/状态/整改情况摘要）；**不含**责任人/联系方式/照片/位置/内部备注（脱敏，规格 §11.2）。
- 口径：与企业内公示一致（ongoing/closed/all 默认 all，可经 query 传 scope 或固定全部——报告取舍，规格默认全部）。
- 响应含 `generated_at`（企业 token 生成时间或当前时间，报告取舍）与 `masked` 标记。

**4. 测试**（`backend/tests/test_hazard_publicity_api.py`，mock db 风格与既有一致，async 带 `@pytest.mark.asyncio`）

- 企业内列表（scope 过滤/字段含整改情况/权限 404/非法 scope 422/字典企业覆盖）；token 生成重置（403/返回值含 token 与链接）；公开页（脱敏字段不出现、404 失效 token、generated_at、scope 过滤）。
- 断言有效无空断言；提交前跑目标测试 + 全量回归。

**5. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §5.10（publicity_scope 字典）、§11.2、§14、§16。
- 模型：`backend/app/models/enterprise.py`（hazard_public_token）、`backend/app/models/hazard_management.py`（HazardRecord/HazardRectification）。
- 既有：`backend/app/routers/hazard_management.py`（_get_ent/_get_admin_ent/ApiResponse）、`backend/app/routers/public_hazard.py`（扫码上报路由）、`backend/app/services/risk_notice_card_service.py`（脱敏先例）、`backend/tests/test_hazard_record_api.py`（mock 风格）。
- 数据字典：`get_dict_map`（publicity_scope/record_status_label）。

## 验证

- `python -m pytest tests/test_hazard_publicity_api.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/routers/hazard_management.py backend/app/routers/public_hazard.py backend/tests/test_hazard_publicity_api.py
git commit -m "feat(hazard): publicity page with desensitized public endpoint"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_10 --claim-id <claim_id> --exit-code 0 --summary "隐患公示实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（scope 口径/token 生成/脱敏规则/整改情况摘要）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
