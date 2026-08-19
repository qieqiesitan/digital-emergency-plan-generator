# Codex Custom Subagents task handoff v1

Task: task_hazard_05_review_spec

## 目标

对隐患任务 5「隐患登记三渠道+AI 摘要分类」提交 `e924dd3`（父 `b1bc6b2`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`e924dd3`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.4、§8、§14、§16）。

## 审查清单（逐项核验并给出证据）

1. **Web 登记契约**：`POST /records`——source_type 枚举校验、hazard_type 数据字典码值校验（equipment/fire/behavior/management/environment/other）、object_id/measure_id 企业归属校验 422、title/description 必填、photo_urls/location 校验；创建后 status=registered、created_by=当前用户、code=HD-{三位序号}；权限=企业主/启用管理员/启用成员（读归属 404、非成员 404）。
2. **AI 摘要分类契约**：`POST /ai/record-assist`——description 必填；返回 {available, title, hazard_type, suggested_level, reason, note}；suggested_level=一般/重大（与 records.level 值域一致）；失败/未配置/返回不合法 → available:false（200 降级）；仅文本不读照片。
3. **扫码公开契约**：`POST /public/hazard/report/{token}`——先 risk_objects.public_token（自动带 object_id、企业由风险点归属推导、location 可选）再 enterprises.hazard_report_token（企业通用、object_id 空、location 缺失 422），均无 404；nonce 必填、内存 TTL 5 分钟、重复 409、成功落库后写入缓存；落库 source_type=report、created_by=NULL、status=registered；响应不暴露内部信息。
4. **路由挂载**：main.py 最小挂载（与 public_risk 同型）；§14 接口 `/public/hazard/report/{token}` 一致；全部响应走 ApiResponse 信封。
5. **移动端**：复用 POST /records（source_type=report/manual）无新端点。
6. **测试有效性**：45 个测试断言有效无空断言；覆盖三渠道/nonce 幂等/token 404/AI 摘要 mock/hazard_type 字典校验/权限。
7. **无越界**：`git show e924dd3 --stat` 恰 6 个清单文件（main.py、routers/hazard_management.py、routers/public_hazard.py、services/hazard_ai_service.py、tests/test_hazard_record_api.py、tests/test_hazard_public_api.py），消息精确匹配「feat(hazard): record registration via web, qr and mobile with AI assist」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_record_api.py tests/test_hazard_public_api.py -v`（预期 45 passed）
- `python -m pytest tests/ -q`（预期 766 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check e924dd3`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_05_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患登记三渠道规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
