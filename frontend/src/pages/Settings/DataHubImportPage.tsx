import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Descriptions,
  Result,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
  Upload,
} from "antd";
import type { TableColumnsType } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { PageHeader } from "@/components/common/PageHeader";
import { parseFile, runExtraction, suggestMapping } from "@/services/extractionService";
import { createJob, createSource } from "@/services/ingestService";
import { extractTableHeaders } from "@/utils/ingestPayload";

const { Dragger } = Upload;
const { Text, Paragraph } = Typography;

interface EntityMeta {
  value: string;
  label: string;
  /** 与后端 ENTITY_SCHEMAS[entity]["fields"] 对齐 */
  fields: string[];
  required: string[];
}

const ENTITIES: EntityMeta[] = [
  {
    value: "major_hazard_unit",
    label: "重大危险源单元",
    fields: ["name", "unit_type", "boundary_desc", "address"],
    required: ["name", "unit_type"],
  },
  {
    value: "major_hazard_unit_chemical",
    label: "单元内危险化学品存量",
    fields: ["unit_name", "chemical_name", "q_design_max", "physical_state"],
    required: ["chemical_name", "q_design_max"],
  },
];

const FIELD_LABELS: Record<string, string> = {
  name: "单元名称",
  unit_type: "单元类型",
  boundary_desc: "边界描述",
  address: "所在位置",
  unit_name: "归属单元名称",
  chemical_name: "危险化学品名称",
  q_design_max: "设计最大量(吨)",
  physical_state: "物理状态",
};

const TABLE_EXT = ["xlsx", "csv"];

const isTableFile = (filename: string) =>
  TABLE_EXT.includes(filename.split(".").pop()?.toLowerCase() ?? "");

interface ParsedFile {
  filename: string;
  chars: number;
  text: string;
}

interface ExtractionResult {
  queued: number;
  skipped: number;
  invalid: number;
}

const errorText = (err: unknown): string => {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  return err instanceof Error ? err.message : "操作失败，请稍后重试";
};

export default function DataHubImportPage() {
  const navigate = useNavigate();
  const { message } = AntApp.useApp();

  const [step, setStep] = useState(0);
  const [entity, setEntity] = useState<EntityMeta>(ENTITIES[0]);
  const [parsed, setParsed] = useState<ParsedFile | null>(null);
  const [parsing, setParsing] = useState(false);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mappingSource, setMappingSource] = useState<"ai" | "exact" | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const tableFile = parsed !== null && isTableFile(parsed.filename);
  const runStep = tableFile ? 3 : 2;
  const unmappedRequired = entity.required.filter((f) => !Object.values(mapping).includes(f));

  const steps = [
    { title: "选目标实体" },
    { title: "上传文件" },
    ...(tableFile ? [{ title: "确认映射" }] : []),
    { title: "触发抽取" },
  ];

  const reset = () => {
    setStep(0);
    setParsed(null);
    setHeaders([]);
    setMapping({});
    setMappingSource(null);
    setResult(null);
    setJobId(null);
    setError(null);
  };

  const handleParse = async (file: File) => {
    setParsing(true);
    setError(null);
    setResult(null);
    setJobId(null);
    try {
      const out = await parseFile(file);
      setParsed(out);
      const cols = isTableFile(out.filename) ? extractTableHeaders(out.text) : [];
      setHeaders(cols);
      if (cols.length) {
        const suggested = await suggestMapping(cols, entity.value);
        setMapping(suggested.mapping);
        setMappingSource(suggested.source);
      } else {
        setMapping({});
        setMappingSource(null);
      }
      setStep(2);
    } catch (err) {
      setParsed(null);
      setError(errorText(err));
    } finally {
      setParsing(false);
    }
  };

  const handleRun = async () => {
    if (!parsed) return;
    setRunning(true);
    setError(null);
    try {
      const source = await createSource({
        source_type: tableFile ? "sheet" : "file",
        name: `资料导入 · ${parsed.filename}`,
        config: {},
        target_entity: entity.value,
        is_active: true,
      });
      const job = await createJob({ source_id: source.id, trigger: "file" });
      const out = await runExtraction({
        job_id: job.id,
        source_id: source.id,
        target_entity: entity.value,
        text: parsed.text,
        filename: parsed.filename,
      });
      setJobId(job.id);
      setResult(out);
      message.success(`已入队 ${out.queued} 条候选，请到待确认队列复核`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setRunning(false);
    }
  };

  const updateMapping = (header: string, target?: string) => {
    setMapping((prev) => {
      const next: Record<string, string> = {};
      for (const [src, dst] of Object.entries(prev)) {
        if (dst === target && src !== header) continue; // 一个目标字段只接受一个源列
        next[src] = dst;
      }
      if (target) next[header] = target;
      else delete next[header];
      return next;
    });
  };

  const mappingColumns: TableColumnsType<{ header: string }> = [
    { title: "表格列名", dataIndex: "header" },
    {
      title: "对应目标字段",
      key: "target",
      width: 320,
      render: (_, row) => {
        const used = new Set(Object.values(mapping));
        return (
          <Select
            style={{ width: "100%" }}
            allowClear
            placeholder="不导入该列"
            value={mapping[row.header]}
            onChange={(v?: string) => updateMapping(row.header, v)}
            options={entity.fields.map((f) => ({
              value: f,
              label: `${FIELD_LABELS[f] ?? f}（${f}）${entity.required.includes(f) ? "（必填）" : ""}`,
              disabled: used.has(f) && mapping[row.header] !== f,
            }))}
          />
        );
      },
    },
  ];

  return (
    <>
      <PageHeader
        title="导入资料"
        subtitle="上传资料 → AI 抽取候选 → 人工确认后才写入业务台账"
        onBack={() => navigate("/settings/data-hub")}
      />

      <Card>
        <Steps current={step} items={steps} style={{ marginBottom: 24 }} />

        {step === 0 && (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Text>选择要从这份资料里抽取的对象：</Text>
            <Select
              style={{ maxWidth: 360 }}
              value={entity.value}
              onChange={(v) => {
                const next = ENTITIES.find((e) => e.value === v) ?? ENTITIES[0];
                setEntity(next);
                setMapping({});
                setMappingSource(null);
              }}
              options={ENTITIES.map((e) => ({ value: e.value, label: e.label }))}
            />
            <Text type="secondary">
              必填字段：{entity.required.map((f) => FIELD_LABELS[f] ?? f).join("、")}
            </Text>
            <Button type="primary" onClick={() => setStep(1)}>
              下一步
            </Button>
          </Space>
        )}

        {step === 1 && (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Dragger
              accept=".pdf,.docx,.xlsx,.csv,.txt"
              maxCount={1}
              showUploadList={false}
              disabled={parsing}
              beforeUpload={(file) => {
                void handleParse(file);
                return false;
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域</p>
              <p className="ant-upload-hint">
                支持 PDF / DOCX / XLSX / CSV / TXT；图片型扫描件暂不支持
              </p>
            </Dragger>
            {parsing && <Text type="secondary">正在解析文件…</Text>}
            {parsed && (
              <Descriptions size="small" column={1} bordered>
                <Descriptions.Item label="文件名">{parsed.filename}</Descriptions.Item>
                <Descriptions.Item label="字符数">{parsed.chars}</Descriptions.Item>
                <Descriptions.Item label="文本预览">
                  <Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                    {parsed.text.slice(0, 500)}
                    {parsed.text.length > 500 ? "…" : ""}
                  </Paragraph>
                </Descriptions.Item>
              </Descriptions>
            )}
            {error && <Alert type="error" showIcon message={error} />}
            <Space>
              <Button onClick={() => setStep(0)}>上一步</Button>
              {parsed && (
                <Button
                  type="primary"
                  onClick={() => setStep(tableFile ? 2 : runStep)}
                  disabled={parsing}
                >
                  下一步
                </Button>
              )}
            </Space>
          </Space>
        )}

        {step === 2 && tableFile && (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Space>
              <Text strong>列映射建议</Text>
              {mappingSource && (
                <Tag color={mappingSource === "ai" ? "blue" : "default"}>
                  {mappingSource === "ai" ? "AI 建议" : "精确匹配"}
                </Tag>
              )}
              <Text type="secondary">确认后用于表格导入，可逐列修改</Text>
            </Space>
            {!headers.length && (
              <Alert
                type="warning"
                showIcon
                message="未从文件中识别到表头行，请确认文件第一行是列名"
              />
            )}
            {entity.value === "major_hazard_unit_chemical" &&
              !Object.values(mapping).includes("unit_name") && (
                <Alert
                  type="info"
                  showIcon
                  message="「归属单元名称」没有对应列是正常的"
                  description="表格里通常只有物质与数量，单元归属在待确认队列页由人工指定，不影响继续。"
                />
              )}
            {unmappedRequired.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message={`必填字段尚未映射：${unmappedRequired
                  .map((f) => FIELD_LABELS[f] ?? f)
                  .join("、")}`}
              />
            )}
            <Table
              rowKey="header"
              size="small"
              pagination={false}
              dataSource={headers.map((h) => ({ header: h }))}
              columns={mappingColumns}
            />
            <Space>
              <Button onClick={() => setStep(1)}>上一步</Button>
              <Button
                type="primary"
                disabled={unmappedRequired.length > 0 || !headers.length}
                onClick={() => setStep(runStep)}
              >
                下一步
              </Button>
            </Space>
          </Space>
        )}

        {step === runStep && (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="目标实体">{entity.label}</Descriptions.Item>
              <Descriptions.Item label="文件">{parsed?.filename ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="字符数">{parsed?.chars ?? 0}</Descriptions.Item>
            </Descriptions>

            {!result && (
              <>
                <Alert
                  type="info"
                  showIcon
                  message="抽取结果会进入「待确认队列」，不会直接写入业务台账"
                  description="每条候选都带来源定位与置信度；低置信度默认不勾选，确认后才入库。"
                />
                {error && <Alert type="error" showIcon message={error} />}
                <Space>
                  <Button onClick={() => setStep(tableFile ? 2 : 1)}>上一步</Button>
                  <Button type="primary" loading={running} onClick={() => void handleRun()}>
                    开始抽取
                  </Button>
                </Space>
              </>
            )}

            {result && (
              <Result
                status={result.queued > 0 ? "success" : "warning"}
                title={`已入队 ${result.queued} 条 / 跳过 ${result.skipped} 条 / 结构不合法 ${result.invalid} 条`}
                subTitle={
                  result.queued === 0 && result.skipped > 0
                    ? "跳过的条目与上次导入重复（幂等生效），无需重复处理"
                    : "请到待确认队列逐条复核后再入库"
                }
                extra={[
                  <Button
                    key="review"
                    type="primary"
                    disabled={!jobId}
                    onClick={() => navigate(`/settings/data-hub/${jobId}/review`)}
                  >
                    去待确认队列
                  </Button>,
                  <Button key="again" onClick={reset}>
                    再导一份
                  </Button>,
                ]}
              />
            )}
          </Space>
        )}
      </Card>
    </>
  );
}
