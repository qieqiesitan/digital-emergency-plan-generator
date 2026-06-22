import { useState, useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import { Modal, Button, Space } from "antd";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// 修复 Leaflet 默认图标路径
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

interface GisMapPickerProps {
  value?: { lat: number; lng: number } | null;
  onChange?: (pos: { lat: number; lng: number } | null) => void;
  visible: boolean;
  onClose: () => void;
}

function MapClickHandler({ onClick }: { onClick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function GisMapPicker({ value, onChange, visible, onClose }: GisMapPickerProps) {
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(value || null);

  useEffect(() => {
    if (visible) setPosition(value || null);
  }, [visible, value]);

  const handleConfirm = () => {
    onChange?.(position);
    onClose();
  };

  const defaultCenter: [number, number] = position
    ? [position.lat, position.lng]
    : [39.9042, 116.4074]; // 默认北京

  return (
    <Modal
      title="在地图上点击选择厂区位置"
      open={visible}
      onCancel={onClose}
      width={700}
      footer={[
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="clear" onClick={() => { setPosition(null); }}>清除选点</Button>,
        <Button key="confirm" type="primary" onClick={handleConfirm}>确定</Button>,
      ]}
    >
      <div style={{ height: 400, marginBottom: 8 }}>
        <MapContainer
          center={defaultCenter}
          zoom={13}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapClickHandler onClick={(lat, lng) => setPosition({ lat, lng })} />
          {position && <Marker position={[position.lat, position.lng]} />}
        </MapContainer>
      </div>
      <div style={{ color: "#666", fontSize: 12 }}>
        {position
          ? `已选位置：纬度 ${position.lat.toFixed(6)}, 经度 ${position.lng.toFixed(6)}`
          : "请在地图上点击选择厂区位置"}
      </div>
    </Modal>
  );
}
