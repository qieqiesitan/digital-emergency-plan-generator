import { useState } from "react";
import { Drawer, Upload, message } from "antd";
import type { UploadFile } from "antd";
import {
  importOnboardingBatch,
  importOnboardingFile,
} from "@/services/onboardingService";
import type { ImportResult } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  open: boolean;
  /** package=资料包（一次多文件自动分流）；single=定点单文件导入（需 module） */
  mode: "package" | "single";
  /** single 模式目标模块（enterprise_info/org_structure/risk_chemical/resources/surrounding） */
  module?: string;
  onClose: () => void;
  onImported: (results: ImportResult[]) => void;
}

function errorMessage(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const resp = (e as { response?: { data?: { detail?: unknown } } }).response;
    const detail = resp?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return e instanceof Error && e.message ? e.message : "导入失败";
}

export default function ImportDrawer({
  enterpriseId,
  open,
  mode,
  module,
  onClose,
  onImported,
}: Props) {
  const [uploading, setUploading] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const isPackage = mode === "package";

  const handleFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setUploading(true);
    try {
      if (isPackage) {
        // 资料包：一次请求走 batch 分流，不做逐文件 N 次并发
        const results = await importOnboardingBatch(enterpriseId, files);
        if (results.length === 0) {
          message.warning("未能从这些文件中识别出企业数据模块，可改用各步骤「导入现有数据」定点导入");
          return; // 保持抽屉打开，便于更换文件重试
        } else {
          const count = results.reduce((n, r) => n + (r.candidates || []).length, 0);
          // 单文件可识别出多模块：按来源文件集合计算实际识别数，避免 skipped 为负数
          const recognizedFiles = new Set(results.map(r => r.source)).size;
          const skipped = files.length - recognizedFiles;
          onImported(results);
          message.success(
            `已提取 ${count} 条候选，分流至 ${results.length} 个模块` +
              (skipped > 0 ? `，${skipped} 个文件未识别模块已跳过` : ""),
          );
          onClose();
        }
      } else {
        const targetModule = module || "auto";
        const result = await importOnboardingFile(enterpriseId, targetModule, files[0]);
        const items = result.candidates || [];
        if (items.length === 0) {
          message.warning("未从该文件中提取到候选，请检查文件内容或换一个文件");
          return; // 保持抽屉打开，便于更换文件重试
        } else {
          onImported([result]);
          message.success(`已提取 ${items.length} 条候选，来源：${result.source}`);
          onClose();
        }
      }
    } catch (e: unknown) {
      message.error(errorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <Drawer
      title={isPackage ? "导入企业资料包" : "导入现有数据"}
      open={open}
      onClose={onClose}
      afterOpenChange={nextOpen => {
        // 抽屉重开时清空上次残留的文件，避免旧文件影响新一次导入
        if (nextOpen) setFileList([]);
      }}
      width={520}
    >
      <p style={{ color: "#666", fontSize: 13 }}>
        支持 .xlsx / .csv / .docx / .pdf / .txt，AI 自动提取为候选供逐条核对；
        {isPackage
          ? "可一次上传多个文件，自动识别模块并分流到各步骤候选区。"
          : "导入结果将进入本步骤候选区（标注来源文件与行号）。"}
      </p>
      <Upload.Dragger
        multiple={isPackage}
        accept=".xlsx,.csv,.docx,.pdf,.txt"
        fileList={fileList}
        beforeUpload={(file, fileList) => {
          // beforeUpload 逐文件触发；仅第一个文件触发整批处理，避免重复请求
          if (file.uid === fileList[0]?.uid) {
            void handleFiles(fileList as unknown as File[]);
          }
          return false;
        }}
        onChange={({ fileList: next }) => setFileList(next)}
        showUploadList={false}
      >
        <p>点击或拖拽文件到这里</p>
        <p style={{ color: "#999", fontSize: 12 }}>
          {uploading
            ? "AI 分析提取中，通常需要 1-2 分钟，请耐心等待…"
            : isPackage
              ? "资料包（多文件）将自动识别并分流到各步骤"
              : "单文件将定点提取到当前步骤候选区"}
        </p>
      </Upload.Dragger>
    </Drawer>
  );
}
