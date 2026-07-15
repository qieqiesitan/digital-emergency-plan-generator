import { useState, useEffect } from "react";
import { Modal, Select, message, Alert, Spin, Typography } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRegulations, abolishRegulation, fetchImpact } from "@/services/regulationService";
import type { RegulationNode, ImpactResponse } from "@/types/regulation";

const { Text } = Typography;

interface Props {
  record: RegulationNode | null;
  open: boolean;
  onClose: () => void;
}

export function AbolishDialog({ record, open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [replacedBy, setReplacedBy] = useState("");
  const [impact, setImpact] = useState<ImpactResponse | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);

  const { data } = useQuery({
    queryKey: ["regulations", "", "effective", "all", 1],
    queryFn: () => fetchRegulations({ status: "effective", page_size: 100 }),
    enabled: open,
  });

  const abolishMut = useMutation({
    mutationFn: () => abolishRegulation(record!.id, replacedBy),
    onSuccess: () => {
      message.success(`已废止：${record?.label}`);
      queryClient.invalidateQueries({ queryKey: ["regulations"] });
      onClose();
      setReplacedBy("");
    },
    onError: () => message.error("操作失败"),
  });

  useEffect(() => {
    if (!open) {
      setReplacedBy("");
      setImpact(null);
      return;
    }
    // Fetch impact when dialog opens
    if (record?.id) {
      setImpactLoading(true);
      setImpact(null);
      fetchImpact(record.id)
        .then(setImpact)
        .catch(() => setImpact(null))
        .finally(() => setImpactLoading(false));
    }
  }, [open, record?.id]);

  const options = (data?.items || []).filter(n => n.id !== record?.id && n.status === "effective");
  const affectedCount = impact?.affected_plan_count || 0;

  return (
    <Modal title={`标记废止：${record?.label || ""}`} open={open} onCancel={onClose}
      onOk={() => { if (!replacedBy) { message.warning("请选择替代法规"); return; } abolishMut.mutate(); }}
      confirmLoading={abolishMut.isPending}
      okText="确认废止" okButtonProps={{ danger: true }}
    >
      <p>此法规将被标记为废止。如有替代法规，请选择：</p>
      <Select showSearch placeholder="搜索并选择替代法规..." value={replacedBy || undefined}
        onChange={setReplacedBy} style={{ width: "100%" }} allowClear
        filterOption={(input, option) => (option?.label as string || "").includes(input)}
        options={options.map(n => ({ label: `${n.code} ${n.full_name}`, value: n.id }))} />

      {/* Impact hint */}
      {impactLoading && (
        <div style={{ marginTop: 12, textAlign: "center" }}>
          <Spin size="small" /> <Text type="secondary">正在查询影响范围...</Text>
        </div>
      )}
      {!impactLoading && impact && affectedCount > 0 && (
        <Alert
          type="warning"
          style={{ marginTop: 12 }}
          message={`废止后将影响 ${affectedCount} 个预案的法规引用`}
          description={
            impact.plans && impact.plans.length > 0 ? (
              <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 12 }}>
                {impact.plans.map((p) => (
                  <li key={p.id}>{p.name}</li>
                ))}
              </ul>
            ) : undefined
          }
        />
      )}
      {!impactLoading && impact && affectedCount === 0 && (
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">✓ 该法规未被任何预案引用</Text>
        </div>
      )}

      <p style={{ color: "#ff4d4f", marginTop: 12 }}>⚠ 标记后，AI 生成时将自动提示此法规已废止，请勿引用。</p>
    </Modal>
  );
}
