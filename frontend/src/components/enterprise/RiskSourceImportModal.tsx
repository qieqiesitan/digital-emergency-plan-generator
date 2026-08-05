import { useState } from "react";
import { Modal, Upload, Button, Table, message, Space, Tag, Alert, Steps } from "antd";
import { DownloadOutlined, UploadOutlined, InboxOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd";
import {
  downloadRiskSourceTemplate,
  previewRiskSourceImport,
  batchCreateRiskSources,
  type ImportPreviewItem,
} from "@/services/riskSourceService";

const { Dragger } = Upload;

interface Props {
  enterpriseId: string;
  visible: boolean;
  onClose: () => void;
  onImported: () => void;
}

type StepKey = "download" | "upload" | "preview";

export default function RiskSourceImportModal({ enterpriseId, visible, onClose, onImported }: Props) {
  const [currentStep, setCurrentStep] = useState<StepKey>("download");
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [previewItems, setPreviewItems] = useState<ImportPreviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  const handleDownload = async () => {
    await downloadRiskSourceTemplate(enterpriseId);
    message.success("模板已下载，请按格式填写后上传");
    setCurrentStep("upload");
  };

  const handleUpload = async () => {
    if (!fileList[0]?.originFileObj) return;
    setLoading(true);
    try {
      const result = await previewRiskSourceImport(enterpriseId, fileList[0].originFileObj as File);
      setPreviewItems(result.items);
      setCurrentStep("preview");
    } catch {
      message.error("文件解析失败，请确认上传的是正确的模板文件");
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    const validItems = previewItems.filter((i) => i.errors.length === 0).map((i) => i.data);
    if (validItems.length === 0) {
      message.warning("没有可导入的有效数据");
      return;
    }
    setImporting(true);
    try {
      await batchCreateRiskSources(enterpriseId, validItems);
      message.success(`成功导入 ${validItems.length} 个风险源`);
      onImported();
      resetAll();
    } catch {
      message.error("导入失败");
    } finally {
      setImporting(false);
    }
  };

  const resetAll = () => {
    setCurrentStep("download");
    setFileList([]);
    setPreviewItems([]);
    onClose();
  };

  const validCount = previewItems.filter((i) => i.errors.length === 0).length;
  const errorCount = previewItems.filter((i) => i.errors.length > 0).length;

  const previewColumns = [
    { title: "行", dataIndex: "row", width: 60 },
    {
      title: "风险类别",
      dataIndex: ["data", "categories"],
      render: (cats: string[]) => (
        <Space size={4} wrap>
          {cats?.map((c) => <Tag key={c} color="orange">{c}</Tag>)}
        </Space>
      ),
    },
    {
      title: "风险名称",
      dataIndex: ["data", "name"],
      render: (v: string, record: ImportPreviewItem) => (
        <span style={record.errors.length > 0 ? { color: "#ff4d4f" } : undefined}>{v || "-"}</span>
      ),
    },
    { title: "位置", dataIndex: ["data", "location"], render: (v: string) => v || "-" },
    { title: "可能性", dataIndex: ["data", "likelihood"], width: 80, render: (v: string) => v || "中" },
    { title: "严重性", dataIndex: ["data", "severity"], width: 80, render: (v: string) => v || "中" },
    {
      title: "错误",
      dataIndex: "errors",
      render: (errs: string[]) =>
        errs.length > 0 ? (
          <span style={{ color: "#ff4d4f" }}>{errs.join("；")}</span>
        ) : (
          <Tag color="green">通过</Tag>
        ),
    },
  ];

  const steps = [
    { title: "下载模板", description: "获取Excel模板文件" },
    { title: "上传文件", description: "上传填写好的模板" },
    { title: "预览确认", description: "检查数据并导入" },
  ];

  const stepIndex = currentStep === "download" ? 0 : currentStep === "upload" ? 1 : 2;

  return (
    <Modal
      title="导入风险源"
      open={visible}
      onCancel={resetAll}
      width={900}
      footer={
        currentStep === "preview"
          ? [
              <Button key="back" onClick={() => { setCurrentStep("upload"); setFileList([]); }}>
                重新上传
              </Button>,
              <Button key="import" type="primary" loading={importing} disabled={validCount === 0} onClick={handleImport}>
                确认导入 ({validCount} 条)
              </Button>,
            ]
          : null
      }
    >
      <Steps current={stepIndex} items={steps} size="small" style={{ marginBottom: 24 }} />

      {currentStep === "download" && (
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <Alert
            type="info"
            message="第一步：下载模板"
            description="下载包含下拉校验的 Excel 模板，按格式填写企业的风险源数据。每行一个风险源，类别/可能性/严重性可从下拉列表中选取。"
            style={{ marginBottom: 24, textAlign: "left" }}
            showIcon
          />
          <Button type="primary" size="large" icon={<DownloadOutlined />} onClick={handleDownload}>
            下载风险源模板 (.xlsx)
          </Button>
          <div style={{ marginTop: 16, color: "#999" }}>下载后请用 Excel 打开并填写，然后进入下一步上传</div>
        </div>
      )}

      {currentStep === "upload" && (
        <div>
          <Alert
            type="info"
            message="第二步：上传已填好的文件"
            description="将填写完成的模板文件上传，系统会自动解析并校验每一行数据。"
            style={{ marginBottom: 16 }}
            showIcon
          />
          <Dragger
            fileList={fileList}
            accept=".xlsx"
            maxCount={1}
            beforeUpload={() => false}
            onChange={({ fileList: fl }) => setFileList(fl)}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p>点击或拖拽上传已填好的 .xlsx 文件</p>
          </Dragger>
          <div style={{ marginTop: 16, textAlign: "right" }}>
            <Space>
              <Button onClick={() => setCurrentStep("download")}>返回下载模板</Button>
              <Button type="primary" icon={<UploadOutlined />} onClick={handleUpload} loading={loading} disabled={!fileList[0]}>
                解析文件
              </Button>
            </Space>
          </div>
        </div>
      )}

      {currentStep === "preview" && (
        <div>
          {errorCount > 0 && (
            <Alert
              type="warning"
              message={`共 ${previewItems.length} 条数据，${validCount} 条有效、${errorCount} 条有错误。有错误的行将跳过不导入。`}
              style={{ marginBottom: 12 }}
              showIcon
            />
          )}
          {errorCount === 0 && (
            <Alert
              type="success"
              message={`共 ${validCount} 条有效数据，确认后将导入数据库`}
              style={{ marginBottom: 12 }}
              showIcon
            />
          )}
          <Table
            dataSource={previewItems}
            rowKey="row"
            columns={previewColumns}
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
        </div>
      )}
    </Modal>
  );
}
