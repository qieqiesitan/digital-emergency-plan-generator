import { useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spin, Button, Space, message, Alert, Tag } from "antd";
import { DownloadOutlined, PrinterOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getExportPreview, exportDocx, validateExport } from "@/services/exportService";
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
  const { data: validation } = useQuery({
    queryKey: ["exportValidate", id],
    queryFn: () => validateExport(id!),
    enabled: !!id,
  });

  // 质量证据 → 预览正文中高亮标注（「待补充」等片段）
  const evidenceList = useMemo(() => {
    const items: string[] = [];
    for (const w of validation?.warnings ?? []) {
      if (w.evidence) items.push(w.evidence);
    }
    return [...new Set(items)];
  }, [validation]);

  const previewHtml = useMemo(() => {
    let htmlStr = preview?.html || "";
    for (const ev of evidenceList) {
      if (ev && htmlStr.includes(ev)) {
        htmlStr = htmlStr.split(ev).join(`<mark class="quality-issue">${ev}</mark>`);
      }
    }
    return htmlStr;
  }, [preview, evidenceList]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      if (!id) { message.error("预案ID缺失"); return; }
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
      } else if (result && (result as ExportTask).task_id) {
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
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "导出失败";
      console.error("DOCX export error:", e);
      message.error(msg);
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
      {validation && !validation.valid && (
        <Alert
          type="error"
          showIcon
          message="导出前请修复以下问题"
          description={
            <ul>
              {validation.issues.map((i, idx) => (
                <li key={idx}>「{i.section_title}」{i.issue}</li>
              ))}
            </ul>
          }
          action={<Button onClick={() => navigate(`/plans/${id}/edit`)}>去编辑</Button>}
        />
      )}
      {validation && validation.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="质量提示"
          description={
            <ul>
              {validation.warnings.map((w, idx) => (
                <li key={idx}>
                  「{w.section_title}」{w.warning}
                  {w.evidence && <Tag color="orange" style={{ marginLeft: 8 }}>正文定位：{w.evidence}</Tag>}
                </li>
              ))}
            </ul>
          }
          style={{ marginTop: 8 }}
        />
      )}
      <style>{`
        mark.quality-issue {
          background-color: #fff3a8;
          color: #ad6800;
          padding: 0 2px;
          border-radius: 2px;
        }
      `}</style>
      <div className="export-preview-container">
        {isLoading ? (
          <Spin size="large" />
        ) : (
          <MermaidRenderer html={previewHtml} />
        )}
      </div>
    </div>
  );
}
