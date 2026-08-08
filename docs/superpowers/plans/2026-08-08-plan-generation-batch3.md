# 预案生成增强 第 3 批（质量与体验）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现生成后内容级质量校验、失败章节一键重试、移动端批量生成接入统一后端链路（含 `generate_batch` 与 `generate_batch_background` 去重）、AI 生成前后 Diff 对比弹窗。

**架构：** 新增 `plan_quality_service.py` 提供 `check_plan`，`export.py::validate_plan_export` 改为调用它（响应结构兼容）；`generation.py` 抽取 `_run_batch_generation` 公共函数，两个批量端点共用并收集 `failed_sections`，新增 `GET /plans/{id}/generate/status`；前端桌面端加 Diff 弹窗与重试入口，移动端批量改走后台接口。

**技术栈：** FastAPI + SQLAlchemy async；React + TypeScript + Antd；pytest / vitest。

**规格：** `docs/superpowers/specs/2026-08-08-plan-generation-enhancement-design.md` 第 3.5-3.8 节

---

## 文件结构

**后端：**
- 新增 `backend/app/services/plan_quality_service.py`
- 修改 `backend/app/routers/export.py` — validate 接入 check_plan
- 修改 `backend/app/routers/generation.py` — `_run_batch_generation` 抽取、failed_sections、generate/status 端点、快照扩展（若批 2 未合入）
- 修改 `backend/app/routers/versions.py` — 快照扩展（若批 2 未合入）
- 新增 `backend/tests/test_plan_quality.py`
- 新增 `backend/tests/test_generation_batch_refactor.py`

**前端：**
- 修改 `frontend/src/types/plan.ts` — SSEEvent 加 failed_sections
- 修改 `frontend/src/pages/Plan/PlanEditorPage.tsx` — 失败重试入口
- 修改 `frontend/src/pages/Plan/ExportPreviewPage.tsx` — 质量报告展示
- 新增 `frontend/src/components/plan/DiffPreviewModal.tsx`
- 修改 `frontend/src/components/plan/AIGenerateButton.tsx` — Diff 集成
- 修改 `frontend/src/mobile/screens/PlanEditorScreen.tsx` — 批量生成接入
- 修改 `frontend/src/services/generationService.ts` — generateBatchBackground 返回 failed_sections

---

### 任务 1：plan_quality_service 质量校验服务

**文件：**
- 新增：`backend/app/services/plan_quality_service.py`
- 新增：`backend/tests/test_plan_quality.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_plan_quality.py
from unittest.mock import MagicMock
from app.services.plan_quality_service import check_plan


def _section(key, title, content):
    s = MagicMock()
    s.section_key = key
    s.title = title
    s.content = content
    return s


def test_empty_required_section_is_issue():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_1", "总则", "")])
    assert result["valid"] is False
    assert any(i["section_key"] == "sec_1" and "空" in i["issue"] for i in result["issues"])


def test_placeholder_residue_is_warning():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_2", "风险描述", "<p>地址（待补充）</p>")])
    assert any("待补充" in w["warning"] for w in result["warnings"])


def test_suspected_inferred_address_warning():
    enterprise = MagicMock(address="（待补充）", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_2", "风险描述", "<p>事故发生在湖北省武汉市某街道</p>")])
    assert any("推断" in w["warning"] for w in result["warnings"])


def test_clean_plan_no_issues():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [
        _section("sec_1", "总则", "<p>企业地址：西安市高新区一路1号，法人：张三</p>"),
    ])
    assert result["valid"] is True
    assert result["issues"] == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_quality.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.plan_quality_service'`

- [ ] **步骤 3：实现服务**

```python
# backend/app/services/plan_quality_service.py
"""预案内容质量校验：导出前检查占位符残留、档案一致性、章节完整性、疑似推断。"""
import re


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def _suspected_address(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fa5]{2,8}(?:省|市|区|县).{0,8}(?:路|街|大道)", text))


def check_plan(plan, enterprise, sections) -> dict:
    issues = []
    warnings = []

    for s in sections:
        if not s.content or not s.content.strip():
            issues.append({
                "section_key": s.section_key,
                "section_title": s.title,
                "issue": "章节内容为空",
            })
            continue
        text = _strip_html(s.content)
        if "（待补充）" in text:
            warnings.append({
                "section_key": s.section_key,
                "section_title": s.title,
                "warning": "存在待补充占位符，请人工补全",
            })

        # 关键档案信息未体现（非空时正文应包含）
        for field, label in [
            (getattr(enterprise, "address", None), "地址"),
            (getattr(enterprise, "legal_representative", None), "法定代表人"),
            (getattr(enterprise, "safety_officer", None), "安全负责人"),
        ]:
            if field and field not in ("（待补充）",) and field not in text:
                warnings.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "warning": f"正文未体现企业档案{label}：{field}",
                })

        # 档案缺失时正文出现疑似地址 → 可能是推断
        if getattr(enterprise, "address", None) in (None, "", "（待补充）") and _suspected_address(text):
            warnings.append({
                "section_key": s.section_key,
                "section_title": s.title,
                "warning": "疑似推断地址，请核实",
            })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_plan_quality.py -v`
预期：PASS（4 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_quality_service.py backend/tests/test_plan_quality.py
git commit -m "feat(plan): add content quality check service (batch3)"
```

---

### 任务 2：validate 接口接入 check_plan + 前端质量报告

**文件：**
- 修改：`backend/app/routers/export.py:306-341`（validate_plan_export）
- 修改：`frontend/src/pages/Plan/ExportPreviewPage.tsx`

- [ ] **步骤 1：修改 validate_plan_export**

```python
# backend/app/routers/export.py  validate_plan_export 函数体替换为：
    from app.services.plan_quality_service import check_plan
    result = check_plan(plan, enterprise, sections)
    # 兼容既有响应：warnings 为字符串列表
    warnings = [
        f"「{w['section_title']}」{w['warning']}"
        for w in result["warnings"]
    ]
    return ApiResponse(data={
        "valid": result["valid"],
        "issues": result["issues"],
        "warnings": warnings,
    })
```

注意：`validate_plan_export` 需要先查询 `enterprise`（参考 `export_plan_docx` 的查询方式）。

- [ ] **步骤 2：前端展示质量报告**

```typescript
// frontend/src/pages/Plan/ExportPreviewPage.tsx  新增查询与渲染：
  const { data: validation } = useQuery({
    queryKey: ["exportValidate", id],
    queryFn: () => validateExport(id!),
    enabled: !!id,
  });

// 顶部（预览容器上方）渲染：
        {validation && !validation.valid && (
          <Alert
            type="error"
            showIcon
            message="导出前请修复以下问题"
            description={
              <ul>
                {validation.issues.map((i, idx) => (
                  <li key={idx}>「{i.section_title}」{i.issue}</li>
                ))}
              </ul>
            }
            action={<Button onClick={() => navigate(`/plans/${id}/edit`)}>去编辑</Button>}
          />
        )}
        {validation && validation.warnings.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message="质量提示"
            description={
              <ul>
                {validation.warnings.map((w, idx) => <li key={idx}>{w}</li>)}
              </ul>
            }
            style={{ marginTop: 8 }}
          />
        )}
```

需从 `@/services/exportService` 导入 `validateExport`，从 `antd` 导入 `Alert`。

- [ ] **步骤 3：类型检查与测试**

运行：`cd frontend && npx tsc -b`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/routers/export.py frontend/src/pages/Plan/ExportPreviewPage.tsx
git commit -m "feat(plan): surface quality report in export preview (batch3)"
```

---

### 任务 3：批量生成公共函数抽取 + failed_sections + status 端点

**文件：**
- 修改：`backend/app/routers/generation.py`
- 新增：`backend/tests/test_generation_batch_refactor.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_generation_batch_refactor.py
from unittest.mock import MagicMock, AsyncMock
import pytest


@pytest.mark.asyncio
async def test_run_batch_generation_collects_failures():
    from app.routers.generation import _run_batch_generation

    bg_db = MagicMock()
    ai_config = MagicMock()
    ent_data = {}

    calls = {"n": 0}

    async def fake_stream(prompt, cfg, plan_type, style=None, advanced=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return "<p>ok</p>"

    result = await _run_batch_generation(
        bg_db=bg_db,
        plan_id="p1",
        section_tuples=[("sec_1", "总则"), ("sec_2", "风险")],
        ai_config=ai_config,
        ent_data=ent_data,
        plan_type="comprehensive",
        style_preference=None,
        advanced_overrides=None,
        stream_fn=fake_stream,
    )
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["failed_sections"] == [{"section_key": "sec_1", "title": "总则"}]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_generation_batch_refactor.py -v`
预期：FAIL，`ImportError: cannot import name '_run_batch_generation'`

- [ ] **步骤 3：实现公共批量函数**

```python
# backend/app/routers/generation.py  模块级新增（位于两个批量端点之前）：
async def _run_batch_generation(
    *,
    bg_db,
    plan_id: str,
    section_tuples: list,
    ai_config,
    ent_data: dict,
    plan_type: str,
    accident_type: str | None = None,
    style_preference=None,
    advanced_overrides=None,
    stream_fn=None,
    on_progress=None,
) -> dict:
    """批量生成公共实现：逐章生成、写库、渲染 Mermaid、统计失败。

    stream_fn: async 函数 (prompt, ai_config, plan_type, style_preference, advanced_overrides) -> str；
    为 None 时使用 _stream_llm。
    """
    completed = 0
    failed = 0
    failed_sections = []

    bg_sections = (await bg_db.execute(
        select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
    )).scalars().all()
    bg_section_map = {s.section_key: s for s in bg_sections}

    for i, (section_key, section_title) in enumerate(section_tuples):
        if on_progress:
            await on_progress(section_key, section_title, i)
        s = bg_section_map.get(section_key)
        if not s:
            continue
        try:
            prompt_text = _build_section_prompt(
                section_title, ent_data, section_number=i + 1,
                section_key=section_key, plan_type=plan_type,
                accident_type=accident_type, diagram_preference="mermaid",
            )
            if stream_fn is None:
                full = await _stream_llm(prompt_text, ai_config, plan_type, style_preference, advanced_overrides)
            else:
                full = await stream_fn(prompt_text, ai_config, plan_type, style_preference, advanced_overrides)
            s.content = md_to_html(full, normalize=True)
            s.ai_generated = True
            s.mermaid_svgs = await _pre_render_mermaid_svgs(full)
            await bg_db.commit()
            completed += 1
        except Exception as e:
            logger.error(f"Section {section_key} failed: {e}")
            failed += 1
            failed_sections.append({"section_key": section_key, "title": section_title})

    return {"completed": completed, "failed": failed, "failed_sections": failed_sections}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && .venv/Scripts/python -m pytest tests/test_generation_batch_refactor.py -v`
预期：PASS（1 passed）

- [ ] **步骤 5：重构 `generate_batch` 与 `generate_batch_background` 调用公共函数**

```python
# generate_batch 的 run_background 内，将逐章循环替换为：
                result = await _run_batch_generation(
                    bg_db=bg_db, plan_id=plan_id, section_tuples=section_tuples,
                    ai_config=ai_config, ent_data=ent_data,
                    plan_type=p.plan_type, accident_type=p.accident_type,
                    style_preference=p.style_preference,
                    advanced_overrides=p.advanced_prompt_overrides,
                    stream_fn=_stream_llm,
                    on_progress=on_progress,
                )
                completed, failed = result["completed"], result["failed"]
                failed_sections = result["failed_sections"]
```

`generate_batch_background` 的调用同样传 `accident_type=p.accident_type`、`stream_fn=None`。

`on_progress` 负责 SSE 事件（progress/chunk/section_done）；`_run_batch_generation` 的逐章生成不再直接发 chunk 事件，SSE 版本需要在 `stream_fn` 包装中转发 chunk。为保持 SSE 流式体验，SSE 端点的 `stream_fn` 用内部包装：

```python
                async def sse_stream(prompt, cfg, pt, sp, ao):
                    full = ""
                    async for chunk in _stream_llm_chunks(prompt, cfg, pt, sp, ao):
                        full += chunk
                        await event_queue.put(sse_event("chunk", content=chunk, section_key=section_key))
                    return full
```

`generate_batch_background` 直接传 `stream_fn=None`（走 `_stream_llm`）。

两个端点生成完成后统一更新状态并写自动版本快照：第 3 批实施前必须先完成批 2 任务 4，直接调用批 2 新增的 `from app.routers.versions import _build_snapshot` 构造 `ver_snapshot = _build_snapshot(p2, updated)`，替换 `generation.py` 两处手工快照构造（行号约 512 与 714）。

- [ ] **步骤 6：新增 status 端点**

```python
# backend/app/routers/generation.py  stop_generation 附近新增：
@router.get("/{plan_id}/generate/status")
async def get_generation_status(plan_id: str, current_user=Depends(get_current_user)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id
    ))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    return {
        "code": 0,
        "data": {
            "generating": _active_generations.get(plan_id, False),
            "failed_sections": _failed_sections.get(plan_id, []),
        },
    }
```

模块级新增 `_failed_sections: dict[str, list] = {}`，批量任务完成后写入；任务开始时清空。

- [ ] **步骤 7：全量回归**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过（若现有批量接口测试存在，需同步调整）

- [ ] **步骤 8：Commit**

```bash
git add backend/app/routers/generation.py backend/tests/test_generation_batch_refactor.py
git commit -m "refactor(plan): extract shared batch generation with failure tracking (batch3)"
```

---

### 任务 4：前端失败重试入口

**文件：**
- 修改：`frontend/src/types/plan.ts`（SSEEvent）
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`

- [ ] **步骤 1：类型扩展**

```typescript
// frontend/src/types/plan.ts  SSEEvent 追加：
  failed_sections?: Array<{ section_key: string; title: string }>;
```

- [ ] **步骤 2：batch_done 事件处理失败清单**

```typescript
// frontend/src/pages/Plan/PlanEditorPage.tsx  batch_done 分支追加 state：
  const [failedSections, setFailedSections] = useState<Array<{ section_key: string; title: string }>>([]);

          case "batch_done":
            setIsGenerating(false);
            setGeneratingSections(new Set());
            setBatchProgress({ current: 0, total: 0, message: "" });
            if (event.failed_sections && event.failed_sections.length > 0) {
              setFailedSections(event.failed_sections);
              message.warning(`${event.failed_sections.length} 个章节生成失败`);
            } else {
              message.success(`全部生成完成，共 ${completedCount} 个章节`);
            }
            queryClient.invalidateQueries({ queryKey: ["planSections", id] });
            queryClient.invalidateQueries({ queryKey: ["plan", id] });
            break;
```

- [ ] **步骤 3：失败提示 + 重试按钮**

```typescript
// PlanEditorPage.tsx  Progress 区域下方渲染：
        {failedSections.length > 0 && !isGenerating && (
          <Alert
            type="warning"
            showIcon
            message={`${failedSections.length} 个章节生成失败`}
            description={failedSections.map((f) => f.title).join("、")}
            action={
              <Button
                size="small"
                onClick={() => {
                  startRealtimeGeneration(failedSections.map((f) => f.section_key));
                  setFailedSections([]);
                }}
              >
                重试失败章节
              </Button>
            }
          />
        )}
```

`startRealtimeGeneration` 增加可选参数 `keys?: string[]`，为 `undefined` 时生成全部、否则只生成传入 keys。需从 `antd` 导入 `Alert`。

- [ ] **步骤 4：类型检查**

运行：`cd frontend && npx tsc -b`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/types/plan.ts frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "feat(plan): retry failed sections in web editor (batch3)"
```

---

### 任务 5：Diff 对比弹窗

**文件：**
- 新增：`frontend/src/components/plan/DiffPreviewModal.tsx`
- 修改：`frontend/src/components/plan/AIGenerateButton.tsx`
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`

- [ ] **步骤 1：实现 DiffPreviewModal**

```typescript
// frontend/src/components/plan/DiffPreviewModal.tsx
import { Modal, Button, Typography } from "antd";

const { Text } = Typography;

interface DiffPreviewModalProps {
  open: boolean;
  oldText: string;
  newText: string;
  onAccept: () => void;
  onReject: () => void;
  onClose: () => void;
}

function diffLines(oldText: string, newText: string) {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const maxLen = Math.max(oldLines.length, newLines.length);
  const rows = [];
  for (let i = 0; i < maxLen; i++) {
    const o = oldLines[i] ?? "";
    const n = newLines[i] ?? "";
    rows.push({ old: o, new: n, changed: o !== n });
  }
  return rows;
}

export default function DiffPreviewModal({
  open, oldText, newText, onAccept, onReject, onClose,
}: DiffPreviewModalProps) {
  const rows = diffLines(oldText, newText);
  return (
    <Modal
      title="生成结果对比"
      open={open}
      width={860}
      onCancel={onClose}
      footer={[
        <Button key="reject" danger onClick={onReject}>拒绝，恢复原文</Button>,
        <Button key="accept" type="primary" onClick={onAccept}>接受新内容</Button>,
      ]}
    >
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ flex: 1, border: "1px solid #f0f0f0", padding: 8, maxHeight: 420, overflow: "auto" }}>
          <Text strong>原文</Text>
          {rows.map((r, i) => (
            <div key={i} style={{ background: r.changed ? "#fff1f0" : "transparent", whiteSpace: "pre-wrap" }}>
              {r.old}
            </div>
          ))}
        </div>
        <div style={{ flex: 1, border: "1px solid #f0f0f0", padding: 8, maxHeight: 420, overflow: "auto" }}>
          <Text strong>新内容</Text>
          {rows.map((r, i) => (
            <div key={i} style={{ background: r.changed ? "#f6ffed" : "transparent", whiteSpace: "pre-wrap" }}>
              {r.new}
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
}
```

- [ ] **步骤 2：AIGenerateButton 集成 Diff**

```typescript
// frontend/src/components/plan/AIGenerateButton.tsx
// props 追加：
  oldContent?: string;
  onReject?: () => void;

// state 追加：
  const [diffOpen, setDiffOpen] = useState(false);
  const [diffOld, setDiffOld] = useState("");
  const [diffNew, setDiffNew] = useState("");

// handleConfirm 内 full 模式 done 分支追加（生成完成且新旧不同）：
            } else if (event.type === "done") {
              setStatus("done");
              const newText = event.content || fullTextRef.current;
              onGenerateComplete(newText);
              if (oldContent && newText !== oldContent) {
                setDiffOld(oldContent);
                setDiffNew(newText);
                setDiffOpen(true);
              }
              setTimeout(() => setStatus("idle"), 1500);
            }

// 组件返回 JSX 末尾追加：
      <DiffPreviewModal
        open={diffOpen}
        oldText={diffOld}
        newText={diffNew}
        onAccept={() => setDiffOpen(false)}
        onReject={() => {
          setDiffOpen(false);
          onReject?.();
        }}
        onClose={() => setDiffOpen(false)}
      />
```

- [ ] **步骤 3：PlanEditorPage 传 oldContent / onReject**

```typescript
// PlanEditorPage.tsx  AIGenerateButton 追加 props：
            oldContent={currentSection.content || ""}
            onReject={() => {
              queryClient.invalidateQueries({ queryKey: ["planSections", id] });
            }}
```

`onReject` 依赖后端已恢复旧内容（实现方式：拒绝时前端调 `updateSection(id, key, { content: oldContent })`，在 `PlanEditorPage` 的 `onReject` 中调用既有 `saveMutation`）。

- [ ] **步骤 4：类型检查与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：全部通过

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/plan/DiffPreviewModal.tsx frontend/src/components/plan/AIGenerateButton.tsx frontend/src/pages/Plan/PlanEditorPage.tsx
git commit -m "feat(plan): add generation diff preview modal (batch3)"
```

---

### 任务 6：移动端批量生成接入

**文件：**
- 修改：`frontend/src/mobile/screens/PlanEditorScreen.tsx`
- 修改：`frontend/src/services/generationService.ts`

- [ ] **步骤 1：generateBatchBackground 返回 failed_sections**

```typescript
// frontend/src/services/generationService.ts  返回类型扩展：
export async function generateBatchBackground(
  planId: string,
  sectionKeys: string[] | null
): Promise<{ code: number; message: string; failed_sections?: Array<{ section_key: string; title: string }> }> {
  // 现有实现不变，返回体直接透传
}
```

- [ ] **步骤 2：移动端批量按钮接入后台接口**

```typescript
// frontend/src/mobile/screens/PlanEditorScreen.tsx  批量生成按钮 onClick 替换为：
      onClick={async () => {
        try {
          const generatable = chapters
            .flatMap((c) => [c, ...(c.children || [])])
            .filter((c) => c.aiGeneratable)
            .map((c) => c.key);
          if (generatable.length === 0) {
            showToast?.({ type: "info", message: "没有可生成的章节" });
            return;
          }
          const res = await generateBatchBackground(planId!, generatable);
          showToast?.({ type: "success", message: res.message || "已在后台开始生成" });
          setTimeout(() => queryClient.invalidateQueries({ queryKey: ["plan-sections", planId] }), 5000);
        } catch (e: any) {
          showToast?.({ type: "error", message: e?.message || "批量生成失败" });
        }
      }}
```

需从 `@/services/generationService` 导入 `generateBatchBackground`。

- [ ] **步骤 3：类型检查**

运行：`cd frontend && npx tsc -b`
预期：PASS

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/mobile/screens/PlanEditorScreen.tsx frontend/src/services/generationService.ts
git commit -m "feat(plan): enable mobile batch generation via background API (batch3)"
```

---

### 任务 7：第 3 批收尾验证

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && .venv/Scripts/python -m pytest tests/ -q`
预期：全部通过

- [ ] **步骤 2：前端构建与测试**

运行：`cd frontend && npx tsc -b && npx vitest run`
预期：全部通过

- [ ] **步骤 3：规格对照自检**

- [x] 3.5 质量服务 → 任务 1
- [x] 3.5 validate 接入 + 前端报告 → 任务 2
- [x] 3.6 failed_sections + status → 任务 3
- [x] 3.6 前端重试 → 任务 4
- [x] 3.8 Diff 弹窗 → 任务 5
- [x] 3.7 批量抽取 + 移动端接入 → 任务 3、6
- [x] 测试计划对应用例 → 各任务步骤

- [ ] **步骤 4：Commit（如收尾有额外改动）**

```bash
git add -A
git commit -m "chore(plan): batch3 final verification"
```
