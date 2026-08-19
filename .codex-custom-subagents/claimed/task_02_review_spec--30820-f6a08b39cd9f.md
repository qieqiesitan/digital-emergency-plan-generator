# Codex Custom Subagents task handoff v1

Task: task_02_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 2 的实现做**只读规格合规审查**，对照 A 规格 §5.4 与实现计划任务 2，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交范围：`b0a1020`（feat，父 bf61245）+ `15b63e5`（fix，父 b0a1020）
- 文件：
  - `backend/app/services/data_dict_service.py`
  - `backend/app/schemas/data_dict.py`
  - `backend/app/routers/data_dicts.py`
  - `backend/app/main.py`
  - `backend/tests/test_data_dict.py`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §5.4（工作树内）
- 计划：`docs/superpowers/plans/2026-08-14-risk-control-enhancement.md` 任务 2（工作树内为旧版，以本任务文件描述为准：mock 风格测试、本地 `_get_enterprise` 辅助函数）

## 审查要点

1. 合并语义：`get_dict_map` 企业条目 > 系统默认、同 code 覆盖、enabled 过滤、60s 缓存、`invalidate_dict_cache` 按企业/类型失效——与规格 §5.4「合并与生效规则」一致；
2. 接口：系统 `GET/POST/PUT /settings/data-dicts`、企业 `GET/POST/PUT/DELETE /enterprises/{id}/data-dicts` 与计划一致；409 重复、404 不存在/非本企业、企业归属校验（本地 `_get_enterprise`）；
3. schema：Create/Update 字段与计划一致，`model_dump(exclude_unset=True)` 正确用于更新；
4. 路由注册：`main.py` 已注册 `data_dicts.router`（prefix `/api/v1`）；
5. 测试：4 个合并/过滤用例 + 反序用例共 5 个，符合项目 mock 风格、`@pytest.mark.asyncio`、缓存清理，覆盖企业>系统语义；
6. 无越界改动：提交仅含任务 2 列出的文件。

## 输出格式

- 结论：✅ 符合规格（无必须修复项）/ ❌ 需修复
- 问题清单：每条标注 **必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_02_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务2规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
