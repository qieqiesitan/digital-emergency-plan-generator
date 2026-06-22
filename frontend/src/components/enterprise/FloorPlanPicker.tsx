import { useState, useRef, useEffect, useCallback } from "react";
import { Modal, Button, Input } from "antd";
import { EnvironmentOutlined } from "@ant-design/icons";

interface FloorPlanPickerProps {
  /** 厂区平面图 URL（由企业信息提供） */
  imageUrl: string | null;
  /** 当前已选坐标和描述 */
  value?: { x: number | null; y: number | null; description: string };
  /** 确认回调 */
  onChange?: (val: { x: number | null; y: number | null; description: string }) => void;
  visible: boolean;
  onClose: () => void;
}

export default function FloorPlanPicker({ imageUrl, value, onChange, visible, onClose }: FloorPlanPickerProps) {
  const [marker, setMarker] = useState<{ x: number; y: number } | null>(null);
  const [desc, setDesc] = useState("");
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (visible) {
      if (value?.x != null && value?.y != null) {
        setMarker({ x: value.x, y: value.y });
      } else {
        setMarker(null);
      }
      setDesc(value?.description || "");
    }
  }, [visible, value]);

  const handleImageClick = useCallback((e: React.MouseEvent<HTMLImageElement>) => {
    if (!imgRef.current) return;
    const rect = imgRef.current.getBoundingClientRect();
    // 计算相对于图片的百分比坐标
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setMarker({ x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 });
  }, []);

  const handleConfirm = () => {
    onChange?.({
      x: marker?.x ?? null,
      y: marker?.y ?? null,
      description: desc,
    });
    onClose();
  };

  return (
    <Modal
      title="在厂区平面图上点选风险源位置"
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="clear" onClick={() => { setMarker(null); setDesc(""); }}>清除标记</Button>,
        <Button key="confirm" type="primary" onClick={handleConfirm}>确定</Button>,
      ]}
    >
      {!imageUrl ? (
        <div style={{ textAlign: "center", padding: 60, color: "#999" }}>
          尚未上传厂区平面图，请先在"编辑企业"中上传。
        </div>
      ) : (
        <>
          <div
            ref={containerRef}
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
              src={imageUrl}
              alt="厂区平面图"
              style={{ width: "100%", display: "block", userSelect: "none" }}
              draggable={false}
              onClick={handleImageClick}
            />
            {marker && (
              <div
                style={{
                  position: "absolute",
                  left: `${marker.x}%`,
                  top: `${marker.y}%`,
                  transform: "translate(-50%, -100%)",
                  pointerEvents: "none",
                  zIndex: 10,
                }}
              >
                <EnvironmentOutlined style={{ fontSize: 28, color: "#ff4d4f", filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.3))" }} />
              </div>
            )}
          </div>
          <div style={{ marginTop: 12 }}>
            <Input.TextArea
              placeholder="请输入该风险源的位置描述（如：3号车间东北角）"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={2}
            />
          </div>
          <div style={{ color: "#999", fontSize: 12, marginTop: 4 }}>
            {marker
              ? `已标记位置（${marker.x}%, ${marker.y}%）`
              : "请在平面图上点击风险源的准确位置"}
          </div>
        </>
      )}
    </Modal>
  );
}
