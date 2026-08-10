import { useRef, useState } from "react";
import { Button, Card, Drawer, Space, message } from "antd";
import { DeleteOutlined, EnvironmentOutlined, UploadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateEnterprise, uploadFile } from "@/services/enterpriseService";
import type { EnterpriseUpdate } from "@/types/enterprise";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import GisMapPicker from "@/components/enterprise/GisMapPicker";
import CandidatesReview from "./CandidatesReview";
import ImportDrawer from "./ImportDrawer";
import type { CandidateItem, ImportResult } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

export default function StepEnterprise({
  enterpriseId,
  onDone,
  onPrev,
  imported,
  onAddImported,
  onRemoveImported,
}: Props) {
  const queryClient = useQueryClient();
  const [manualOpen, setManualOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [gisModalOpen, setGisModalOpen] = useState(false);
  const [gisPos, setGisPos] = useState<{ lat: number; lng: number } | null>(null);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const { data: enterprise, isError } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });
  const effectiveGis =
    gisPos ??
    (enterprise?.gis_lat != null && enterprise?.gis_lng != null
      ? { lat: enterprise.gis_lat, lng: enterprise.gis_lng }
      : null);
  const effectiveFloorPlan = floorPlanUrl ?? enterprise?.floor_plan_url ?? null;

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
  };

  const handleUpload = async (file: File) => {
    try {
      const url = await uploadFile(file);
      setFloorPlanUrl(url);
      message.success("平面图上传成功");
    } catch {
      message.error("平面图上传失败");
    }
  };

  const saveGis = async () => {
    try {
      await updateEnterprise(enterpriseId, {
        gis_lat: effectiveGis?.lat ?? null,
        gis_lng: effectiveGis?.lng ?? null,
        floor_plan_url: effectiveFloorPlan,
      });
      refreshAll();
      message.success("GIS 定位与平面图已保存");
    } catch (e: unknown) {
      message.error((e as Error)?.message || "保存失败，请重试");
    }
  };

  const handleImported = (results: ImportResult[]) => {
    const result = results[0];
    if (!result) return;
    const items = (result.candidates || []).map((raw, i) => ({
      ...raw,
      _key: raw._key || `imp-ent-${Date.now()}-${i}`,
      source: result.source,
    }));
    onAddImported?.("enterprise", items);
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
      onRemoveImported?.("enterprise", item._key);
      refreshAll();
      message.success(`已采纳：${String(item.name || "企业信息")}`);
    } catch (e: unknown) {
      message.error((e as Error)?.message || "保存失败，请重试");
    }
  };

  if (isError) {
    return (
      <div style={{ maxWidth: 720 }}>
        <h3>企业信息</h3>
        <p style={{ color: "#fa8c16" }}>企业不存在或已删除</p>
        <Button onClick={onPrev}>返回</Button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <h3>企业信息</h3>
          <p style={{ color: "#666", fontSize: 13 }}>
            先确认企业是谁——这是整份预案的事实基础
          </p>
        </div>
        <Space>
          <Button onClick={() => setManualOpen(true)}>✍️ 手动填写</Button>
          <Button onClick={() => setImportOpen(true)}>📄 导入现有数据</Button>
        </Space>
      </div>
      <EnterpriseInfoCards
        enterprise={enterprise}
        onSaved={async (values) => {
          await updateEnterprise(enterpriseId, values as EnterpriseUpdate);
          refreshAll();
          message.success("企业信息已保存");
        }}
      />
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
            <div style={{ position: "relative", display: "inline-block", marginLeft: 12 }}>
              <img
                src={effectiveFloorPlan}
                alt="平面图预览"
                style={{ maxWidth: 300, maxHeight: 150, border: "1px solid #d9d9d9", borderRadius: 4 }}
              />
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                style={{ position: "absolute", top: 0, right: 0 }}
                onClick={() => {
                  setFloorPlanUrl(null);
                  if (uploadRef.current) uploadRef.current.value = "";
                }}
              />
            </div>
          )}
        </div>
        <div style={{ marginBottom: 12 }}>
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
        <Button type="primary" onClick={saveGis}>
          保存 GIS 信息
        </Button>
      </Card>
      <GisMapPicker
        visible={gisModalOpen}
        value={effectiveGis}
        onChange={(pos) => setGisPos(pos)}
        onClose={() => setGisModalOpen(false)}
      />
      {(imported || []).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <CandidatesReview
            accepted={[]}
            candidates={imported || []}
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
            onDelete={(item) => onRemoveImported?.("enterprise", item._key)}
            onGenerateMore={() => setImportOpen(true)}
            generateMoreLabel="继续导入文件"
          />
        </div>
      )}
      <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
        <Button type="primary" onClick={onDone}>
          标记完成，下一步 →
        </Button>
      </div>
      <Drawer
        title="✍️ 手动填写企业信息"
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        width={520}
      >
        {enterprise && (
          <EnterpriseInfoCards
            enterprise={enterprise}
            onSaved={async (values) => {
              await updateEnterprise(enterpriseId, values as EnterpriseUpdate);
              refreshAll();
              setManualOpen(false);
              message.success("企业信息已保存");
            }}
          />
        )}
      </Drawer>
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
