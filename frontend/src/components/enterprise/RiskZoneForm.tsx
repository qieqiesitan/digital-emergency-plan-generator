import { useState, useRef, useCallback } from "react";
import { Drawer, Form, Input, Button, Modal, Space } from "antd";
import { EnvironmentOutlined, DeleteOutlined } from "@ant-design/icons";
import { mergeEditedPolygon } from "@/utils/zoneSubmit";

interface PolygonPoint { x: number; y: number }

interface RiskZoneFormValues {
  name: string;
  description?: string;
  floor_plan_polygon?: {
    version: 2;
    color_source: "auto" | "manual";
    color: string | null;
    polygons: { id: string; label?: string; points: PolygonPoint[] }[];
  };
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: RiskZoneFormValues) => void;
  initialValues?: RiskZoneFormValues;
  floorPlanUrl?: string | null;
}

export default function RiskZoneForm({ open, onClose, onSubmit, initialValues, floorPlanUrl }: Props) {
  const [form] = Form.useForm<RiskZoneFormValues>();
  const [polygonOpen, setPolygonOpen] = useState(false);
  const [polygonPoints, setPolygonPoints] = useState<PolygonPoint[]>([]);
  const [existingRegionCount, setExistingRegionCount] = useState(0);
  const imgRef = useRef<HTMLImageElement>(null);

  const handleOpen = () => {
    const existing = form.getFieldValue("floor_plan_polygon");
    setPolygonPoints(existing?.polygons?.[0]?.points ?? (existing as { points?: PolygonPoint[] } | undefined)?.points ?? []);
    setExistingRegionCount(existing?.polygons?.length ?? 0);
    setPolygonOpen(true);
  };

  const handlePolygonConfirm = () => {
    const existing = form.getFieldValue("floor_plan_polygon");
    form.setFieldsValue({
      floor_plan_polygon: mergeEditedPolygon(existing, form.getFieldValue("name"), polygonPoints),
    });
    setPolygonOpen(false);
  };

  const handleImageClick = useCallback((e: React.MouseEvent<HTMLImageElement>) => {
    if (!imgRef.current) return;
    const rect = imgRef.current.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 10000) / 100;
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 10000) / 100;
    setPolygonPoints((prev) => [...prev, { x, y }]);
  }, []);

  const handleUndoPoint = () => {
    setPolygonPoints((prev) => prev.slice(0, -1));
  };

  const handleFinish = (values: RiskZoneFormValues) => {
    onSubmit(values);
  };

  const polyStr = polygonPoints.length > 0
    ? `${polygonPoints.length} 个顶点`
    : "未标注";

  return (
    <>
      <Drawer
        title={initialValues ? "编辑风险分区" : "新增风险分区"}
        open={open}
        onClose={onClose}
        width={520}
        extra={
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" onClick={() => form.submit()}>
              保存
            </Button>
          </Space>
        }
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={handleFinish}
        >
          <Form.Item
            name="name"
            label="分区名称"
            rules={[{ required: true, message: "请输入分区名称" }]}
          >
            <Input placeholder="如储罐区" />
          </Form.Item>

          <Form.Item name="description" label="描述说明">
            <Input.TextArea rows={4} placeholder="请描述该分区的范围、用途等" />
          </Form.Item>

          <Form.Item name="floor_plan_polygon" label="平面图标注" hidden>
            <Input />
          </Form.Item>

          {floorPlanUrl ? (
            <div style={{ marginBottom: 16 }}>
              <Button
                icon={<EnvironmentOutlined />}
                onClick={handleOpen}
                block
              >
                在平面图上标注
              </Button>
              <div style={{ marginTop: 4, color: "#999", fontSize: 12 }}>
                当前: {polyStr}
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: 16, color: "#999", fontSize: 12 }}>
              未上传平面图，无法标注
            </div>
          )}
        </Form>
      </Drawer>

      {/* fullscreen polygon drawing overlay */}
      <Modal
        title="在平面图上点击绘制多边形区域"
        open={polygonOpen}
        onCancel={() => setPolygonOpen(false)}
        width="90vw"
        style={{ top: 20 }}
        footer={[
          <Button key="undo" icon={<DeleteOutlined />} onClick={handleUndoPoint} disabled={polygonPoints.length === 0}>
            撤销顶点
          </Button>,
          <Button key="cancel" onClick={() => setPolygonOpen(false)}>取消</Button>,
          <Button key="confirm" type="primary" onClick={handlePolygonConfirm}>确定</Button>,
        ]}
      >
        {!floorPlanUrl ? (
          <div style={{ textAlign: "center", padding: 60, color: "#999" }}>
            未上传平面图
          </div>
        ) : (
          <div
            style={{
              position: "relative",
              border: "1px solid #d9d9d9",
              borderRadius: 4,
              overflow: "hidden",
              cursor: "crosshair",
              background: "#f5f5f5",
            }}
          >
            <img
              ref={imgRef}
              src={floorPlanUrl}
              alt="厂区平面图"
              style={{ width: "100%", display: "block", userSelect: "none" }}
              draggable={false}
              onClick={handleImageClick}
            />
            {/* draw polygon */}
            {polygonPoints.length >= 3 && (
              <svg
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  pointerEvents: "none",
                }}
              >
                <polygon
                  points={polygonPoints.map((p) => `${p.x}%,${p.y}%`).join(" ")}
                  fill="rgba(255,77,79,0.2)"
                  stroke="#ff4d4f"
                  strokeWidth={2}
                />
              </svg>
            )}
            {/* draw vertex markers */}
            {polygonPoints.map((p, i) => (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: `${p.x}%`,
                  top: `${p.y}%`,
                  transform: "translate(-50%, -50%)",
                  pointerEvents: "none",
                  zIndex: 10,
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: "#ff4d4f",
                  border: "2px solid #fff",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
                }}
              />
            ))}
          </div>
        )}
        <div style={{ color: "#999", fontSize: 12, marginTop: 8 }}>
          {polygonPoints.length === 0
            ? "请点击平面图添加多边形顶点（至少3个点）"
            : `已标记 ${polygonPoints.length} 个顶点${polygonPoints.length < 3 ? "（至少需要3个点才能形成区域）" : ""}`}
        </div>
        {existingRegionCount > 1 && (
          <div style={{ color: "#faad14", fontSize: 12, marginTop: 4 }}>
            该分区包含 {existingRegionCount} 个区域，本次仅更新当前编辑区域，其余区域将保留。
          </div>
        )}
      </Modal>
    </>
  );
}
