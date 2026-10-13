# 四色分布图嵌套分区识别（封闭格提取）— 设计规格

日期：2026-10-13
状态：已实现并通过验证（用户确认方案：能识别的格子全部识别，围框进可恢复排除列表）

## 1. 背景与问题

用户反馈：上传白底彩边画法的风险四色图（永昇加油站）时，"很多分区内的分区识别不到，
画成一个统一的大分区"。原图 934×681，识别结果只有 7 个分区：中央"加油区"大框与
底部罐区被并成一个占图 28% 的怪形大分区，房间整排被并成一条，框内 加油机/储罐/卸油口/
各房间小框全部丢失。

## 2. 根因（代码证据）

1. 该图是"白底 + 彩色粗描边"画法：分区填充近纯白（HSV S≈0-24）被归背景，
   颜色掩码里只剩**边框线条**——每个分区在掩码中是一个空心环。
   实测：橙色掩码整图仅 32289 px 描边，但 `cv2.contourArea` 按"外轮廓包围面积"
   算出中央大环 177376 px（占全图 27.9%）。
2. `mask_to_polygons` 用 `RETR_EXTERNAL` 只取最外层轮廓：大环内部的所有独立小框
   在轮廓树里位于"洞"中，整批不被返回——这就是"分区内的分区识别不到"。
3. 大环外轮廓本身直接成为一个分区（统一大分区）；左上角两个储罐 + 卸油口因描边相连，
   连通域并成一个怪形分区。

复现与对照：`output/tmp/fourcolor-debug/`（debug_reco.py 中间图 + vis_external_contours.png
与用户截图逐一吻合；真实管线实跑 7 个分区、0 排除）。

## 3. 方案：封闭格提取（新增第二条识别路径）

实心色块路径（原有）与封闭格路径并存：

- **实心路径（改造）**：每色掩码先 `cv2.erode`（半径 = max(2, kernel_size)，borderValue=0）。
  腐蚀后仍存活的连通块才算"实心色块"（实心分区/图例/图标），按原逻辑经
  `classify_interference` 过滤；存活但填充率 < 0.5 的按"胖描边环"跳过（交给封闭格）。
  细描边（白底彩边图的分区边框）腐蚀后消失 → 不产出空心大分区。
- **封闭格路径（新增 `extract_enclosed_cells`）**：
  1. 四色描边并集为"墙"，膨胀 1 px 封住抗锯齿/JPEG 压缩造成的 1px 缺口；
  2. 反相后做连通域（4 连通）；**不与图像边缘连通**的连通域 = 被描边围住的一个格；
  3. 每格即一个分区候选（大框内部的小框各自成格，嵌套关系天然保留）；
  4. 颜色归属：格边界像素由近及远（半径 1→3）找最近的墙像素颜色投票
     （跨色覆盖，如橙色块压住蓝色行线，也能按边界主色判对）；
  5. 过滤分级：
     - 面积 < 0.2% 画布 → 静默丢弃（数字徽章白字、笔画缝）；
     - 有洞或填充率 < 0.5 且面积 < 1% 画布 → 视为"容器围框"，
       进 `excluded`（reason=`frame`，前端"已自动排除"可恢复）；
     - 细长比 > 12 → `excluded`（reason=`thin`）；
     - 面积 > 5% 画布且空心 → `suspected`（沿用原疑似规则）；
     - 格若 ≥90% 落在某个实心色块内部（实心分区里被文字/图案挖出的洞）→ 跳过。
- **OCR 命名**：文字框中心可能同时落在大分区与其内部小分区 → 归给**面积最小**（最内层）的
  未命名分区。

常量（`four_color_recognizer.py` 顶部集中定义）：
`SOLID_FILL_MIN=0.5`、`WALL_SEAL_DILATE_ITER=1`、`CELL_MIN_AREA_RATIO=2e-3`、
`FRAME_MAX_AREA_RATIO=0.01`、`FRAME_FILL_MIN=0.5`、`SOLID_CELL_OVERLAP_MIN=0.9`、
`CELL_COLOR_SEARCH_RADII=(1,2,3)`。

## 4. 接口与契约

- `reason` 枚举新增 `"frame"`：后端 `schemas/risk_management.py` Literal、
  前端 `types/riskMappingWorkbench.ts` 联合类型、`FourColorImportModal.tsx` 的
  `REASON_LABEL`（文案"容器围框"）同步更新。
- 分区多边形仍为单环多边形；嵌套分区之间允许重叠（与既有 v2 契约一致）。
- analyze/commit 接口契约不变；commit 前分区多边形校验不变。

## 5. 验证

- 单测（`backend/tests/test_four_color_recognizer.py`，新增 3 例）：
  - `test_recognize_detects_nested_zones_in_hollow_border_map`：白底彩边合成图
    4 个嵌套分区全识别，且大分区多边形取**内边界**（修复前 2 个、取外边界）；
  - `test_recognize_container_frame_goes_to_excluded`（围框有洞）；
  - `test_recognize_uhaped_container_frame_goes_to_excluded`（围框被打散成 U 形无洞）。
  - 全文件 39 例通过；相关 API/报告文件 `test_four_color_import_api.py` 等 41 例通过。
- 真实原图（永昇加油站）端到端：**7 → 26 个分区 + 2 个围框排除**；
  25/26 个分区得到 OCR 建议名（发电间/水罐/休息室/办公室/配电室/营业室/值班室/
  卫生间/楼梯间/柴油储罐/甲醇储罐/卸油口/加注机/加油机/洗车机/汽油储罐…）。
- 真接口实测（docker backend :8000，qa 账号）：
  `POST /api/v1/enterprises/{eid}/risk-management/floors/{fid}/four-color/analyze`
  → canvas 1372×1000、zones 26、excluded 2（均为 frame）、schema 校验通过。
- 前端：`tsc -b --force` 通过；`vitest run riskMappingWorkbenchService.test.ts` 通过。

## 6. 已知边界

- 拍照件（斜拍/低对比）描边可能断续导致漏格；兜底退化为"大分区形态"，不会比修复前更差。
- 数字徽章（1~5 圆标）若被描边融合不单独成区；孤立徽章可能仍按实心块成区（与修复前一致）。
- 疑似分区（面积 >5% 且空心）仍走 CLIP 提示，不自动删除。

## 7. 涉及文件

- `backend/app/services/four_color_recognizer.py`（主改动：提取/分类/管线/命名）
- `backend/app/schemas/risk_management.py`（reason 枚举）
- `frontend/src/types/riskMappingWorkbench.ts`、`frontend/src/components/enterprise/riskMapping/FourColorImportModal.tsx`（reason 类型与文案）
- `backend/tests/test_four_color_recognizer.py`（新增用例）
