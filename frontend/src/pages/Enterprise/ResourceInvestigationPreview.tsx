import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spin, Button, message } from "antd";
import { ArrowLeftOutlined, DownloadOutlined } from "@ant-design/icons";
import { getResourceInvestigationPreview, downloadResourceInvestigation } from "@/services/resourceInvestigationService";
import type { ResourceInvestigationPreview as RIPreview } from "@/types/resourceInvestigation";

export default function ResourceInvestigationPreview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<RIPreview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getResourceInvestigationPreview(id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [id]);

  const handleExport = async () => {
    if (id) {
      try {
        await downloadResourceInvestigation(id);
      } catch (err: any) {
        message.error(err.message || "download failed");
      }
    }
  };

  if (loading) return <Spin size="large" />;
  if (!data) return <div>报告不存在</div>;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/enterprises/${id}`)}>
          返回企业详情
        </Button>
        <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport}>
          下载 Word
        </Button>
      </div>
      <div
        style={{
          background: "#fff",
          padding: "60px 80px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          maxWidth: 794,
          margin: "0 auto",
        }}
        dangerouslySetInnerHTML={{ __html: data.html }}
      />
    </div>
  );
}
