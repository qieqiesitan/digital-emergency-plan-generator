# 四色分布图干扰项自动剔除 — 设计规格

日期：2026-08-07
状态：头脑风暴已批准（含 OCR + 零样本 CLIP 增强），等待用户审查书面规格

## 1. 背景与目标

四色分布图除分区要素外还包含大量干扰项：图例（四色小色块簇）、图框细线、指北针/比例尺、独立文字符号、背景网格、大面积彩色 Logo 等。当前识别管线会把其中一部分误识别为分区（图例稳定产生 4 个假分区），并受细碎元素干扰。

目标：在识别管线内新增**纯视觉规则过滤层**，自动剔除高置信干扰项，并对低置信干扰项标记"疑似"；所有自动剔除项在预览中可见、可恢复，绝不静默删除。

范围：仅影响四色图识别（analyze）与预览交互；commit 契约不变；不使用视觉模型。

## 2. 需求决策（头脑风暴结论）

1. 干扰类型：图例/图框/表格、文字线条符号、背景网格、大面积 Logo 四类都存在（用户确认 D）。
2. 主识别用**纯视觉规则**；辅助增强：**RapidOCR** 读图上文字（分区建议名 + 文字干扰提示）、**零样本 CLIP**（mobileCLIP）判别疑似干扰。不使用外部视觉 API、不训练模型（YOLO 微调后置）。
3. **保守优先**：只自动剔除"几乎肯定不是分区"的项；低置信的大色块保留为分区并标记"疑似干扰"，由用户在预览中决定去留。
4. 自动剔除项在预览中展示并可一键恢复。
5. 落地方式：识别管线内加"干扰过滤层"（方案 1），对比视图用"已自动排除"列表覆盖，交互删除保留为既有预览能力兜底。
6. AI 辅助结果**只强化提示、绝不自动删除**；模型/依赖缺失时静默降级为纯规则模式。

## 3. 整体流程（数据流）

1. 上传 → `recognize_from_bytes`：解码 → 透视校正（保守门控）→ 颜色分类 → 形态学清理 → 轮廓提取。
2. **新增过滤层**：把四色通道的候选色块汇总，运行 `classify_interference`，输出三组：`kept`（正常分区）、`excluded`（高置信自动排除）、`suspected`（保留但标记）。
3. `kept` + `suspected` 生成分区（`suspected` 分区带标记），`excluded` 随 analyze 响应返回。
4. 前端预览：分区列表（含"疑似干扰"标签）+ 折叠区"已自动排除干扰项（N）"（每项可恢复）。
5. 用户确认落图 → commit（只提交分区，排除项不落库）。

## 4. 识别器过滤层（核心）

### 4.1 位置与形态

在 `four_color_recognizer.py` 中，把当前"按颜色循环 → 立即生成 zones"重构为：

```text
extract_components(mask, color, ...) -> list[ComponentInfo]   # 每色通道
classify_interference(components, width, height) -> InterferenceResult
components_to_zones(kept + suspected) -> zones                # suspected 置标记
```

`ComponentInfo`：`color`（调色板名）、`points`（像素多边形）、`area`、`bbox`（x0,y0,x1,y1）。

`InterferenceResult`：`kept`、`excluded`（含 reason）、`suspected`。

### 4.2 规则（全部保守，按置信度分级）

| 规则 | 判定 | 结果 | reason |
| --- | --- | --- | --- |
| 图例簇 | 一组紧邻、尺寸相近（尺寸比 ≤3）、包含 ≥3 种四色、单块面积在 0.02%-2% 画面的色块簇 | 整组排除 | `legend` |
| 细长线 | 外接矩形宽高比 >12:1，或实心度极低的长条 | 排除 | `thin` |
| 贴边细框 | bbox 贴图像边缘且厚度 <1% 画面、沿一个方向延伸较长 | 排除 | `border_frame` |
| 极小噪点 | 面积 < `MIN_AREA_RATIO`（沿用现有值 5e-5） | 排除 | `tiny` |
| 疑似大色块 | 面积 >5% 画面且实心度 <0.5（形状异常） | **保留** + `suspected=true` | - |

常量（集中定义、可调）：

```python
LEGEND_MIN_COLORS = 3
LEGEND_MIN_AREA_RATIO = 2e-4
LEGEND_MAX_AREA_RATIO = 0.02
LEGEND_MAX_SIZE_RATIO = 3.0
LEGEND_PROXIMITY_RATIO = 0.08
THIN_ASPECT_RATIO = 12.0
BORDER_FRAME_THICKNESS_RATIO = 0.01
SUSPECT_AREA_RATIO = 0.05
SUSPECT_SOLIDITY = 0.5
```

文字压住分区由既有闭运算处理，不新增规则；背景网格线由颜色分类阶段天然排除。

### 4.3 图例簇判定细则

1. 过滤出面积在 `LEGEND_MIN_AREA_RATIO..LEGEND_MAX_AREA_RATIO` 画面区间的候选色块。
2. 两两判定"相邻"：两 bbox 的最近间距 < `LEGEND_PROXIMITY_RATIO` × 图像最短边，且面积比 ≤ `LEGEND_MAX_SIZE_RATIO`。
3. 用并查集把相邻色块聚成簇；簇内颜色种类 ≥ `LEGEND_MIN_COLORS` 判定为图例簇。
4. 整簇排除，reason=`legend`；簇内所有色块不再进入分区。

### 4.4 OCR 文字识别（RapidOCR，辅助）

- 依赖：`rapidocr_onnxruntime`（模型随包内置，约 15MB，仅依赖 onnxruntime，无 Paddle 重依赖）。
- 时机：分区构建完成后，对校正后整图执行一次 OCR（CPU 0.2-0.8 秒），产出文字框列表。
- 用途：
  1. **建议名**：文字框中心落在分区多边形内 → 该分区 `suggested_name`（预览预填、可编辑）；同一分区多段文字按面积取主文字。
  2. **图例佐证**：图例色块附近的"重大/较大/一般/低"等文字增强图例簇判定置信。
  3. **文字干扰提示**：疑似分区内含文字 → `ai_hint` 倾向"疑似标签/装饰"。
- 独立文字框（不在任何分区内）不参与分区生成，仅进入 `texts` 列表供预览展示。

### 4.5 零样本 CLIP 疑似判别（mobileCLIP，辅助）

- 模型：mobileCLIP-S2 ONNX（约 15-20MB）。**工程风险**：预转换 ONNX 文件来源需验证；构建期拿不到则降级为纯启发式，不阻塞主流程。
- 时机：对 `suspected` 色块，按 bbox 带边距裁剪 → 224×224 → 与提示词（"风险分区色块" / "图标Logo" / "图例色块" / "文字标签"）比对相似度。
- 输出：`ai_hint`（如"疑似图例"、"疑似Logo"）；**仅提示，不自动排除**。
- 性能：单色块几十到几百毫秒；候选通常 0-5 个。

### 4.6 降级策略

- `rapidocr_onnxruntime` 或 CLIP 模型缺失/加载失败 → 对应功能静默跳过：分区名回退"分区N"、疑似仍走启发式，analyze 照常返回（与 cv2 可选导入同一模式）。

## 5. 数据结构与 API 契约

### 5.1 后端

`RecognizeResult` 增加：

```python
excluded: list[dict]   # {color, reason, polygons}，polygons 与 zones 同构
```

`zones` 每个分区 dict 增加 `suspected: bool`。

`backend/app/schemas/risk_management.py`：

```python
class FourColorExcludedItem(BaseModel):
    color: str
    reason: Literal["legend", "thin", "border_frame", "tiny"]
    polygons: list[FourColorDraftPolygon]

class FourColorDraftZone(BaseModel):
    ...  # 现有字段
    suspected: bool = False
    suggested_name: str | None = None
    ai_hint: str | None = None

class FourColorTextItem(BaseModel):
    points: list[RiskPolygonPoint]   # 文字框四点
    text: str
    confidence: float

class FourColorAnalyzeResponse(BaseModel):
    ...  # 现有字段
    excluded: list[FourColorExcludedItem] = []
    texts: list[FourColorTextItem] = []
```

`FourColorCommitRequest`、commit 行为不变（只提交分区；被排除项不落库；恢复后的项即为普通分区）。

### 5.2 前端

```ts
export interface FourColorExcludedItem {
  color: string;
  reason: "legend" | "thin" | "border_frame" | "tiny";
  polygons: FourColorDraftPolygon[];
}
export interface FourColorTextItem {
  points: { x: number; y: number }[];
  text: string;
  confidence: number;
}
// FourColorDraftZone 增加 suspected?: boolean / suggested_name?: string | null / ai_hint?: string | null
// FourColorAnalyzeResult 增加 excluded: FourColorExcludedItem[] / texts: FourColorTextItem[]
```

reason 中文映射：`legend=图例`、`thin=细长线/符号`、`border_frame=贴边图框`、`tiny=极小噪点`。

## 6. 前端交互（FourColorImportModal.tsx）

- 新增状态 `excluded: FourColorExcludedItem[]`，analyze 成功后写入。
- 新增状态 `texts: FourColorTextItem[]`；预览图新增"文字标注"开关（SVG 虚线框叠显，默认开）。
- 分区列表下方新增折叠区（antd Collapse）"已自动排除干扰项（N）"：逐项显示原因中文标签 + 「恢复」按钮；恢复 = 由该项生成新分区（`client_id=draft-uuid`、名称"分区N"、`risk_level` 按 color 映射、polygons 原样）追加到 zones，并从 excluded 移除。
- `suspected=true` 的分区行追加橙色"疑似干扰"Tag；不阻止提交。
- `suggested_name` 非空时预填到名称输入框（仍可编辑）；`ai_hint` 非空时作为 Tag 的 tooltip 展示。
- 删除/恢复共用 zones 状态；commit payload 组装逻辑不变。

## 7. 测试策略

### 7.1 后端单测 `test_four_color_recognizer.py`（新增）

1. 合成四色图例（4 个紧邻小色块）→ `excluded` 含 reason=`legend`（整簇 4 项），其余分区不受影响。
2. 合成细长线（宽高比 >12）→ reason=`thin`。
3. 合成贴边细框（紧贴图像边缘的薄条）→ reason=`border_frame`。
4. 合成大块异常形状（凹多边形、实心度 <0.5、面积 >5%）→ 保留为分区且 `suspected=True`。
5. 正常四矩形图 → `excluded` 为空、全部 `suspected=False`（既有用例断言补全）。
6. 既有透视/噪点/文字用例保持通过。

OCR/CLIP 相关：
7. 合成"文字压分区"图 → 分区 `suggested_name` 提取正确；独立文字 → `texts` 列表。
8. 合成图例 + 图例文字 → 图例仍被排除（OCR 佐证不破坏原判定）。
9. CLIP 接线用 mock 单测（suspected 项 → `ai_hint` 传播正确）；真实模型做可选集成测试（模型缺失跳过）。

### 7.2 后端 API `test_four_color_import_api.py`

- `FourColorAnalyzeResponse` schema 接受/校验 `excluded` 与 `suspected`。
- `FourColorAnalyzeResponse` schema 接受/校验 `texts`、`suggested_name`、`ai_hint`。
- analyze 端点响应含 `excluded` 字段（可为空列表）。

### 7.3 前端

- E2E（`four-color-import.spec.ts` 新增用例）：mock analyze 返回 `excluded` 项与 `suspected` 分区 → 预览显示"已自动排除干扰项（1）"与"疑似干扰"标签 → 点恢复 → 分区列表 +1 → 确认落图成功。
- E2E 增量：mock 返回 `suggested_name` / `ai_hint` / `texts` → 名称预填、"疑似干扰"Tag 带提示、文字标注叠显开关可用。
- 既有 2 个 E2E 用例保持通过。

## 8. 受影响文件清单

后端：
- `backend/app/services/four_color_recognizer.py`（过滤层 + RecognizeResult 扩展）
- `backend/app/services/vision_helpers.py`（新增：OCR 与 CLIP 加载/调用封装，含降级）
- `backend/app/schemas/risk_management.py`（excluded/suspected）
- `backend/requirements.txt`（新增 `rapidocr_onnxruntime`）
- `backend/Dockerfile` 或构建流程（CLIP ONNX 模型资产打包；失败时降级）
- `backend/tests/test_four_color_recognizer.py`
- `backend/tests/test_four_color_import_api.py`

前端：
- `frontend/src/types/riskMappingWorkbench.ts`
- `frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`
- `frontend/e2e/four-color-import.spec.ts`

## 9. 错误处理

- 无新错误码；过滤层为纯函数，输入异常（缺 polygons/越界）由既有 `validate_polygon_v2` 与 schema 校验兜底。
- 图例检测误判风险：若真实小分区恰好形成"3 色紧邻簇"，可能被误排除 → 由预览"已自动排除"列表可恢复兜底（保守优先的代价）。
- `excluded` 为空是合法响应，前端折叠区隐藏。

## 10. 明确不做（YAGNI / 二期）

- YOLO 目标检测微调（图例/文字块/指北针的专用检测器，后置）。
- 排除项持久化 / 同图多次导入的黑名单记忆。
- 背景网格专项规则（颜色分类已排除）。
- 排除项的可调参数 UI（常量集中管理，后续按真实图集校准）。
- 图上文字自动写入数据库（`suggested_name` 仅为预览预填，用户确认后随分区提交）。

## 11. 风险与关键决策

- 规则阈值是启发式常量，需用真实图集校准；首版以保守默认值起步，靠"可恢复"兜底。
- 图例簇判定可能把紧邻的多个真实小分区误判为图例 → 保守阈值（≥3 色、尺寸相近、间距小）+ 预览恢复兜底。
- `suspected` 不阻止提交，仅提示，避免流程卡顿。
- 过滤层保持纯函数、无 DB/IO 依赖，与现有识别器测试模式一致。
- mobileCLIP 预转换 ONNX 文件来源是构建期风险点 → 提供降级路径，不阻塞主流程。
- 零样本 CLIP 对抽象色块判别准确率中等 → 结果仅作提示，人工确认兜底。
- RapidOCR 对印刷体中文识别良好，手写/艺术字可能失败 → 建议名可编辑，失败时保持"分区N"。
