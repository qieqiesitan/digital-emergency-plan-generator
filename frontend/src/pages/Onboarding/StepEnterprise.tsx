import { useState } from "react";
import { Button, Drawer, Space, message } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateEnterprise } from "@/services/enterpriseService";
import type { EnterpriseUpdate } from "@/types/enterprise";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
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
  const { data: enterprise, isError } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
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
