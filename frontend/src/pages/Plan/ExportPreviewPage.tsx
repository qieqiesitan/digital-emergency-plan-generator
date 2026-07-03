import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spin, Button, Space, message } from "antd";
import { DownloadOutlined, PrinterOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getExportPreview, exportDocx } from "@/services/exportService";
import MermaidRenderer from "@/components/plan/MermaidRenderer";
import type { ExportTask } from "@/types/plan";

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
      if (!id) { message.error("预案ID缺失"); setDownloading(false); return; }
      const result = await exportDocx(id);
      if (result instanceof Blob) {
        const url = URL.createObjectURL(result);
        const a = document.createElement("a");
        a.href = url;
        a.download = (preview?.title || "plan") + ".docx";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        message.success("下载成功");
      } else if ((result as ExportTask).task_id) {
        const task = result as ExportTask;
        if (task.download_url) {
          window.open(task.download_url, "_blank");
          message.success("文档已生成");
        } else {
          message.info("导出任务已提交，请稍后刷新页面下载");
        }
      } else {
        message.error("导出失败：服务器返回异常");
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
