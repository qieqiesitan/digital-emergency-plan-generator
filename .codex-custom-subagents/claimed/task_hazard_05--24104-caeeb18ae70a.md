# Codex Custom Subagents task handoff v1

Task: task_hazard_05

## 目标

实现隐患管理任务 5「隐患登记（三渠道）+ AI 摘要分类」并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`b1bc6b2`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：`backend/app/routers/hazard_management.py`（追加）、新建 `backend/app/routers/public_hazard.py`、`backend/app/services/hazard_ai_service.py`（追加 record-assist）、新建 `backend/tests/test_hazard_record_api.py`、新建 `backend/tests/test_hazard_public_api.py`。公开路由需在 `backend/app/main.py` 挂载（若与既有 public_risk 挂载同型，最小改动并说明）。

**1. Web 登记** `POST /records`（router 既有前缀 `/enterprises/{enterprise_id}/hazard-inspection`）

- body：source_type（inspection/report/regulatory/accident/manual 枚举校验）、hazard_type（可选，须来自数据字典 `hazard_type` 码值 equipment/fire/behavior/management/environment/other，字典校验失败 422）、object_id/measure_id（可选，校验属于该企业，否则 422）、title（必填 255 内）、description（必填）、photo_urls（可选数组）、location（可选 500 内）、source_task_id/source_item_id（可选，回填校验属于该企业任务）。
- 创建后 status=registered、created_by=当前用户、code=`HD-{三位序号}`（复用 `hazard_service.next_hazard_code`）。
- 权限：写=企业主/启用管理员/启用成员（隐患登记面向全员，参照任务 3 权限分层，读=归属 404）；说明角色取舍。
- 全部响应走 ApiResponse 信封。

**2. AI 摘要分类** `POST /ai/record-assist`（router 既有前缀下）

- body：`{description}`（必填非空；可带可选 object_id/measure_id 上下文）；返回 `{available, title, hazard_type, suggested_level, reason, note}`；suggested_level 用 一般/重大 中文或 general/major 码值（选一种，报告说明）。
- 服务函数放 `hazard_ai_service.py`：遵循既有 AI 惯例（llm_text_completion timeout=60、_parse_ai_json、get_system_ai_config）；prompt 要求返回 title（≤255 中文摘要）、hazard_type（字典码值之一）、suggested_level、reason；任何失败/未配置 → available:false 降级（200，§16）。
- 仅文本处理，不读照片（§8）。

**3. 扫码公开上报** 新建 `backend/app/routers/public_hazard.py`，免登录

- `POST /public/hazard/report/{token}`：token 匹配优先级——先查 `risk_objects.public_token`（自动带 object_id，enterprise 由风险点归属推导）；再查 `enterprises.hazard_report_token`（企业通用二维码，object_id 可空，location 必填或可空——报告说明取舍）；均无 → 404。
- body：title（可选，默认由描述截断或「扫码上报隐患」）、description（必填）、photo_urls（可选）、location（可选，企业通用 token 时建议必填 422，说明取舍）、nonce（必填）。
- **nonce 防重**：前端生成 nonce，后端内存缓存 5 分钟（TTL 键 `hazard_report:{nonce}`），已存在 → 409「请勿重复提交」；成功提交后写入缓存；缓存过期自动清理（可用简单 dict + 时间戳惰性清理或 expire 记录，报告说明实现）。
- 落库：source_type=report、created_by=NULL、status=registered、code=HD-{三位序号}；token 失效/不存在 → 404。
- 响应不暴露内部信息（§8「已提交，待企业管理员确认」风格）。

**4. 移动端**：复用 `POST /records`（source_type=report/manual），无需新端点（前端接入后续任务）。

**5. 测试**

- `tests/test_hazard_record_api.py`：登记成功（各 source_type）/字段校验 422/hazard_type 字典校验/object/measure 归属 422/权限 403/404/AI record-assist 成功与降级。
- `tests/test_hazard_public_api.py`：风险点 token 上报（object_id 自动带）/企业 token 上报（location 逻辑）/token 404/nonce 重复 409/nonce 缺失 422/created_by NULL/source_type=report。
- mock db 风格与既有测试一致；async 测试带 `@pytest.mark.asyncio`；断言有效无空断言；提交前跑目标测试 + 全量回归。

**6. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §5.4、§8、§14、§16。
- 模型：`backend/app/models/hazard_management.py`（HazardRecord）、`backend/app/models/enterprise.py`（hazard_report_token）、风险点模型（risk_objects.public_token 与 enterprise 归属，查 risk_management 模型）。
- 既有惯例：`backend/app/routers/public_risk.py`（免登录 token 端点）、`backend/app/routers/risk_management.py`、`backend/app/routers/hazard_management.py`（_get_ent/_get_admin_ent/ApiResponse/next_hazard_code）、`backend/app/services/hazard_ai_service.py`（模板 AI 服务）、`backend/tests/test_hazard_plan_api.py`（mock db 风格）。
- 数据字典：`data_dicts` 表/`data_dict_service` 查询 hazard_type 码值的方式（A 阶段已实现）。

## 验证

- `python -m pytest tests/test_hazard_record_api.py tests/test_hazard_public_api.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/routers/hazard_management.py backend/app/routers/public_hazard.py backend/app/services/hazard_ai_service.py backend/tests/test_hazard_record_api.py backend/tests/test_hazard_public_api.py
git commit -m "feat(hazard): record registration via web, qr and mobile with AI assist"
```

若确需挂载公开路由的最小改动（main.py），一并 add 并在报告中说明；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_05 --claim-id <claim_id> --exit-code 0 --summary "隐患登记三渠道+AI摘要分类实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（token 匹配优先级/nonce 实现/权限/location 取舍/AI 降级）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
