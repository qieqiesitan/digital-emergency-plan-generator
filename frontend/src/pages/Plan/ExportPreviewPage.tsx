import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spin, Button, Space, message } from "antd";
import { DownloadOutlined, PrinterOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getExportPreview } from "@/services/exportService";
import MermaidRenderer from "@/components/plan/MermaidRenderer";

export default function ExportPreviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState(false);
  const { data: preview, isLoading } = useQuery({
    queryKey: ["exportPreview", id],
    queryFn: () => getExportPreview(id!),
    enabled: !!id,
  });

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const token = localStorage.getItem("access_token");
      const resp = await fetch("/api/v1/plans/" + id + "/export/docx", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = (preview?.title || "plan") + ".docx";
        a.click();
        URL.revokeObjectURL(url);
        message.success("下载成功");
      } else {
        message.error("导出失败");
      }
    } catch {
      message.error("导出失败");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 100px)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/plans/" + id + "/edit")}>
          返回编辑
        </Button>
        <Space>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>
            打印
          </Button>
          <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownload} loading={downloading}>
            下载 .docx
          </Button>
        </Space>
      </div>
      <div className="export-preview-container">
        {isLoading ? (
          <Spin size="large" />
        ) : (
          <MermaidRenderer html={preview?.html || ""} />
        )}
      </div>
    </div>
  );
}
