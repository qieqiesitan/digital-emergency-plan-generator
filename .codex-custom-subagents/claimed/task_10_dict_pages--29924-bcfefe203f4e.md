# Codex Custom Subagents task handoff v1

Task: task_10_dict_pages

## 目标

实现「风险分级管控增强（A 阶段）」任务 10：风险告知卡双等级展示 + 数据字典管理页（系统级 + 企业覆盖），按门禁完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=当前 `73ca31c`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景

- 任务 2 已提供字典接口：`GET/POST/PUT /settings/data-dicts`（系统）、`GET/POST/PUT/DELETE /enterprises/{id}/data-dicts`（企业覆盖，GET 返回系统+企业合并视图）；
- 任务 3 已给 RiskEvent 加 inherent_risk_level；任务 6 已有 max_risk_level(mode)；
- 风险告知卡：后端 `backend/app/services/risk_notice_card_service.py` 组装 CardData、`backend/app/schemas/risk_notice_card.py` 定义 CardData、快照存 `risk_notice_cards.content` JSONB；
- 路由实际在 `frontend/src/routes/index.tsx`（App.tsx 只调 createRouter，任务 9 已确认）；
- 前端约定：vitest 仅 service/utils；组件靠 tsc/lint + 手工冒烟（任务 12）。

## 文件

- 后端（告知卡双等级，小改）：
  - 修改：`backend/app/schemas/risk_notice_card.py`（CardData 增加 `inherent_risk_level: str | None = None`）
  - 修改：`backend/app/services/risk_notice_card_service.py`（组装时按事件 `inherent_risk_level` 取最大固有等级填入；快照读取时缺字段回退 None）
  - 修改：`backend/tests/test_risk_notice_card_service.py`（补固有等级断言；若既有测试结构合适则追加用例）
- 前端：
  - 修改：`frontend/src/components/enterprise/RiskNoticeCard.tsx`（等级色带区显示「现有风险：{level}（固有 {inherent}）」，inherent 缺失时不显示括号）
  - 修改：`frontend/src/types/riskNoticeCard.ts`（CardData 加 `inherent_risk_level?: string | null`）
  - 创建：`frontend/src/types/dataDict.ts`
  - 创建：`frontend/src/services/dataDictService.ts`
  - 创建：`frontend/src/services/dataDictService.test.ts`（URL 断言）
  - 创建：`frontend/src/pages/Settings/DataDictManagePage.tsx`
  - 创建：`frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx`
  - 修改：`frontend/src/routes/index.tsx`（两个新路由）
  - 修改：`frontend/src/layouts/AuthLayout.tsx`（系统菜单加「数据字典管理」；按现有权限模式）
  - 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`（加「风险与隐患配置」按钮跳企业字典页）

## 步骤

- [ ] **步骤 1：告知卡双等级（后端小改）**

`CardData` schema 加 `inherent_risk_level`；组装服务在现有「取最大现有等级」逻辑旁同步取最大固有等级（遍历对象/单元事件，`inherent_risk_level` 按 `RISK_LEVEL_ORDER` 取最大；无则 None）。快照 content 无该字段时回退 None（前端隐藏括号）。补后端测试。

- [ ] **步骤 2：告知卡双等级（前端）**

`RiskNoticeCard.tsx` 等级色带区域（标题或色带下方）显示：`现有风险：{level}`，有 inherent 时追加 `（固有 {inherent}）`；快照/预览/公开页共用组件自动生效。

- [ ] **步骤 3：字典类型与 service**

`frontend/src/types/dataDict.ts`：

```typescript
export interface DataDictItem { id: string; dict_type: string; code: string; label: string;
  value: Record<string, unknown>; scope: "system" | "enterprise"; enterprise_id: string | null;
  sort_order: number; enabled: boolean; is_system: boolean; description?: string | null; }
export interface DataDictPayload { dict_type: string; code: string; label: string;
  value: Record<string, unknown>; sort_order?: number; enabled?: boolean; description?: string | null; }
```

`dataDictService.ts`（按文件惯例箭头函数 + `.then(r => r.data.data)` 解包）：

```typescript
export const listSystemDicts = (dictType?: string) => api.get("/settings/data-dicts", { params: { dict_type: dictType } }).then(r => r.data.data);
export const createSystemDict = (payload: DataDictPayload) => api.post("/settings/data-dicts", payload).then(r => r.data.data);
export const updateSystemDict = (id: string, patch: Partial<DataDictPayload>) => api.put(`/settings/data-dicts/${id}`, patch).then(r => r.data.data);
export const listEnterpriseDicts = (enterpriseId: string, dictType?: string) => api.get(`/enterprises/${enterpriseId}/data-dicts`, { params: { dict_type: dictType } }).then(r => r.data.data);
export const createEnterpriseDict = (enterpriseId: string, payload: DataDictPayload) => api.post(`/enterprises/${enterpriseId}/data-dicts`, payload).then(r => r.data.data);
export const updateEnterpriseDict = (enterpriseId: string, id: string, patch: Partial<DataDictPayload>) => api.put(`/enterprises/${enterpriseId}/data-dicts/${id}`, patch).then(r => r.data.data);
export const deleteEnterpriseDict = (enterpriseId: string, id: string) => api.delete(`/enterprises/${enterpriseId}/data-dicts/${id}`).then(r => r.data.data);
```

补 service 测试（URL + 参数断言）。

- [ ] **步骤 4：系统字典管理页**（`DataDictManagePage.tsx`）

- 左侧 dict_type 分组（从种子/响应去重：measure_factors / control_level_map / hazard_type 等）；
- 主区 Table：code/label/value（JSON 展示）/enabled/sort_order/description + 编辑/新增 Drawer（value 用 JSON 文本域，提交前 `JSON.parse` 校验，非法 422 提示）；删除（系统条目支持删除则提供，否则禁用并说明）；
- 变更后 invalidate/refetch query；顶部返回。

- [ ] **步骤 5：企业字典覆盖页**（`EnterpriseDictConfigPage.tsx`）

- 读取 `listEnterpriseDicts`（系统+企业合并视图）；按 dict_type 分组展示；
- 系统条目（scope=system）显示「系统默认」Tag + 「覆盖」按钮（调用 `createEnterpriseDict` 复制同 code 为 enterprise scope，可再编辑）；
- 企业条目（scope=enterprise）可编辑（`updateEnterpriseDict`）/删除（`deleteEnterpriseDict`，恢复系统默认）；
- value 用 JSON 文本域 + JSON.parse 校验；变更后 refetch；
- 入口：`RiskManagementTab.tsx` 加「风险与隐患配置」按钮跳转；路由 `/enterprises/:id/data-dicts`（ProtectedRoute 内）。

- [ ] **步骤 6：系统菜单与路由**

- `AuthLayout.tsx` 系统设置菜单加「数据字典管理」（按现有菜单/权限模式）；
- `routes/index.tsx`：`/settings/data-dicts`（ProtectedRoute 内）、`/enterprises/:id/data-dicts`。

- [ ] **步骤 7：门禁**

后端：`python -m pytest tests/test_risk_notice_card_service.py tests/test_risk_notice_card_data.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归。
前端：`npx tsc -b`、eslint（改动文件）、`npx vitest run` 全部通过；`git diff --check` 干净。

- [ ] **步骤 8：Commit（可分两个）**

```bash
git add backend/app/schemas/risk_notice_card.py backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_service.py frontend/src/types/riskNoticeCard.ts frontend/src/components/enterprise/RiskNoticeCard.tsx
git commit -m "feat(risk): show inherent level on risk notice card"

git add frontend/src/types/dataDict.ts frontend/src/services/dataDictService.ts frontend/src/services/dataDictService.test.ts frontend/src/pages/Settings/DataDictManagePage.tsx frontend/src/pages/Enterprise/EnterpriseDictConfigPage.tsx frontend/src/routes/index.tsx frontend/src/layouts/AuthLayout.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx
git commit -m "feat(data-dict): system and enterprise dict management pages"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_10_dict_pages --claim-id <claim_id> --exit-code 0 --summary "告知卡双等级+字典管理页完成"
```

最终回复报告：task_id、claim_id、commit SHA（两个）、测试/门禁结果、自审结论。

## 规则

- 用 `apply_patch` 编辑；只改上述文件（如需额外文件请说明理由）；阻塞时停下汇报。
