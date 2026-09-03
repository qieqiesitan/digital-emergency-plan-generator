# 风险评估报告附四色分布图 设计

日期：2026-09-03
状态：已获用户逐节批准（B2：插在「二、危险有害因素辨识汇总」之后；B：草稿阶段即带图）
范围：风险评估报告（桌面 Web）；资源调查报告不插图

## 1. 背景与目标

风险评估报告应展示企业风险分级管控的“四色分布图”与风险源点位，使报告图文结合。
已确认：图随全量生成在草稿阶段出现；正式内容中图位于「二、危险有害因素辨识汇总」
与「三、风险等级评估」之间；Word 导出与预览页均可见。

## 2. 非目标

- 不把图片做成可编辑章节内容（图块只读展示）。
- 单章重新生成不重渲染图片（图片只在全量 generate 时刷新）。
- 资源调查报告不加图。
- 不改动风险管控前端画布（WorkbenchCanvas）本身。

## 3. 数据与渲染规格

每楼层一张 PNG：

- 画布 1200×900（与前端工作台一致）。
- 有楼层底图（`floor_plan_url`）先铺底（缩放铺满画布），无底图白底。
- 分区：`RiskZone.floor_plan_polygon.polygons[].points` 百分比坐标 → 像素；
  填充 `effective_color`（复用风险管控的色值计算，不另立色表），半透明填充 +
  描边 + 区域名标签。
- 风险源点位：`RiskObject(is_risk_point=True)` 的 `location_x/location_y`
  （百分比）画圆点 + 名称（字号 11）。
- 右下角四色图例（重大/较大/一般/低）；图上角标题“{楼层名} 四色分布图”。
- 中文字体：优先文泉驿正黑（容器已装
  `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`），候选列表兜底；找不到字体时
  跳过文字绘制不崩溃。

## 4. 后端改动

新建 `backend/app/services/report_four_color_service.py`：

```python
async def render_enterprise_four_color_images(enterprise_id: str, db) -> list[dict]:
    """按楼层渲染四色分布图 PNG，写入 uploads，返回
    [{floor_id, floor_name, url}]；无分区/点位时返回 []。"""
```

- 直接查询 `EnterpriseFloor / RiskZone / RiskObject`；zone 颜色复用
  `risk_management.py` 现有 `effective_color` 计算（提取为可复用函数或同源调用）。
- PNG 路径：`backend/uploads/enterprises/{enterprise_id}/four-color/{floor_id}.png`，
  url：`/uploads/enterprises/{enterprise_id}/four-color/{floor_id}.png`（现有静态挂载）。

修改 `backend/app/routers/risk_assessment.py`：

1. 全量 `generate` 逐章完成后调用渲染服务，把结果写入
   `report.summary["images"]`（draft 即带图）；失败仅记日志不阻断生成。
2. `merge` 拼 content 时，在「二、…辨识汇总」章节与「三、…风险等级评估」标题之间
   插入 Markdown 图片行（每层一张）：

```markdown
![{楼层名} 四色分布图](/uploads/enterprises/{eid}/four-color/{floor_id}.png)
```

3. `_render_content_to_docx` 识别 `![标题](url)` 行：
   - url 以 `/uploads/` 开头 → 映射本地文件（`UPLOAD_DIR + 相对路径`）并
     `add_picture`（页宽 90%、居中），标题作题注；
   - 文件缺失或非本地上传路径 → 跳过该行不崩溃。

## 5. 前端改动

- `types/reportWorkspace.ts`：`ReportDocument` 增加
  `fourColorImages?: Array<{ floor_id: string; floor_name: string; url: string }>`。
- `services/reportAdapters.ts` load：透传 `report.summary?.images`。
- `components/report/ReportWorkspace.tsx`：
  - 选中章节为风险评估「二、…辨识汇总」（key `ch2_summary`）时，编辑器下方展示
    只读图块（图 + 楼层名；支持点击放大）；
  - 全量生成 `batch_done` 后重新 `load()` 刷新图片列表；
  - `fourColorImages` 为空时不渲染图块。

## 6. 错误处理

- 渲染失败/无数据：记录日志并返回空列表；生成/合并不中断。
- docx 图片缺失：跳过图片行。
- 字体缺失：跳过文字绘制，多边形仍上色。

## 7. 测试策略（TDD）

后端：

- 图片行插入定位纯函数：markdown 中「辨识汇总」与「风险等级评估」标题之间插入；
  标题缺失/重复时行为确定（重复则插到最后一个标题前，缺失则追加到报告末尾或跳过）。
- `_render_content_to_docx` 图片行解析辅助：`/uploads/` 映射与缺失跳过。
- 渲染服务：最小 fixture（1 层 + 1 分区 + 1 点位）调用后返回列表、PNG 存在且尺寸
  1200×900（写入临时目录）。

前端：tsc + vitest；新增纯逻辑如有则抽函数单测。

手工验收：重新生成风险评估报告 → 草稿「辨识汇总」下方出现图；合并 → 预览含图；
导出 Word 含图（尺寸、中文题注正常）；无图企业不报错。

## 8. 已确认决策

- 图片位置：ch2 与 ch3 之间（正文内，非文末附录）。
- 生成时机：全量 generate 完成即渲染并记录（草稿带图）；merge 时固化进 content。
- 图数量：按楼层一张；标题含楼层名。
- 图上内容：底图（有则叠加）+ 四色分区 + 区域名 + 风险源点位名称 + 图例。
- 仅风险评估报告接入。
