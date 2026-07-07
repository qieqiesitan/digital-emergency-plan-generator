import { useState, useEffect } from "react";
import { Modal, Select, message } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRegulations, abolishRegulation } from "@/services/regulationService";
import type { RegulationNode } from "@/types/regulation";

interface Props {
  record: RegulationNode | null;
  open: boolean;
  onClose: () => void;
}

export function AbolishDialog({ record, open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [replacedBy, setReplacedBy] = useState("");

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

  useEffect(() => { if (!open) setReplacedBy(""); }, [open]);

  const options = (data?.items || []).filter(n => n.id !== record?.id && n.status === "effective");

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
      <p style={{ color: "#ff4d4f", marginTop: 12 }}>⚠ 标记后，AI 生成时将自动提示此法规已废止，请勿引用。</p>
    </Modal>
  );
}