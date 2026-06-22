import { useState } from "react";
import { Modal, Button, Input, Select, InputNumber, Space, message, Card } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateSurrounding } from "@/services/enterpriseService";
import type { SurroundingInfo, NearbyUnit, SensitiveTarget } from "@/types/enterprise";

interface Props {
  enterpriseId: string;
  surroundingInfo: SurroundingInfo;
  visible: boolean;
  onClose: () => void;
}

const DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export default function SurroundingInfoForm({ enterpriseId, surroundingInfo, visible, onClose }: Props) {
  const [data, setData] = useState<SurroundingInfo>(JSON.parse(JSON.stringify(surroundingInfo || { nearby_units: [], sensitive_targets: [], traffic_info: "" })));
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (d: SurroundingInfo) => updateSurrounding(enterpriseId, d),
    onSuccess: () => { message.success("保存成功"); queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] }); onClose(); },
    onError: () => message.error("保存失败"),
  });

  return (
    <Modal title="编辑周边环境" open={visible} onCancel={onClose} width={700}
      footer={[<Button key="cancel" onClick={onClose}>取消</Button>, <Button key="save" type="primary" loading={mutation.isPending} onClick={() => mutation.mutate(data)}>保存</Button>]}
    >
      <Card title="周边单位" size="small" style={{ marginBottom: 16 }}>
        {data.nearby_units.map((u, i) => (
          <Space key={i} style={{ marginBottom: 8 }}>
            <Input placeholder="名称" value={u.name} onChange={(e) => { const nu = [...data.nearby_units]; nu[i] = { ...nu[i], name: e.target.value }; setData({ ...data, nearby_units: nu }); }} />
            <Select value={u.direction} onChange={(v) => { const nu = [...data.nearby_units]; nu[i] = { ...nu[i], direction: v }; setData({ ...data, nearby_units: nu }); }} options={DIRS.map((d) => ({ value: d, label: d }))} style={{ width: 80 }} />
            <InputNumber placeholder="距离(米)" value={u.distance_m} onChange={(v) => { const nu = [...data.nearby_units]; nu[i] = { ...nu[i], distance_m: v || 0 }; setData({ ...data, nearby_units: nu }); }} />
            <Input placeholder="主要风险" value={u.main_risk} onChange={(e) => { const nu = [...data.nearby_units]; nu[i] = { ...nu[i], main_risk: e.target.value }; setData({ ...data, nearby_units: nu }); }} />
            <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setData({ ...data, nearby_units: data.nearby_units.filter((_, j) => j !== i) })} />
          </Space>
        ))}
        <Button type="dashed" icon={<PlusOutlined />} onClick={() => setData({ ...data, nearby_units: [...data.nearby_units, { name: "", direction: "N", distance_m: 0, main_risk: "" }] })} block>添加</Button>
      </Card>
      <Card title="敏感目标" size="small" style={{ marginBottom: 16 }}>
        {data.sensitive_targets.map((t, i) => (
          <Space key={i} style={{ marginBottom: 8 }}>
            <Input placeholder="名称" value={t.name} onChange={(e) => { const st = [...data.sensitive_targets]; st[i] = { ...st[i], name: e.target.value }; setData({ ...data, sensitive_targets: st }); }} />
            <Select value={t.direction} onChange={(v) => { const st = [...data.sensitive_targets]; st[i] = { ...st[i], direction: v }; setData({ ...data, sensitive_targets: st }); }} options={DIRS.map((d) => ({ value: d, label: d }))} style={{ width: 80 }} />
            <InputNumber placeholder="距离(米)" value={t.distance_m} onChange={(v) => { const st = [...data.sensitive_targets]; st[i] = { ...st[i], distance_m: v || 0 }; setData({ ...data, sensitive_targets: st }); }} />
            <Input placeholder="类型" value={t.type} onChange={(e) => { const st = [...data.sensitive_targets]; st[i] = { ...st[i], type: e.target.value }; setData({ ...data, sensitive_targets: st }); }} />
            <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setData({ ...data, sensitive_targets: data.sensitive_targets.filter((_, j) => j !== i) })} />
          </Space>
        ))}
        <Button type="dashed" icon={<PlusOutlined />} onClick={() => setData({ ...data, sensitive_targets: [...data.sensitive_targets, { name: "", direction: "N", distance_m: 0, type: "" }] })} block>添加</Button>
      </Card>
      <Card title="交通状况" size="small">
        <Input.TextArea value={data.traffic_info} rows={3} onChange={(e) => setData({ ...data, traffic_info: e.target.value })} />
      </Card>
    </Modal>
  );
}
