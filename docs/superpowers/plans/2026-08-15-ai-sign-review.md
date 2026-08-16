# AI 审查安全标志 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在风险告知卡标志生成链路中新增「AI 审查安全标志」：规则匹配后由 AI 结合风险点实际场景审查标志合理性，差异对比确认后保存快照（版本 +1）；同时提供人工微调（从 36 个国标标志库增删保存）。

**架构：** 后端在 `risk_notice_card_ai.py` 新增 `review_signs` 服务（复用 DeepSeek 通道），返回「建议删除/增加 + 理由」差异；新增无副作用端点 `POST /ai-review-signs`；快照 `content` 扩展 `signs`/`signs_source`（无 DB 迁移），`build_card_data` 快照优先用快照标志、否则回退规则 `match_signs`；前端预览页新增「AI 审查标志」按钮 + 差异对比 Modal + 人工微调编辑，全部保存走既有 `PUT /snapshot`。

**技术栈：** FastAPI + SQLAlchemy(async)、DeepSeek（llm_text_completion）、React 18 + Ant Design 5、Vitest、pytest。

**规格文档：** `docs/superpowers/specs/2026-08-15-ai-sign-review-design.md`（commit `eef9640`）

---

## 文件结构

### 后端（修改）

| 文件 | 职责 |
|------|------|
| `backend/app/services/risk_notice_card_ai.py` | 新增 `review_signs`：组装上下文 + 调 AI + 解析差异建议 |
| `backend/app/services/risk_notice_card_service.py` | `build_card_data` 支持快照 `signs`；新增 `normalize_signs`（非法丢弃/去重/排序/限量） |
| `backend/app/schemas/risk_notice_card.py` | 新增 `AiSignReviewResponse`/`Suggestion`；`SnapshotSaveRequest.content` 扩展 signs/signs_source |
| `backend/app/routers/risk_notice_card.py` | 新增 `POST /{object_id}/ai-review-signs`；快照端点 content 透传 signs |
| `backend/tests/test_risk_notice_card_service.py` | 快照 signs 优先 / 回退规则 / normalize_signs 测试 |
| `backend/tests/test_risk_notice_card_api.py` | ai-review-signs 端点测试 + 快照带 signs 测试 |

### 前端（修改）

| 文件 | 职责 |
|------|------|
| `frontend/src/types/riskNoticeCard.ts` | `SignSuggestion`/`AiSignReviewResponse` 类型；`SnapshotContent` 扩展 signs/signs_source |
| `frontend/src/services/riskNoticeCardService.ts` | `aiReviewSigns` 调用 |
| `frontend/src/services/riskNoticeCardService.test.ts` | 补 aiReviewSigns 用例 |
| `frontend/src/components/enterprise/RiskNoticeCard.tsx` | `signs_source` 来源 Tag；标志区编辑模式（候选网格勾选） |
| `frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx` | 「AI 审查标志」按钮 + 差异对比 Modal + 人工微调保存 |

---

## 任务 1：快照 content 扩展 + build_card_data 支持 signs

**文件：**
- 修改：`backend/app/services/risk_notice_card_service.py`
- 测试：`backend/tests/test_risk_notice_card_service.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_build_card_data_prefers_snapshot_signs():
    import asyncio
    from app.models.risk_management import RiskObject, RiskEvent, RiskMeasure
    from app.models.enterprise import Enterprise
    from app.schemas.risk_notice_card import CardData
    from app.services.risk_notice_card_service import build_card_data

    async def run():
        class FakeDB:
            async def execute(self, stmt):
                class R:
                    def scalars(self):
                        return self
                    def first(self):
                        return None
                return R()

        ent = Enterprise(name="测试公司", safety_officer="李四", safety_officer_phone="13900000000")
        obj = RiskObject(id="o1", name="会议室", category="工作场所")
        events = [RiskEvent(id="e1", accident_type="火灾", risk_level="较大",
                            trigger_conditions="线路老化", consequences="火灾",
                            method_type="LS", method_params={"l": 3, "s": 3})]
        # mock 快照：get_snapshot 返回 content 含 signs
        from unittest.mock import AsyncMock, MagicMock
        snap = MagicMock()
        snap.content = {
            "hazard_description": "x", "accident_types": ["火灾"],
            "control_measures": [], "emergency_measures": [],
            "signs": [{"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"}],
            "signs_source": "ai",
        }
        snap.version = 1
        snap.source = "ai"
        snap.updated_at = None
        db = AsyncMock()
        db.execute.return_value = MagicMock()
        db.execute.return_value.scalars.return_value.first.return_value = snap
        card = await build_card_data(db, ent, obj, [obj], events, [])
        assert card.signs[0].svg_name == "warning-fire"
        assert card.signs[0].name == "当心火灾"

    asyncio.run(run())
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py::test_build_card_data_prefers_snapshot_signs -v`
预期：FAIL（build_card_data 忽略快照 signs）

- [ ] **步骤 2：实现**

在 `risk_notice_card_service.py` 的 `build_card_data` 中：从快照 content 读取 `signs`，有则 `CardData(signs=...)`，无则保持 `match_signs(col.accident_types)`。注意快照 content 的 `signs` 为 dict 列表（CardData 校验时自动转 SignItem）。

```python
snapshot_signs = None
if snapshot and isinstance(snapshot.content, dict) and snapshot.content.get("signs"):
    snapshot_signs = snapshot.content["signs"]
...
signs = snapshot_signs if snapshot_signs is not None else match_signs(col.accident_types)
```

并在返回的 CardData 中透传 `snapshot_signs`（无快照时保持 match_signs 结果）。

- [ ] **步骤 3：运行测试验证通过**

`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v` 预期 PASS（新增 + 既有）

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): support snapshot signs in card data"
```

---

## 任务 2：normalize_signs 规范化函数

**文件：**
- 修改：`backend/app/services/risk_notice_card_service.py`
- 测试：`backend/tests/test_risk_notice_card_service.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_normalize_signs_filters_and_limits():
    from app.services.risk_notice_card_service import normalize_signs

    signs = [
        {"category": "notice", "name": "紧急出口", "svg_name": "notice-exit"},
        {"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"},
        {"category": "warning", "name": "当心爆炸", "svg_name": "warning-explosion"},
        {"category": "warning", "name": "当心触电", "svg_name": "warning-electric"},
        {"category": "prohibition", "name": "禁止烟火", "svg_name": "prohibition-smoking"},
        {"category": "instruction", "name": "必须戴安全帽", "svg_name": "instruction-helmet"},
        {"category": "instruction", "name": "必须戴防护手套", "svg_name": "instruction-gloves"},
        {"category": "instruction", "name": "必须穿绝缘鞋", "svg_name": "instruction-insulating-shoes"},
        {"category": "bogus", "name": "自造标志", "svg_name": "not-in-library"},
    ]
    out = normalize_signs(signs)
    names = [s["name"] for s in out]
    assert "自造标志" not in names           # 非法丢弃
    assert names[0] == "紧急出口"             # 排序前：先 notice？见下
    cats = [s["category"] for s in out]
    assert cats == sorted(cats, key=["warning", "prohibition", "instruction", "notice"].index)
    assert cats.count("instruction") <= 2     # 每类上限 2
    assert len(out) <= 8                      # 总数上限 8
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py::test_normalize_signs_filters_and_limits -v`
预期：FAIL（normalize_signs 不存在）

- [ ] **步骤 2：实现**

在 `risk_notice_card_service.py` 新增：

```python
VALID_SVG_NAMES = {s["svg_name"] for group in SIGN_GROUPS.values() for s in group}
VALID_SVG_NAMES |= {s["svg_name"] for s in DEFAULT_SIGN_GROUP}

def normalize_signs(
    signs: list[dict],
    max_per_category: int = 2,
    max_total: int = 8,
) -> list[dict]:
    """规范化 AI/人工提交的标志：过滤非法 svg_name、去重、按类别排序、限量。"""
    seen: set[str] = set()
    merged: list[dict] = []
    for s in signs or []:
        svg = s.get("svg_name")
        if svg not in VALID_SVG_NAMES or svg in seen:
            continue
        seen.add(svg)
        merged.append(s)
    ordered: list[dict] = []
    counts: dict[str, int] = {}
    for category in SIGN_CATEGORY_ORDER:
        for s in merged:
            if s.get("category") == category and counts.get(category, 0) < max_per_category:
                ordered.append(s)
                counts[category] = counts.get(category, 0) + 1
    return ordered[:max_total]
```

- [ ] **步骤 3：运行测试验证通过**

`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v` 预期 PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): add sign normalization helper"
```

---

## 任务 3：review_signs AI 服务

**文件：**
- 修改：`backend/app/services/risk_notice_card_ai.py`
- 测试：`backend/tests/test_risk_notice_card_api.py`（AI 路径 mock）

- [ ] **步骤 1：编写失败测试（mock llm_text_completion）**

```python
def test_review_signs_parses_suggestion(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from app.services import risk_notice_card_ai

    async def fake_completion(messages, config, timeout=60):
        return (
            '{"remove": ["instruction-helmet"], "add": ["warning-fall"], '
            '"reasons": [{"sign_name": "必须戴安全帽", "reason": "会议室为非生产区域"}, '
            '{"sign_name": "当心滑倒", "reason": "存在滑倒风险"}]}'
        )

    async def run():
        monkeypatch.setattr(risk_notice_card_ai, "llm_text_completion", fake_completion)
        db = AsyncMock()
        result = await risk_notice_card_ai.review_signs(
            db, "u1", "测试公司", "会议室", "工作场所", "三楼",
            [{"accident_type": "火灾"}, {"accident_type": "人员滑倒/摔伤"}],
            [{"category": "instruction", "name": "必须戴安全帽", "svg_name": "instruction-helmet"}],
            [{"category": "warning", "name": "当心滑倒", "svg_name": "warning-fall"}],
        )
        assert result["remove"] == ["instruction-helmet"]
        assert result["add"] == ["warning-fall"]
        assert len(result["reasons"]) == 2

    asyncio.run(run())
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_review_signs_parses_suggestion -v`
预期：FAIL（review_signs 不存在）

- [ ] **步骤 2：实现 review_signs**

在 `risk_notice_card_ai.py` 新增：

```python
async def review_signs(
    db: AsyncSession,
    user_id: str,
    enterprise_name: str,
    object_name: str,
    category: str | None,
    location: str | None,
    events: list[dict],
    current_signs: list[dict],
    catalog: list[dict],
) -> dict:
    """AI 审查安全标志：返回 {remove, add, reasons} 差异建议。"""
    ai_config = await _get_ai_config(user_id, db)
    events_text = "\n".join(
        f"- 事故类型：{e.get('accident_type', '')}；触发条件：{e.get('trigger_conditions', '') or ''}；"
        f"可能后果：{e.get('consequences', '') or ''}"
        for e in events
    )
    current_text = "、".join(f"{s['name']}({s['svg_name']})" for s in current_signs) or "（无）"
    catalog_text = "；".join(f"{s['name']}({s['svg_name']})" for s in catalog)
    prompt = (
        "你是安全生产专家，熟悉 GB 2894-2025《安全色和安全标志》与 GB 6441-1986 事故分类。"
        "请审查以下风险点告知卡的安全标志是否合理，输出严格 JSON："
        '{"remove": ["svg_name 列表（仅限当前标志中不合理的）"], "add": ["svg_name 列表（仅限候选库中应补充的）"], '
        '"reasons": [{"sign_name": "标志中文名", "reason": "具体理由"}]}。'
        f"企业：{enterprise_name}；风险点：{object_name}；类别：{category or '未知'}；位置：{location or '未知'}。\n"
        f"风险事件：\n{events_text or '（无）'}\n"
        f"当前标志：{current_text}\n"
        f"候选标志库（只能从这里选，不得发明）：{catalog_text}\n"
        "要求：remove 必须来自当前标志；add 必须来自候选库且不在当前标志；"
        "每类（警告/禁止/指令/提示）最多 2 个、总数不超过 8；理由结合具体场景；中文输出。"
    )
    messages = [
        {"role": "system", "content": "你是安全生产专家。"},
        {"role": "user", "content": prompt},
    ]
    raw = await llm_text_completion(messages, ai_config, timeout=60)
    try:
        data = _parse_optimized_json(raw)
    except json.JSONDecodeError:
        logger.warning("AI 审查标志 JSON 解析失败: raw=%s", raw[:200])
        raise HTTPException(502, "AI 返回格式异常，无法解析 JSON")
    remove = data.get("remove", []) if isinstance(data.get("remove"), list) else []
    add = data.get("add", []) if isinstance(data.get("add"), list) else []
    reasons = data.get("reasons", []) if isinstance(data.get("reasons"), list) else []
    return {"remove": remove, "add": add, "reasons": reasons}
```

- [ ] **步骤 3：运行测试验证通过**

`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_review_signs_parses_suggestion -v` 预期 PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/risk_notice_card_ai.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): add ai sign review service"
```

---

## 任务 4：schemas + ai-review-signs 端点

**文件：**
- 修改：`backend/app/schemas/risk_notice_card.py`
- 修改：`backend/app/routers/risk_notice_card.py`
- 测试：`backend/tests/test_risk_notice_card_api.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_ai_review_signs_endpoint_returns_suggestion(client, monkeypatch):
    from app.services import risk_notice_card_ai

    async def fake_review(*args, **kwargs):
        return {"remove": [], "add": ["warning-fall"], "reasons": [{"sign_name": "当心滑倒", "reason": "有滑倒风险"}]}

    monkeypatch.setattr(risk_notice_card_ai, "review_signs", fake_review)
    resp = client.post("/api/v1/enterprises/e1/risk-notice-cards/o1/ai-review-signs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["suggestion"]["add"] == ["warning-fall"]
    assert data["original_signs"] is not None
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_ai_review_signs_endpoint_returns_suggestion -v`
预期：FAIL（端点不存在 → 404/405）

- [ ] **步骤 2：schemas**

在 `risk_notice_card.py`（schemas）新增：

```python
class SignSuggestion(BaseModel):
    remove: list[str] = []
    add: list[str] = []
    reasons: list[dict] = []

class AiSignReviewResponse(BaseModel):
    original_signs: list[SignItem] = []
    suggestion: SignSuggestion
```

`SnapshotSaveRequest.content` 保持 dict（前端可带 signs/signs_source 键）。

- [ ] **步骤 3：端点实现**

在 `risk_notice_card.py`（router）新增：

```python
from app.schemas.risk_notice_card import AiSignReviewResponse, SignSuggestion
from app.services.risk_notice_card_ai import review_signs
from app.services.risk_notice_card_data import SIGN_GROUPS, DEFAULT_SIGN_GROUP

@router.post("/{object_id}/ai-review-signs", response_model=ApiResponse[AiSignReviewResponse])
async def ai_review_signs(
    enterprise_id: str,
    object_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    obj = (
        await db.execute(select(RiskObject).where(RiskObject.id == object_id, RiskObject.enterprise_id == enterprise_id))
    ).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "风险点不存在")
    events, measures = await load_events_and_measures(db, object_id)
    col = build_right_column(events, measures)
    current_signs = match_signs(col.accident_types)
    # 快照优先
    snapshot = await get_snapshot(db, object_id)
    if snapshot and isinstance(snapshot.content, dict) and snapshot.content.get("signs"):
        current_signs = snapshot.content["signs"]
    catalog = [
        {"category": s["category"], "name": s["name"], "svg_name": s["svg_name"]}
        for group in SIGN_GROUPS.values()
        for s in group
    ]
    catalog_keys = {s["svg_name"] for s in catalog}
    for s in DEFAULT_SIGN_GROUP:
        if s["svg_name"] not in catalog_keys:
            catalog.append(s)
    events_data = [
        {"accident_type": e.accident_type, "trigger_conditions": e.trigger_conditions, "consequences": e.consequences}
        for e in events
    ]
    try:
        suggestion = await review_signs(
            db, current_user.id, ent.name, obj.name, obj.category, obj.location,
            events_data, current_signs, catalog,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("AI 审查标志失败: enterprise=%s object=%s", enterprise_id, object_id)
        raise HTTPException(502, "AI 审查失败，请稍后重试或保留原版")
    return ApiResponse(data=AiSignReviewResponse(
        original_signs=current_signs,
        suggestion=SignSuggestion(**suggestion),
    ))
```

- [ ] **步骤 4：运行测试验证通过**

`cd backend && python -m pytest tests/test_risk_notice_card_api.py -v` 预期 PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/schemas/risk_notice_card.py backend/app/routers/risk_notice_card.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): add ai sign review endpoint"
```

---

## 任务 5：快照端点透传 signs（含人工微调）

**文件：**
- 修改：`backend/app/routers/risk_notice_card.py`
- 修改：`backend/app/services/risk_notice_card_service.py`（save_snapshot 规范化 signs）
- 测试：`backend/tests/test_risk_notice_card_api.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_snapshot_save_with_signs(client, monkeypatch):
    # PUT snapshot content 带 signs → save_snapshot 收到 content 含 signs
    resp = client.put("/api/v1/enterprises/e1/risk-notice-cards/o1/snapshot", json={
        "content": {
            "hazard_description": "x", "accident_types": ["火灾"],
            "control_measures": [], "emergency_measures": [],
            "signs": [{"category": "warning", "name": "当心火灾", "svg_name": "warning-fire"}],
            "signs_source": "manual",
        }
    })
    assert resp.status_code == 200
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_api.py::test_snapshot_save_with_signs -v`
预期：取决于现有 mock（若 save_snapshot 已透传 content 则 PASS；若 content 校验拒绝 signs 则 FAIL）

- [ ] **步骤 2：实现**

- `SnapshotSaveRequest.content` 若为 `RightColumn` 类型，需改为宽松 dict（允许 signs 键）或给 RightColumn 加 `signs`/`signs_source` 可选字段（推荐后者，保持类型）。
- `save_snapshot` 保存前对 `content.get("signs")` 调 `normalize_signs` 规范化；`signs_source` 限制为 `rule|ai|manual`（非法回退 `rule`）。

```python
if isinstance(content.get("signs"), list):
    content["signs"] = normalize_signs(content["signs"])
source = content.get("signs_source")
if source not in ("rule", "ai", "manual"):
    content["signs_source"] = "rule"
```

- [ ] **步骤 3：运行测试验证通过**

`cd backend && python -m pytest tests/test_risk_notice_card_api.py tests/test_risk_notice_card_service.py -v` 预期 PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/schemas/risk_notice_card.py backend/app/routers/risk_notice_card.py backend/app/services/risk_notice_card_service.py backend/tests/test_risk_notice_card_api.py
git commit -m "feat(risk-notice-card): persist signs in snapshot with normalization"
```

---

## 任务 6：前端类型 + service

**文件：**
- 修改：`frontend/src/types/riskNoticeCard.ts`
- 修改：`frontend/src/services/riskNoticeCardService.ts`
- 修改：`frontend/src/services/riskNoticeCardService.test.ts`

- [ ] **步骤 1：编写失败测试**

```typescript
it("aiReviewSigns posts and unpacks suggestion", async () => {
  vi.mock("@/services/api", () => ({ api: { post: vi.fn().mockResolvedValue({ data: { data: {
    original_signs: [],
    suggestion: { remove: [], add: ["warning-fall"], reasons: [{ sign_name: "当心滑倒", reason: "有滑倒风险" }] },
  } } }) } }));
  const result = await aiReviewSigns("e1", "o1");
  expect(result.suggestion.add).toContain("warning-fall");
});
```

运行：`cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts`
预期：FAIL（aiReviewSigns 不存在）

- [ ] **步骤 2：实现**

类型（`riskNoticeCard.ts`）：

```typescript
export interface SignSuggestion {
  remove: string[];
  add: string[];
  reasons: { sign_name: string; reason: string }[];
}

export interface AiSignReviewResponse {
  original_signs: SignItem[];
  suggestion: SignSuggestion;
}
```

service：

```typescript
export async function aiReviewSigns(enterpriseId: string, objectId: string): Promise<AiSignReviewResponse> {
  const res = await request(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}/ai-review-signs`, { method: "POST" });
  return res.data;
}
```

- [ ] **步骤 3：运行测试验证通过**

`cd frontend && npx vitest run src/services/riskNoticeCardService.test.ts` 预期 PASS

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/types/riskNoticeCard.ts frontend/src/services/riskNoticeCardService.ts frontend/src/services/riskNoticeCardService.test.ts
git commit -m "feat(risk-notice-card): add frontend sign review types and service"
```

---

## 任务 7：预览页「AI 审查标志」按钮 + 差异对比 Modal

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`

- [ ] **步骤 1：实现**

在预览页工具栏新增「AI 审查标志」按钮（`reviewing` loading 防重入）：

```tsx
const [reviewResult, setReviewResult] = useState<AiSignReviewResponse | null>(null);
const [reviewing, setReviewing] = useState(false);

const handleReviewSigns = async () => {
  setReviewing(true);
  try {
    setReviewResult(await aiReviewSigns(id, objectId));
  } catch {
    message.error("AI 审查失败，已保留原版");
  } finally {
    setReviewing(false);
  }
};
```

差异对比 Modal（AntD Modal）：

```tsx
<Modal open={!!reviewResult} title="AI 审查安全标志" onCancel={() => setReviewResult(null)} footer={null} width={640}>
  {reviewResult && (
    <>
      <div>建议增加（{reviewResult.suggestion.add.length}）</div>
      {reviewResult.suggestion.add.map((svg) => <div key={svg}>+ {svg}</div>)}
      <div>建议删除（{reviewResult.suggestion.remove.length}）</div>
      {reviewResult.suggestion.remove.map((svg) => <div key={svg}>✕ {svg}</div>)}
      <div>理由</div>
      {reviewResult.suggestion.reasons.map((r) => <div key={r.sign_name}>{r.sign_name}：{r.reason}</div>)}
      <Space>
        <Button onClick={() => setReviewResult(null)}>放弃，保留原版</Button>
        <Button type="primary" onClick={handleAdoptSigns}>采用建议并保存快照（版本 +1）</Button>
      </Space>
    </>
  )}
</Modal>
```

`handleAdoptSigns`：把 AI 建议应用到当前标志（remove 去掉、add 加入，normalize 后），组装完整 content（当前右栏 + 新 signs + signs_source=ai）→ `saveSnapshot(id, objectId, content)` → 提示 → refetch → 关闭 Modal。

- [ ] **步骤 2：门禁**

`cd frontend && npx tsc -b` 0 错误；`npx eslint src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx` 0 问题

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx
git commit -m "feat(risk-notice-card): add ai sign review compare modal"
```

---

## 任务 8：人工微调 + 来源 Tag

**文件：**
- 修改：`frontend/src/components/enterprise/RiskNoticeCard.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx`

- [ ] **步骤 1：来源 Tag**

`RiskNoticeCard` 标志区：`card.signs_source === "ai"` 显示「AI 审查」Tag、`"manual"` 显示「人工调整」；`CardData` 类型加 `signs_source?: "rule" | "ai" | "manual"`。

- [ ] **步骤 2：人工微调编辑模式**

预览页标志区加「编辑」入口 → 编辑 Modal：
- 当前已选标志列表（可移除）
- 候选库网格（从 `/signs/{svg_name}.svg` 渲染，勾选添加）
- 校验：每类 ≤2、总数 ≤8，超限即时提示
- 保存：组装完整 content（当前右栏 + 调整后 signs + signs_source=manual）→ `saveSnapshot` → refetch → 版本 +1

候选库数据：后端 `ai-review-signs` 响应不含全量 catalog——前端可硬编码从类型常量取（`SIGN_GROUPS` 前端没有）。方案：人工微调候选库用后端新增的轻量数据（在 `CardData` 或单独接口返回）——**简化**：本期人工微调候选库 = 当前标志可移除 + 从「AI 审查建议的 add」中选择 + 预置常用标志（当心火灾/当心滑倒/禁止烟火/紧急出口等 12 个常用）。如需完整 36 库，后续可加 catalog 接口。

> 实现注意：若需完整 36 库，可在 `ai-review-signs` 响应中一并返回 `catalog`（后端已有组装），前端复用。**推荐此方案**：`AiSignReviewResponse` 增加 `catalog: SignItem[]`，人工微调与 AI 审查共用候选库。

- [ ] **步骤 3：门禁**

`cd frontend && npx tsc -b` 0 错误；`npx eslint` 两文件 0 问题；`npx vitest run` 全绿

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/enterprise/RiskNoticeCard.tsx frontend/src/pages/Enterprise/RiskNoticeCardPreviewPage.tsx
git commit -m "feat(risk-notice-card): add manual sign editing and source tag"
```

---

## 任务 9：回归门禁 + 部署验证

**文件：** 无新增（视修复）

- [ ] **步骤 1：后端全量**

`cd backend && python -m pytest tests/ -q` 预期 418+ passed

- [ ] **步骤 2：前端全量**

`cd frontend && npx tsc -b && npx vitest run` 预期 0 错误、61+ 通过

- [ ] **步骤 3：手工冒烟**

本地起栈：预览页点「AI 审查标志」→ 差异对比 → 采用 → 版本 +1、标志更新；人工微调增删 → 保存 → 刷新保持；公开页显示快照标志与来源 Tag。

- [ ] **步骤 4：Commit（如有修复）+ 等待合并决策**

```bash
git add -A
git commit -m "chore(risk-notice-card): regression fixes"
```

按 finishing-a-development-branch 提供合并选项。

---

## 自检记录

**规格覆盖度：**
- §3 决策 1-5 → 任务 3/4/7/8 ✅
- §5 架构数据流 → 任务 1/4/7 ✅
- §6 快照 content 扩展 → 任务 1/5 ✅
- §7 API → 任务 4/5 ✅
- §8 AI 提示词与约束 → 任务 3（提示词）+ 2（规范化）✅
- §9 前端交互 → 任务 7/8 ✅
- §10 错误处理 → 任务 4（502/404）+ 7（前端提示）✅
- §11 测试计划 → 各任务 ✅

**占位符扫描：** 无 TODO/待定；任务 8 的「实现注意」为可选增强（推荐方案已明确）。

**类型一致性：** `AiSignReviewResponse`/`SignSuggestion`/`signs_source` 在 spec（§7）、schemas（任务 4）、前端类型（任务 6）、service（任务 1/2）间一致（`remove`/`add`/`reasons`/`svg_name`/`signs_source`）。
