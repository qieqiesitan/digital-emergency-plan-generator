import { useState } from "react";
import axios from "axios";
import { Drawer, Upload, message } from "antd";
import { importOnboardingBatch } from "@/services/onboardingService";

interface Props {
  enterpriseId: string;
  open: boolean;
  onClose: () => void;
  onImported: (items: unknown[]) => void;
}

export default function ImportDrawer({ enterpriseId, open, onClose, onImported }: Props) {
  const [uploading, setUploading] = useState(false);
  return (
    <Drawer title="导入现有数据" open={open} onClose={onClose} width={520}>
      <p style={{ color: "#666", fontSize: 13 }}>
        支持 .xlsx / .csv / .docx / .pdf，AI 自动提取为候选供核对；也可上传多个文件作为「资料包」自动分流。
      </p>
      <Upload.Dragger
        multiple
        accept=".xlsx,.csv,.docx,.pdf,.txt"
        beforeUpload={async (file) => {
          setUploading(true);
          try {
            const result = await importOnboardingBatch(enterpriseId, [file as unknown as File]);
            const items = result.flatMap(r => r.candidates || []);
            onImported(items);
            message.success(`已提取 ${items.length} 条候选`);
          } catch (e: unknown) {
            const err = e as { response?: { data?: { detail?: unknown } } };
            const detail = axios.isAxiosError(e) ? e.response?.data?.detail : err?.response?.data?.detail;
            const fallbackMsg = (e as Error | undefined)?.message || "导入失败";
            message.error(typeof detail === "string" ? detail : fallbackMsg);
          } finally {
            setUploading(false);
          }
          return false;
        }}
        showUploadList={false}
      >
        <p>点击或拖拽文件到这里</p>
        <p style={{ color: "#999", fontSize: 12 }}>
          {uploading ? "AI 分析提取中…" : "资料包（多文件）将自动识别并分流到各步骤"}
        </p>
      </Upload.Dragger>
    </Drawer>
  );
}
