import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, message, Space } from "antd";
import { DeleteOutlined, UploadOutlined } from "@ant-design/icons";
import AppIcon from "@/components/common/AppIcon";
import axios from "axios";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createEnterprise, uploadFile } from "@/services/enterpriseService";
import type { EnterpriseCreate } from "@/types/enterprise";
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

export default function EnterpriseCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [gisModalOpen, setGisModalOpen] = useState(false);
  const [gisPos, setGisPos] = useState<{ lat: number; lng: number } | null>(null);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: createEnterprise,
    onSuccess: (data) => {
      message.success("企业创建成功");
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      // 引导按企业维度进行（每个企业创建后都进入引导，可从引导页「稍后继续」离开）
      navigate(`/onboarding?enterprise_id=${data.id}`);
    },
    onError: (err: unknown) => message.error(extractDetail(err) || "创建失败"),
  });

  const handleUpload = async (file: File) => {
    try {
      const url = await uploadFile(file);
      setFloorPlanUrl(url);
      message.success("平面图上传成功");
    } catch {
      message.error("平面图上传失败");
    }
  };

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="新建企业" onBack={() => navigate("/enterprises")} />
      <EnterpriseInfoCards
        onCreate={async (values) => {
          const payload = values as unknown as EnterpriseCreate;
          mutation.mutate({
            ...payload,
            gis_lat: gisPos?.lat ?? null,
            gis_lng: gisPos?.lng ?? null,
            floor_plan_url: floorPlanUrl ?? null,
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
          {floorPlanUrl && (
            <div style={{ position: "relative", display: "inline-block", marginLeft: 12 }}>
              <img
                src={floorPlanUrl}
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
                  if (uploadRef.current) uploadRef.current.value = "";
                }}
              />
            </div>
          )}
        </div>
        <div>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>GIS 坐标</div>
          <Space>
            <Button icon={<AppIcon name="location" size={14} />} onClick={() => setGisModalOpen(true)}>
              在地图上选择厂区位置
            </Button>
            {gisPos && (
              <span style={{ color: "#666", fontSize: 13 }}>
                已选：{gisPos.lat.toFixed(6)}, {gisPos.lng.toFixed(6)}
              </span>
            )}
          </Space>
        </div>
      </Card>
      <GisMapPicker
        visible={gisModalOpen}
        value={gisPos}
        onChange={(pos) => setGisPos(pos)}
        onClose={() => setGisModalOpen(false)}
      />
    </div>
  );
}
