import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Card, message, Space, Spin } from "antd";
import { DeleteOutlined, EnvironmentOutlined, UploadOutlined } from "@ant-design/icons";
import axios from "axios";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateEnterprise, uploadFile } from "@/services/enterpriseService";
import type { EnterpriseUpdate } from "@/types/enterprise";
import { PageHeader } from "@/components/common/PageHeader";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import GisMapPicker from "@/components/enterprise/GisMapPicker";

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

export default function EnterpriseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [gisModalOpen, setGisModalOpen] = useState(false);
  const [gisPos, setGisPos] = useState<{ lat: number; lng: number } | null>(null);
  const [gisCleared, setGisCleared] = useState(false);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const [floorPlanCleared, setFloorPlanCleared] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);

  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });
  const mutation = useMutation({
    mutationFn: (values: EnterpriseUpdate) => updateEnterprise(id!, values),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["enterprise", id] });
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      navigate(`/enterprises/${id}`);
    },
    onError: (err: unknown) => message.error(extractDetail(err) || "保存失败"),
  });

  if (isLoading) return <Spin size="large" />;

  const existingGis =
    enterprise?.gis_lat != null && enterprise?.gis_lng != null
      ? { lat: enterprise.gis_lat, lng: enterprise.gis_lng }
      : null;
  const effectiveGis = gisCleared ? null : (gisPos ?? existingGis);
  const effectiveFloorPlan = floorPlanCleared ? null : (floorPlanUrl ?? enterprise?.floor_plan_url ?? null);

  const handleUpload = async (file: File) => {
    try {
      const url = await uploadFile(file);
      setFloorPlanUrl(url);
      setFloorPlanCleared(false);
      message.success("平面图上传成功");
    } catch {
      message.error("平面图上传失败");
    }
  };

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="编辑企业" onBack={() => navigate(`/enterprises/${id}`)} />
      <EnterpriseInfoCards
        enterprise={enterprise}
        onSaved={async (values) => {
          const payload = values as unknown as EnterpriseUpdate;
          mutation.mutate({
            ...payload,
            gis_lat: effectiveGis?.lat ?? null,
            gis_lng: effectiveGis?.lng ?? null,
            floor_plan_url: effectiveFloorPlan,
          });
        }}
      />
      <Card title="GIS 定位与平面图" size="small" style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>厂区平面图</div>
          <input
            ref={uploadRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
            }}
          />
          <Button icon={<UploadOutlined />} onClick={() => uploadRef.current?.click()}>
            上传厂区平面图
          </Button>
          {effectiveFloorPlan && (
            <div style={{ position: "relative", display: "inline-block", marginLeft: 12 }}>
              <img
                src={effectiveFloorPlan}
                alt="平面图预览"
                style={{ maxWidth: 300, maxHeight: 150, border: "1px solid #d9d9d9", borderRadius: 4 }}
              />
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                style={{ position: "absolute", top: 0, right: 0 }}
                onClick={() => {
                  setFloorPlanUrl(null);
                  setFloorPlanCleared(true);
                  if (uploadRef.current) uploadRef.current.value = "";
                }}
              />
            </div>
          )}
        </div>
        <div>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>GIS 坐标</div>
          <Space>
            <Button icon={<EnvironmentOutlined />} onClick={() => setGisModalOpen(true)}>
              {effectiveGis ? "重新选择厂区位置" : "在地图上选择厂区位置"}
            </Button>
            {effectiveGis && (
              <span style={{ color: "#666", fontSize: 13 }}>
                已选：{effectiveGis.lat.toFixed(6)}, {effectiveGis.lng.toFixed(6)}
              </span>
            )}
          </Space>
        </div>
      </Card>
      <GisMapPicker
        visible={gisModalOpen}
        value={effectiveGis}
        onChange={(pos) => {
          if (pos) {
            setGisPos(pos);
            setGisCleared(false);
          } else {
            setGisPos(null);
            setGisCleared(true);
          }
        }}
        onClose={() => setGisModalOpen(false)}
      />
    </div>
  );
}
