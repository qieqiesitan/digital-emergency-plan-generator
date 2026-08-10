import { useState } from "react";
import { Alert, Button, Checkbox, Collapse, Input, List, Modal, Spin, Tag, Upload, message } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import {
  analyzeFourColorMap,
  cancelFourColorImport,
  commitFourColorImport,
} from "@/services/riskMappingWorkbenchService";
import type {
  FourColorAnalyzeResult,
  FourColorCommitResult,
  FourColorDraftZone,
  FourColorExcludedItem,
  FourColorTextItem,
} from "@/types/riskMappingWorkbench";
import type { RiskLevel } from "@/types/riskManagement";

interface FourColorImportModalProps {
  open: boolean;
  enterpriseId: string;
  floorId: string;
  hasExistingData: boolean;
  existingZoneCount: number;
  existingRiskPointCount: number;
  onClose: () => void;
  onImported: (result: FourColorCommitResult) => void;
}

type Stage = "select" | "analyzing" | "preview";

const LEVEL_COLORS: Record<string, string> = {
  重大: "#ff4d4f",
  较大: "#fa8c16",
  一般: "#fadb14",
  低: "#52c41a",
};

const COLOR_LEVEL: Record<string, RiskLevel> = { 红: "重大", 橙: "较大", 黄: "一般", 蓝: "低" };
const REASON_LABEL: Record<string, string> = {
  legend: "图例",
  thin: "细长线/符号",
  border_frame: "贴边图框",
  tiny: "极小噪点",
};

function extractToken(previewUrl: string): string {
  return previewUrl.split("/four_color_tmp/")[1]?.split("/")[0] ?? "";
}

export default function FourColorImportModal({
  open,
  enterpriseId,
  floorId,
  hasExistingData,
  existingZoneCount,
  existingRiskPointCount,
  onClose,
  onImported,
}: FourColorImportModalProps) {
  const [stage, setStage] = useState<Stage>("select");
  const [result, setResult] = useState<FourColorAnalyzeResult | null>(null);
  const [zones, setZones] = useState<FourColorDraftZone[]>([]);
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [excluded, setExcluded] = useState<FourColorExcludedItem[]>([]);
  const [texts, setTexts] = useState<FourColorTextItem[]>([]);
  const [showTexts, setShowTexts] = useState(true);

  const reset = () => {
    setStage("select");
    setResult(null);
    setZones([]);
    setReplaceExisting(true);
    setExcluded([]);
    setTexts([]);
    setShowTexts(true);
  };

  const handleClose = () => {
    const token = result ? extractToken(result.preview_url) : "";
    if (token) {
      cancelFourColorImport(enterpriseId, floorId, token).catch(() => undefined);
    }
    reset();
    onClose();
  };

  const runAnalyze = async (file: File) => {
    setStage("analyzing");
    try {
      const res = await analyzeFourColorMap(enterpriseId, floorId, file);
      setResult(res);
      setZones(res.zones.map(z => ({ ...z, name: z.suggested_name || z.name })));
      setExcluded(res.excluded);
      setTexts(res.texts);
      setStage("preview");
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { code?: string; message?: string } } } };
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : detail?.message;
      if (detail && typeof detail !== "string" && detail.code === "NO_ZONE_DETECTED") {
        message.error(msg || "未识别到红/橙/黄/蓝色块，请检查图片");
      } else {
        message.error(msg || "识别失败，请重试");
      }
      setStage("select");
    }
  };

  const handleCommit = async () => {
    if (!result || zones.length === 0) return;
    setSubmitting(true);
    try {
      const payload = {
        file_token: extractToken(result.preview_url),
        zones: zones.map(z => ({
          name: z.name,
          risk_level: z.risk_level,
          polygons: z.polygons.map(p => ({ points: p.points })),
        })),
        replace_existing: replaceExisting,
      };
      const commitResult = await commitFourColorImport(enterpriseId, floorId, payload);
      onImported(commitResult);
      reset();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { code?: string; message?: string } } } };
      const detail = err?.response?.data?.detail;
      message.error(typeof detail === "string" ? detail : detail?.message || "落图失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRestore = (item: FourColorExcludedItem) => {
    const level = COLOR_LEVEL[item.color] ?? "一般";
    const newZone: FourColorDraftZone = {
      client_id: `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: `分区${zones.length + 1}`,
      risk_level: level,
      color: LEVEL_COLORS[level],
      polygons: item.polygons,
    };
    setZones([...zones, newZone]);
    setExcluded(excluded.filter(x => x !== item));
  };

  return (
    <Modal
      open={open}
      title="导入四色分布图"
      width={860}
      onCancel={handleClose}
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={handleClose}>取消</Button>,
        <Button
          key="commit"
          type="primary"
          disabled={stage !== "preview" || zones.length === 0 || submitting}
          loading={submitting}
          onClick={handleCommit}
        >
          确认落图
        </Button>,
      ]}
    >
      {stage === "select" && (
        <Upload.Dragger
          accept="image/png,image/jpeg,image/webp"
          showUploadList={false}
          beforeUpload={file => {
            runAnalyze(file as unknown as File);
            return false;
          }}
        >
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽上传四色分布图（PNG/JPEG/WebP，≤20MB）</p>
        </Upload.Dragger>
      )}
      {stage === "analyzing" && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin tip="正在识别四色区域…">
            <div style={{ width: 80, height: 80 }} />
          </Spin>
        </div>
      )}
      {stage === "preview" && result && (
        <div>
          {result.warnings.map(w => (
            <Alert key={w} type="warning" showIcon message={w} style={{ marginBottom: 8 }} />
          ))}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 12, minHeight: 320 }}>
            <div
              style={{
                position: "relative",
                background: "#fafafa",
                borderRadius: 8,
                overflow: "hidden",
                alignSelf: "start",
                aspectRatio: `${result.canvas_width} / ${result.canvas_height}`,
                width: "100%",
              }}
            >
              <img
                src={result.preview_url}
                alt="四色分布图预览"
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  objectFit: "fill",
                }}
              />
              <svg
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
              >
                {zones.map(z =>
                  z.polygons.map(p => (
                    <polygon
                      key={p.id}
                      points={p.points.map(pt => `${pt.x},${pt.y}`).join(" ")}
                      fill={LEVEL_COLORS[z.risk_level]}
                      fillOpacity={0.35}
                      stroke={LEVEL_COLORS[z.risk_level]}
                      strokeWidth={1}
                      vectorEffect="non-scaling-stroke"
                    />
                  )),
                )}
              </svg>
              {texts.length > 0 && (
                <Checkbox
                  checked={showTexts}
                  onChange={e => setShowTexts(e.target.checked)}
                  style={{ position: "absolute", top: 8, right: 8, zIndex: 2, background: "rgba(255,255,255,.85)", padding: "0 6px" }}
                >
                  文字标注
                </Checkbox>
              )}
              {showTexts && texts.map((t, i) => (
                <svg key={`text-${i}`} viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
                  <polygon
                    points={t.points.map(p => `${p.x},${p.y}`).join(" ")}
                    fill="none"
                    stroke="#1677ff"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              ))}
            </div>
            <div>
              <List
                size="small"
                dataSource={zones}
                locale={{ emptyText: "未识别到分区" }}
                renderItem={(z, i) => (
                  <List.Item
                    actions={[
                      <Button
                        key="del"
                        type="text"
                        danger
                        onClick={() => setZones(zones.filter(x => x.client_id !== z.client_id))}
                      >
                        删除
                      </Button>,
                    ]}
                  >
                    <div style={{ width: "100%" }}>
                      <Input
                        value={z.name}
                        aria-label={`分区名称${i + 1}`}
                        onChange={e =>
                          setZones(zones.map(x => (x.client_id === z.client_id ? { ...x, name: e.target.value } : x)))
                        }
                        style={{ marginBottom: 4 }}
                      />
                      <Tag color={LEVEL_COLORS[z.risk_level]}>{z.risk_level}</Tag>
                      {z.suspected && (
                        <Tag color="orange" title={z.ai_hint || "形状异常，可能不是真实分区"}>疑似干扰</Tag>
                      )}
                      <span style={{ color: "#999", fontSize: 12 }}>
                        {z.polygons.length} 个多边形 · {z.polygons[0]?.points.length ?? 0} 个顶点
                      </span>
                    </div>
                  </List.Item>
                )}
              />
              {excluded.length > 0 && (
                <Collapse
                  style={{ marginTop: 12 }}
                  items={[{
                    key: "excluded",
                    label: `已自动排除干扰项（${excluded.length}）`,
                    children: (
                      <List
                        size="small"
                        dataSource={excluded}
                        renderItem={(item, i) => (
                          <List.Item
                            actions={[
                              <Button key="restore" type="link" onClick={() => handleRestore(item)}>恢复</Button>,
                            ]}
                          >
                            <span style={{ color: "#999", fontSize: 12 }}>
                              {i + 1}. {REASON_LABEL[item.reason] ?? item.reason} · {item.polygons[0]?.points.length ?? 0} 个顶点
                            </span>
                          </List.Item>
                        )}
                      />
                    ),
                  }]}
                />
              )}
              {hasExistingData && (
                <Checkbox
                  checked={replaceExisting}
                  onChange={e => setReplaceExisting(e.target.checked)}
                  style={{ marginTop: 12 }}
                >
                  移除该楼层原有分区、文字标注与风险点（{existingZoneCount} 个分区 / {existingRiskPointCount} 个风险点）后导入
                </Checkbox>
              )}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
