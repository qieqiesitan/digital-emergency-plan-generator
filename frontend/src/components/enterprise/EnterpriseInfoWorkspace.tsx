import { useRef, useState } from "react";
import { Button, Card, message, Progress, Space } from "antd";
import { DeleteOutlined, EnvironmentOutlined, UploadOutlined } from "@ant-design/icons";
import axios from "axios";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateEnterprise, uploadFile } from "@/services/enterpriseService";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import type { EnterpriseUpdate } from "@/types/enterprise";
import type { CandidateItem, ImportResult } from "@/types/onboarding";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import GisMapPicker from "@/components/enterprise/GisMapPicker";
import CandidatesReview from "@/pages/Onboarding/CandidatesReview";
import ImportDrawer from "@/pages/Onboarding/ImportDrawer";

interface Props {
  enterpriseId: string;
  /** 引导页「标记完成，下一步」按钮；编辑页不传则不渲染 */
  onDone?: () => void;
  /** 资料包/页面级导入候选（引导页由 OnboardingPage 分发），编辑页不传则用本地 state */
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

/**
 * 公共企业信息工作台：引导页第 1 步与企业管理信息编辑页共用。
 * 企业信息卡片 + GIS 定位/平面图 + 导入候选核对 + 完成度条，
 * 「保存」一次性提交基本资料与 GIS 字段并停留当前页。
 */
export default function EnterpriseInfoWorkspace({
  enterpriseId,
  onDone,
  imported,
  onAddImported,
  onRemoveImported,
}: Props) {
  const queryClient = useQueryClient();
  const [importOpen, setImportOpen] = useState(false);
  const [localImported, setLocalImported] = useState<CandidateItem[]>([]);
  const [gisModalOpen, setGisModalOpen] = useState(false);
  const [gisPos, setGisPos] = useState<{ lat: number; lng: number } | null>(null);
  const [gisCleared, setGisCleared] = useState(false);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const [floorPlanCleared, setFloorPlanCleared] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);

  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: completion, isError: completionError } = useQuery({
    queryKey: ["completion", enterpriseId],
    queryFn: () => getEnterpriseCompletion(enterpriseId),
    enabled: !!enterpriseId,
  });

  const existingGis =
    enterprise?.gis_lat != null && enterprise?.gis_lng != null
      ? { lat: enterprise.gis_lat, lng: enterprise.gis_lng }
      : null;
  // 「清除」语义：清空后提交 null（不回落旧值）
  const effectiveGis = gisCleared ? null : (gisPos ?? existingGis);
  const effectiveFloorPlan = floorPlanCleared
    ? null
    : (floorPlanUrl ?? enterprise?.floor_plan_url ?? null);

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
  };

  const handleUpload = async (file: File) => {
    try {
      const url = await uploadFile(file);
      setFloorPlanUrl(url);
      setFloorPlanCleared(false);
      message.success("平面图上传成功");
    } catch {
      message.error("平面图上传失败");
    }
  };

  // 一次「保存」同时提交基本资料与 GIS/平面图，保存后停留当前页
  const handleSaved = async (values: Record<string, unknown>) => {
    try {
      await updateEnterprise(enterpriseId, {
        ...(values as EnterpriseUpdate),
        gis_lat: effectiveGis?.lat ?? null,
        gis_lng: effectiveGis?.lng ?? null,
        floor_plan_url: effectiveFloorPlan,
      });
      refreshAll();
      message.success("企业信息已保存");
    } catch (e: unknown) {
      message.error(extractDetail(e) || "保存失败，请重试");
    }
  };

  const candidates = imported ?? localImported;

  const handleImported = (results: ImportResult[]) => {
    const result = results[0];
    if (!result) return;
    const items = (result.candidates || []).map((raw, i) => ({
      ...raw,
      _key: raw._key || `imp-ent-${Date.now()}-${i}`,
      source: result.source,
    }));
    if (onAddImported) {
      onAddImported("enterprise", items);
    } else {
      setLocalImported(prev => [...prev, ...items]);
    }
  };

  const removeCandidate = (itemKey: string) => {
    if (onRemoveImported) {
      onRemoveImported("enterprise", itemKey);
    } else {
      setLocalImported(prev => prev.filter(x => x._key !== itemKey));
    }
  };

  const acceptImport = async (item: CandidateItem) => {
    const patch: EnterpriseUpdate = {};
    const assign = (key: string, raw: unknown) => {
      if (raw === null || raw === undefined || String(raw).trim() === "") return;
      (patch as Record<string, unknown>)[key] = String(raw);
    };
    assign("name", item.name);
    assign("address", item.address);
    assign("industry", item.industry);
    assign("business_scope", item.business_scope);
    assign("credit_code", item.credit_code);
    assign("legal_representative", item.legal_representative);
    assign("employee_count", item.employee_count);
    assign("safety_officer", item.safety_officer);
    if (Object.keys(patch).length === 0) {
      message.info("该候选无可采纳字段");
      return;
    }
    try {
      await updateEnterprise(enterpriseId, patch);
      removeCandidate(item._key);
      refreshAll();
      message.success(`已采纳：${String(item.name || "企业信息")}`);
    } catch (e: unknown) {
      message.error(extractDetail(e) || "保存失败，请重试");
    }
  };

  const enterpriseModule = completion?.modules?.find(m => m.key === "enterprise_info");

  return (
    <div>
      {completion && !completionError && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 8,
            }}
          >
            <span style={{ fontWeight: 600 }}>📊 数据完成度 {completion.percent}%</span>
            <span
              style={{
                fontSize: 13,
                color: enterpriseModule?.done ? "#52c41a" : "#fa8c16",
              }}
            >
              {enterpriseModule?.done ? "✓ 企业信息已完成" : "企业信息待补充"}
            </span>
          </div>
          <Progress percent={completion.percent} showInfo={false} strokeColor="#1677ff" />
        </Card>
      )}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <Button onClick={() => setImportOpen(true)}>📄 导入现有数据</Button>
      </div>
      <EnterpriseInfoCards enterprise={enterprise} onSaved={handleSaved} />
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
          {effectiveFloorPlan && (
            <div
              style={{
                position: "relative",
                display: "inline-block",
                marginLeft: 12,
              }}
            >
              <img
                src={effectiveFloorPlan}
                alt="平面图预览"
                style={{
                  maxWidth: 300,
                  maxHeight: 150,
                  border: "1px solid #d9d9d9",
                  borderRadius: 4,
                }}
              />
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                style={{ position: "absolute", top: 0, right: 0 }}
                onClick={() => {
                  setFloorPlanUrl(null);
                  setFloorPlanCleared(true);
                  if (uploadRef.current) uploadRef.current.value = "";
                }}
              />
            </div>
          )}
        </div>
        <div>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>GIS 坐标</div>
          <Space>
            <Button icon={<EnvironmentOutlined />} onClick={() => setGisModalOpen(true)}>
              {effectiveGis ? "重新选择厂区位置" : "在地图上选择厂区位置"}
            </Button>
            {effectiveGis && (
              <span style={{ color: "#666", fontSize: 13 }}>
                已选：{effectiveGis.lat.toFixed(6)}, {effectiveGis.lng.toFixed(6)}
              </span>
            )}
          </Space>
        </div>
      </Card>
      <GisMapPicker
        visible={gisModalOpen}
        value={effectiveGis}
        onChange={(pos) => {
          if (pos) {
            setGisPos(pos);
            setGisCleared(false);
          } else {
            setGisPos(null);
            setGisCleared(true);
          }
        }}
        onClose={() => setGisModalOpen(false)}
      />
      {candidates.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <CandidatesReview
            accepted={[]}
            candidates={candidates}
            renderItem={(item: CandidateItem) => (
              <div>
                <b>{String(item.name || "")}</b>
                <div style={{ color: "#666", fontSize: 12 }}>
                  {[item.address, item.industry, item.credit_code]
                    .filter(v => v !== null && v !== undefined && String(v) !== "")
                    .map(String)
                    .join(" · ") || "信息待补充"}
                </div>
                {item.source && (
                  <div style={{ color: "#999", fontSize: 11 }}>来源：{String(item.source)}</div>
                )}
              </div>
            )}
            onAccept={acceptImport}
            onModify={() => message.info("修改功能后续接入")}
            onDelete={(item) => removeCandidate(item._key)}
            onGenerateMore={() => setImportOpen(true)}
            generateMoreLabel="继续导入文件"
          />
        </div>
      )}
      {onDone && (
        <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
          <Button type="primary" onClick={onDone}>
            标记完成，下一步 →
          </Button>
        </div>
      )}
      <ImportDrawer
        enterpriseId={enterpriseId}
        open={importOpen}
        mode="single"
        module="enterprise_info"
        onClose={() => setImportOpen(false)}
        onImported={handleImported}
      />
    </div>
  );
}
