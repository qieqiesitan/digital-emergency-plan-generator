# 四色分布图自动识别导入 — 设计规格

日期：2026-08-06
状态：头脑风暴已批准，等待用户审查书面规格

## 1. 背景与目标

用户（企业安全管理人员）在制作数字化四色分布图时，通常已经持有本企业的现有四色分布图（电子版或纸质拍照件）。当前系统的四色分布工作台要求从零开始绘制分区，重复劳动明显。

目标：用户上传现有四色分布图后，系统自动识别图中红/橙/黄/蓝四色区域并自动落图——上传图成为该楼层的底图，识别出的分区按原图位置落好，用户只需校对微调即可保存。

范围：仅服务"四色分布工作台"单楼层导入；不动风险评估、预案生成等其他模块。

## 2. 需求决策（头脑风暴结论）

1. 图源形态：干净电子图与拍照/扫描件两种都要支持。
2. 上传图与系统现有平面图**无几何关系**，因此不需要配准、锚点或特征匹配；上传图本身成为该楼层的底图。
3. 每楼层一张四色图，导入动作绑定到指定楼层。
4. 识别输出：**形状 + 颜色等级**。颜色映射：红=重大、橙=较大、黄=一般、蓝=低（与前端 `RiskLevel` 枚举一致）。名称默认"分区N"，由用户校对时修改。纯计算机视觉实现，零 AI 成本。
5. 技术路线：**后端 OpenCV 一键识别 + 工作台校对落图**。不做前端 Canvas 识别，不做容差调节滑块（列入二期）。
6. 设计底线：识别结果不直接入库，先经"预览校对"环节；确认落图时若楼层已有数据，需用户显式确认替换。

## 3. 整体流程（数据流）

1. 用户在工作台顶部点击「导入四色图」→ 弹出 `FourColorImportModal`。
2. 选择图片（PNG/JPEG/WebP，≤20MB，≤12000×12000）→ 上传调用 `analyze` 接口。
3. 后端保存临时文件并执行识别（不写任何业务表）→ 返回预览 URL、画布尺寸、分区草稿、警告列表。
4. 预览界面：左侧原图 + 识别多边形叠显（按颜色描边），右侧分区列表（可改名、可删行）。
5. 用户点击「确认落图」→ 若有已有数据则弹确认框（默认勾选替换）→ 调用 `commit` 接口。
6. 后端事务内：转正临时文件 → 更新楼层底图与画布尺寸 → 按规则替换或创建分区 → 提交。
7. 前端用 commit 返回结果刷新工作台 store（`setSnapshot` + `markSaved`），画布直接显示成品，可继续编辑。
8. 用户取消或关闭弹窗（已 analyze）→ 调用 `cancel` 接口清理临时文件。

## 4. 后端识别管线

新增 `backend/app/services/four_color_recognizer.py`，全部拆成可单测的纯函数：

### 4.1 常量

```python
COLOR_PALETTE = {"红": (255, 0, 0), "橙": (255, 127, 0), "黄": (255, 255, 0), "蓝": (0, 0, 255)}
LEVEL_BY_COLOR = {"红": "重大", "橙": "较大", "黄": "一般", "蓝": "低"}
MIN_AREA_RATIO = 5e-5        # 相对图片面积的最小连通区域占比，过滤噪点
EPSILON_RATIO = 0.0025       # 多边形简化 epsilon 相对对角线比例（Douglas-Peucker）
MAX_POLYGON_POINTS = 128     # 简化后多边形顶点上限
MAX_ZONES = 200              # 单次识别分区上限，超出截断并警告
```

### 4.2 纯函数清单

- `detect_perspective_quad(img) -> np.ndarray | None`：检测最大近似四边形（纸张/图框边缘）。若四边形近似整图（面积占比 >95%）返回 None（无需校正）。
- `warp_perspective(img, quad) -> np.ndarray`：四点透视校正为正矩形。
- `classify_pixels(img) -> dict[str, np.ndarray]`：逐像素按 HSV 距离归类到最近标准色；距离超过阈值归为无色。红色需处理色相 0/360 环绕。
- `clean_mask(mask) -> np.ndarray`：形态学开运算 + 闭运算（核 3×3，随图片尺寸放大），去除噪点、填补文字造成的小孔。
- `mask_to_polygons(mask, width, height) -> list[list[tuple[float, float]]]`：`findContours`（RETR_EXTERNAL）+ `approxPolyDP` 简化 + 最小面积过滤 + 顶点上限，输出像素坐标多边形。
- `normalize_points(points, width, height) -> list[dict]`：像素坐标归一化为 0-100（`x / width * 100`，`y / height * 100`），越界 clamp 到 [0, 100]，四舍五入保留 2 位小数。
- `recognize_from_bytes(data: bytes) -> RecognizeResult`：管线入口，输出 `RecognizeResult(zones, warnings)`。

### 4.3 管线步骤

1. Pillow 打开图片，应用 EXIF 方向。
2. 尝试透视校正（拍照件路径）：检测到明显四边形 → warp；失败 → 继续原图识别并追加 warning「未能自动校正透视，请尽量上传正拍图」。
3. 对四色分别生成二值掩码 → `clean_mask` → `mask_to_polygons`。
4. 每个连通色块生成一个分区草稿：名称"分区N"（按色块顺序递增）、等级按 `LEVEL_BY_COLOR`、多边形数组（`floor_plan_polygon` v2 结构）。
5. 同名同色不相邻区域**不合并**：每个连通区域独立成区，用户可在校对列表删改。
6. 返回 `zones`（≤MAX_ZONES）与 `warnings`（透视失败、超限截断、存在无法可靠识别的色块等）。

## 5. API 契约

路由前缀与现有 risk-management 一致（`/api/v1/enterprises/{enterprise_id}/risk-management`），统一走 `ApiResponse` 包装、`get_current_user` 鉴权，楼层必须属于当前企业（`_get_ent` + floor 归属校验，否则 404）。

### 5.1 POST `/floors/{floor_id}/four-color/analyze`

multipart 上传，字段名 `file`。

- 校验复用 `save_floor_plan` 同款规则：仅 PNG/JPEG/WebP、≤20MB、≤12000×12000。
- 保存临时文件到 `{UPLOAD_DIR}/enterprises/{eid}/floors/{floor_id}/four_color_tmp/{token}/source{ext}`，`token = uuid4().hex`。
- 先清理该楼层旧 `four_color_tmp` 目录（防堆积）。
- 不写任何业务表，可重复调用（幂等）。
- 未识别到任何四色区域 → `422`，`detail.code = "NO_ZONE_DETECTED"`，message「未识别到红/橙/黄/蓝色块，请检查图片」。

响应 `data`：

```json
{
  "preview_url": "/uploads/enterprises/{eid}/floors/{floor_id}/four_color_tmp/{token}/source.png",
  "canvas_width": 1200,
  "canvas_height": 800,
  "zones": [
    {
      "client_id": "draft-{uuid}",
      "name": "分区1",
      "risk_level": "重大",
      "color": "#FF0000",
      "polygons": [
        { "id": "poly-{uuid}", "label": null, "points": [ { "x": 12.3, "y": 45.6 } ] }
      ]
    }
  ],
  "warnings": []
}
```

### 5.2 POST `/floors/{floor_id}/four-color/commit`

请求体：

```json
{
  "file_token": "uuid-hex",
  "zones": [
    {
      "name": "分区1",
      "risk_level": "重大",
      "polygons": [ { "points": [ { "x": 1, "y": 2 } ] } ]
    }
  ],
  "replace_existing": true
}
```

校验：

- `file_token` 必须匹配 UUID hex 格式，且该楼层 `four_color_tmp/{token}` 目录存在，否则 404。
- `zones` 数量 1..MAX_ZONES；每个 zone 的 `polygons` ≥1、每多边形点 ≥3、坐标 0-100；`risk_level ∈ {重大, 较大, 一般, 低}`；`name` 非空且 ≤50 字符。复用/对齐 `validate_polygon_v2` 与 `RiskPolygonPoint` 校验，违规 422。
- `replace_existing=false` 且楼层已有分区或 `canvas_texts` 非空 → 422，`detail.code = "FLOOR_NOT_EMPTY"`。

事务与文件操作顺序：

1. 校验全部输入。
2. 文件先行：`four_color_tmp/{token}/source{ext}` rename 为正式文件名 `{YYYYMMDD}_{uuid}{ext}`（同卷 rename，失败概率趋零）；失败抛 500，DB 未动。
3. DB 事务：`SELECT ... FOR UPDATE` 锁楼层 → `replace_existing=true` 时删除该楼层全部 `RiskZone`（ORM `cascade="all, delete-orphan"` 级联删除对象/风险点/单位/事件/措施）并清空 `canvas_texts` → 更新 `floor_plan_url`、`canvas_width`、`canvas_height` → 按序创建新分区（`color_source="manual"`、`color` 对应等级色、`sort_order` 按序号、`floor_plan_polygon` v2 结构）。
4. DB 失败 → 回滚并尽力删除刚 rename 的正式文件，返回错误。
5. 提交成功后：删除旧底图文件（replace 时，复用 `remove_floor_plan` 安全路径校验）、清理 `four_color_tmp/{token}`。

响应 `data`（对齐 `BatchSaveResponse` 形态，前端可直接 `setSnapshot`）：

```json
{ "floor": { "...": "FloorResponse" }, "zones": [ { "...": "RiskZoneResponse" } ] }
```

### 5.3 DELETE `/floors/{floor_id}/four-color/{file_token}`

- 幂等删除 `four_color_tmp/{token}` 目录；路径安全校验同 `remove_floor_plan`（resolved 路径必须在楼层目录内）。
- 成功返回 `ApiResponse(message="已清理临时文件")`（200），与现有 DELETE 端点风格一致。

## 6. 前端交互

### 6.1 类型（`frontend/src/types/riskMappingWorkbench.ts`）

```ts
export interface FourColorDraftZone {
  client_id: string;
  name: string;
  risk_level: RiskLevel;
  color: string;
  polygons: { id: string; label?: string | null; points: { x: number; y: number }[] }[];
}
export interface FourColorAnalyzeResult {
  preview_url: string;
  canvas_width: number;
  canvas_height: number;
  zones: FourColorDraftZone[];
  warnings: string[];
}
export interface FourColorCommitPayload {
  file_token: string;
  zones: { name: string; risk_level: RiskLevel; polygons: { points: { x: number; y: number }[] }[] }[];
  replace_existing: boolean;
}
```

### 6.2 服务函数（`frontend/src/services/riskMappingWorkbenchService.ts`）

- `analyzeFourColorMap(eid, floorId, file)`：FormData POST analyze。
- `commitFourColorImport(eid, floorId, payload)`：POST commit。
- `cancelFourColorImport(eid, floorId, token)`：DELETE cancel。

### 6.3 组件 `FourColorImportModal.tsx`（新增，`frontend/src/components/enterprise/riskMapping/`）

- 阶段：`select`（Upload.Dragger 选图）→ `analyzing`（Spin）→ `preview`。
- 预览：左侧 `<img src={preview_url}>` + SVG overlay（每个 zone 按 `color` 描边、半透明填充）；右侧 antd List（名称可编辑 Input、等级 Tag、删除按钮）；`warnings` 以 Alert 展示。
- 底部按钮：取消（已 analyze 则先调 cancel）/ 确认落图（`zones` 为空或 analyzing 时禁用）。
- 确认前检测楼层已有数据（zones / 风险点 / texts 任一非空）→ `Modal.confirm` + Checkbox「移除该楼层原有分区、文字标注与风险点」（默认勾选，决定 `replace_existing`）。
- 提交成功 → `onImported(commitResult)` 回调，由父组件刷新。
- `NO_ZONE_DETECTED` → 错误提示并停留在选图阶段；网络错误 → message.error。

### 6.4 页面集成（`RiskMappingWorkbenchPage.tsx`）

- 顶部按钮「导入四色图」（icon `UploadOutlined`）置于 `EnterpriseFloorManager` 与 `WorkbenchToolbar` 之间。
- 维护 `importOpen` 状态与当前楼层；无楼层时按钮禁用。
- `onImported`：用返回的 `floor` + `zones`（风险点/文字清空）`setSnapshot` + `markSaved`，invalidate `risk-hierarchy` / `risk-overview` 查询。

## 7. 数据模型与兼容性

- 坐标：识别结果归一化为 0-100，与 `RiskPolygonPoint` 校验（0 ≤ x/y ≤ 100）完全兼容；`floor_plan_polygon` v2 结构（`version: 2, color_source, color, polygons[{id,label,points}]`）直接复用，无迁移。
- 等级：`risk_level` 使用现有字符串枚举「重大/较大/一般/低」，颜色→等级映射见 4.1。
- 画布尺寸：`canvas_width/height = 图片像素尺寸`（与 `upload_floor_plan` 行为一致），工作台按比例适配。
- 分区的 `color_source` 置为 `"manual"` 并写入识别色，避免与 `max_risk_level` 派生色冲突（分区当前无风险对象，`max_risk_level` 为 None，落图后由人工评估逐步填充）。
- 无需新增数据库表/字段。

## 8. 替换规则（replace_existing）

- 语义：底图更换后，旧分区、文字标注、风险点的坐标相对旧底图全部失去意义，因此替换时一并移除。
- 实现：删除该楼层全部 `RiskZone` 即可，ORM 关系 `cascade="all, delete-orphan"` 级联删除对象、风险点、单位、事件、措施；`canvas_texts` 置空。不直接删 `RiskObject`（避免与 ORM 级联重复/冲突）。
- 前端：已有数据时确认框默认勾选"移除并导入"；用户取消勾选则不提交（后端以 `replace_existing=false` + `FLOOR_NOT_EMPTY` 兜底）。
- 该删除不可逆，确认框文案明确提示将删除 N 个分区 / M 个风险点。

## 9. 错误处理汇总

| 场景 | 行为 |
| --- | --- |
| 文件类型/大小/像素超限 | 复用现有 422 提示（仅 PNG/JPEG/WebP、≤20MB、≤12000×12000） |
| 未识别到任何四色区域 | 422 `NO_ZONE_DETECTED`，前端提示并留在选图阶段 |
| 透视校正失败 | warning 提示，继续识别不阻断 |
| 区域超 MAX_ZONES | 截断 + warning「识别区域过多，已保留前 200 个」 |
| 部分色块不可靠识别 | warning「有 N 处颜色无法可靠识别，已忽略」 |
| token 无效 / 楼层不属于企业 | 404 |
| zones 校验失败 | 422（点 <3、坐标越界、非法等级、空名称等） |
| `replace_existing=false` 且有数据 | 422 `FLOOR_NOT_EMPTY` |
| commit DB 失败 | 回滚 + 尽力删除已转正文件 + 500/业务错误 |
| 取消/关闭弹窗 | 调 cancel 清理临时文件（幂等） |

## 10. 测试策略

### 10.1 后端单测 `backend/tests/test_four_color_recognizer.py`（Pillow 合成图）

1. 合成红/橙/黄/蓝四色块图 → 识别出 4 个分区，等级映射正确，多边形中心与色块中心偏差在容差内。
2. 抗锯齿/渐变边缘 → 多边形中心命中，坐标全部落在 0-100。
3. 随机小噪点 → 被 `MIN_AREA_RATIO` 过滤。
4. 色块上绘制文字 → 闭运算后轮廓连通、仍能识别。
5. 透视合成图 → 校正后识别成功。
6. 无四色纯白图 → 空 zones + warning。
7. `normalize_points` 越界 clamp。
8. `MAX_ZONES` 截断行为。

### 10.2 后端集成 `backend/tests/test_four_color_import_api.py`

1. analyze 上传合成图 → 200、zones>0、库表无变化。
2. analyze 非四色图 → 422 `NO_ZONE_DETECTED`。
3. commit 全链路 → floor_plan_url 更新（非 tmp 路径）、canvas 尺寸、zones 落库（名称/等级/polygons）。
4. commit `replace_existing=true` 有旧数据 → 旧分区/风险点/文字清除，新分区就位。
5. commit `replace_existing=false` 有旧数据 → 422 `FLOOR_NOT_EMPTY`。
6. commit 无效 token → 404；越权楼层 → 404。
7. commit zones 校验失败（点 <3、坐标越界、非法等级、超过 MAX_ZONES）→ 422。
8. cancel → 临时目录删除、幂等。

### 10.3 前端

- vitest：三个 service 函数（mock api）参数与响应解包正确。
- Playwright `frontend/e2e/four-color-import.spec.ts`（测试资产 `frontend/e2e/fixtures/four-color-sample.png` 由脚本/Pillow 预生成并入库）：
  1. 打开工作台 → 导入合成图 → 预览出现分区 → 确认落图 → 画布出现分区 → 保存成功。
  2. 楼层已有数据 → 确认框出现且默认勾选 → 提交后旧数据消失。

## 11. 依赖变更

- `backend/requirements.txt` 新增 `opencv-python-headless>=4.10,<5`（无 GUI 依赖，Docker/服务器友好）与 `numpy>=1.26`（显式声明，当前由 chromadb 传递引入）。
- Docker 后端镜像需重建（`docker compose build backend`），与现有部署流程一致。

## 12. 明确不做（YAGNI / 二期）

- 颜色容差调节滑块（混合交互模式）。
- OCR / 视觉大模型读取图上文字作为分区名。
- AI 自动命名分区。
- 同色不相邻区域自动合并为"一个分区多个多边形"。
- 手动四点透视校正 UI。
- 厂区总图 / 多楼层批量导入。
- 识别结果直接入库（不做自动跳过校对）。

## 13. 受影响文件清单

后端：

- `backend/app/services/four_color_recognizer.py`（新增）
- `backend/app/services/floor_plan_storage_service.py`（新增临时文件保存/转正/清理辅助函数）
- `backend/app/routers/risk_management.py`（新增 3 个端点）
- `backend/app/schemas/risk_management.py`（新增分析/提交 schema）
- `backend/requirements.txt`
- `backend/tests/test_four_color_recognizer.py`（新增）
- `backend/tests/test_four_color_import_api.py`（新增）

前端：

- `frontend/src/types/riskMappingWorkbench.ts`
- `frontend/src/services/riskMappingWorkbenchService.ts`
- `frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`（新增）
- `frontend/src/pages/Enterprise/RiskMappingWorkbenchPage.tsx`
- `frontend/e2e/four-color-import.spec.ts`（新增）
- `frontend/e2e/fixtures/four-color-sample.png`（新增测试资产）

## 14. 风险与关键决策

- 颜色容差是启发式常量，需用真实图集校准；首版默认值以"标准四色 + 常见打印色偏"为基准，宁多勿漏，靠校对兜底。
- 打印件色偏（偏暗/偏灰）通过放宽 HSV 明度/饱和度下限处理；仍无法识别时走 `NO_ZONE_DETECTED` 明确提示。
- 图例/标题若与色块同色可能误识别 → 由 `MIN_AREA_RATIO` 过滤 + 校对兜底，不做语义过滤（YAGNI）。
- 超大图（12000px）识别耗时上升，预期 <3s，可接受；`MAX_ZONES` 防极端输入拖垮接口。
- 替换删除不可逆 → 确认框 + 后端 `replace_existing` 显式语义双重保障。
- commit 采用"文件先行、DB 回滚补偿"顺序，规避文件系统与事务无法同原子的问题。
