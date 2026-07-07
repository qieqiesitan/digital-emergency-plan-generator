import { useState } from "react";
import { Modal, Button, Input, Table, message, Card, Space, Tag, Select, InputNumber } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import type { NearbyUnit, SensitiveTarget, SurroundingInfo } from "@/types/enterprise";

interface Props {
  visible: boolean;
  amapResult: SurroundingInfo;
  existingSurrounding: SurroundingInfo;
  searchedAddress: string;
  onCancel: () => void;
  onImport: (merged: SurroundingInfo) => Promise<void>;
}

interface EditableNearby extends NearbyUnit {
  _key: string;
  _isNew: boolean;
}
interface EditableTarget extends SensitiveTarget {
  _key: string;
  _isNew: boolean;
}

const DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export default function AmapSearchResultModal({
  visible, amapResult, existingSurrounding, searchedAddress,
  onCancel, onImport,
}: Props) {
  const existingUnits: EditableNearby[] = (existingSurrounding.nearby_units || []).map(
    (u, i) => ({ ...u, _key: `existing-unit-${i}`, _isNew: false }),
  );
  const newUnits: EditableNearby[] = amapResult.nearby_units.map((u, i) => ({
    ...u, _key: `amap-unit-${i}`, _isNew: true,
  }));
  const existingTargets: EditableTarget[] = (existingSurrounding.sensitive_targets || []).map(
    (t, i) => ({ ...t, _key: `existing-target-${i}`, _isNew: false }),
  );
  const newTargets: EditableTarget[] = amapResult.sensitive_targets.map((t, i) => ({
    ...t, _key: `amap-target-${i}`, _isNew: true,
  }));

  const [nearbyUnits, setNearbyUnits] = useState<EditableNearby[]>([...existingUnits, ...newUnits]);
  const [sensitiveTargets, setSensitiveTargets] = useState<EditableTarget[]>([...existingTargets, ...newTargets]);
  const [importing, setImporting] = useState(false);
  const [trafficDraft, setTrafficDraft] = useState(
    amapResult.traffic_info || existingSurrounding.traffic_info || ""
  );

  const handleImport = async () => {
    setImporting(true);
    try {
      const merged: SurroundingInfo = {
        nearby_units: nearbyUnits.map(({ _key, _isNew, ...rest }) => rest),
        sensitive_targets: sensitiveTargets.map(({ _key, _isNew, ...rest }) => rest),
        traffic_info: trafficDraft,
      };
      await onImport(merged);
      message.success("周边环境已更新");
      onCancel();
    } catch {
      message.error("导入失败");
    } finally {
      setImporting(false);
    }
  };

  const updateNearby = (key: string, field: string, value: unknown) =>
    setNearbyUnits((prev) => prev.map((u) => (u._key === key ? { ...u, [field]: value } : u)));
  const deleteNearby = (key: string) =>
    setNearbyUnits((prev) => prev.filter((u) => u._key !== key));
  const addNearby = () =>
    setNearbyUnits((prev) => [...prev, { _key: `manual-unit-${Date.now()}`, _isNew: true, name: "", direction: "N", distance_m: 0, main_risk: "" }]);

  const updateTarget = (key: string, field: string, value: unknown) =>
    setSensitiveTargets((prev) => prev.map((t) => (t._key === key ? { ...t, [field]: value } : t)));
  const deleteTarget = (key: string) =>
    setSensitiveTargets((prev) => prev.filter((t) => t._key !== key));
  const addTarget = () =>
    setSensitiveTargets((prev) => [...prev, { _key: `manual-target-${Date.now()}`, _isNew: true, name: "", direction: "N", distance_m: 0, type: "" }]);

  return (
    <Modal
      title="高德地图搜索结果预览"
      open={visible}
      onCancel={onCancel}
      width={900}
      footer={[
        <Button key="cancel" onClick={onCancel}>取消</Button>,
        <Button key="import" type="primary" loading={importing} onClick={handleImport}>
          确认导入
        </Button>,
      ]}
    >
      <p style={{ color: "#666", marginBottom: 16 }}>
        搜索地址：<strong>{searchedAddress}</strong>
        ，新增 <Tag color="blue">{amapResult.nearby_units.length}</Tag> 个周边单位，
        <Tag color="green">{amapResult.sensitive_targets.length}</Tag> 个敏感目标。
        可在下方编辑、删除或手动添加后再导入。
      </p>

      <Card title="周边单位" size="small" style={{ marginBottom: 12 }}>
        <Space style={{ marginBottom: 8 }}>
          <Button size="small" icon={<PlusOutlined />} onClick={addNearby}>手动添加</Button>
        </Space>
        <Table
          dataSource={nearbyUnits}
          rowKey="_key"
          pagination={false}
          size="small"
          scroll={{ y: 240 }}
          columns={[
            {
              title: "名称", dataIndex: "name", width: 200,
              render: (v: string, record: EditableNearby) => (
                <Input size="small" value={v}
                  onChange={(e) => updateNearby(record._key, "name", e.target.value)}
                  prefix={record._isNew ? <Tag color="blue" style={{ marginRight: 4 }}>新</Tag> : undefined} />
              ),
            },
            {
              title: "方位", dataIndex: "direction", width: 90,
              render: (v: string, record: EditableNearby) => (
                <Select size="small" value={v}
                  onChange={(val) => updateNearby(record._key, "direction", val)}
                  options={DIRECTIONS.map((d) => ({ value: d, label: d }))}
                  style={{ width: "100%" }} />
              ),
            },
            {
              title: "距离(m)", dataIndex: "distance_m", width: 100,
              render: (v: number, record: EditableNearby) => (
                <InputNumber size="small" value={v}
                  onChange={(val) => updateNearby(record._key, "distance_m", val || 0)}
                  style={{ width: "100%" }} />
              ),
            },
            {
              title: "主要风险", dataIndex: "main_risk",
              render: (v: string, record: EditableNearby) => (
                <Input size="small" value={v}
                  onChange={(e) => updateNearby(record._key, "main_risk", e.target.value)} />
              ),
            },
            {
              title: "", width: 40,
              render: (_: unknown, record: EditableNearby) => (
                <Button type="text" size="small" danger icon={<DeleteOutlined />}
                  onClick={() => deleteNearby(record._key)} />
              ),
            },
          ]}
        />
      </Card>

      <Card title="敏感目标" size="small" style={{ marginBottom: 12 }}>
        <Space style={{ marginBottom: 8 }}>
          <Button size="small" icon={<PlusOutlined />} onClick={addTarget}>手动添加</Button>
        </Space>
        <Table
          dataSource={sensitiveTargets}
          rowKey="_key"
          pagination={false}
          size="small"
          scroll={{ y: 240 }}
          columns={[
            {
              title: "名称", dataIndex: "name", width: 200,
              render: (v: string, record: EditableTarget) => (
                <Input size="small" value={v}
                  onChange={(e) => updateTarget(record._key, "name", e.target.value)}
                  prefix={record._isNew ? <Tag color="green" style={{ marginRight: 4 }}>新</Tag> : undefined} />
              ),
            },
            {
              title: "方位", dataIndex: "direction", width: 90,
              render: (v: string, record: EditableTarget) => (
                <Select size="small" value={v}
                  onChange={(val) => updateTarget(record._key, "direction", val)}
                  options={DIRECTIONS.map((d) => ({ value: d, label: d }))}
                  style={{ width: "100%" }} />
              ),
            },
            {
              title: "距离(m)", dataIndex: "distance_m", width: 100,
              render: (v: number, record: EditableTarget) => (
                <InputNumber size="small" value={v}
                  onChange={(val) => updateTarget(record._key, "distance_m", val || 0)}
                  style={{ width: "100%" }} />
              ),
            },
            {
              title: "类型", dataIndex: "type",
              render: (v: string, record: EditableTarget) => (
                <Input size="small" value={v}
                  onChange={(e) => updateTarget(record._key, "type", e.target.value)} />
              ),
            },
            {
              title: "", width: 40,
              render: (_: unknown, record: EditableTarget) => (
                <Button type="text" size="small" danger icon={<DeleteOutlined />}
                  onClick={() => deleteTarget(record._key)} />
              ),
            },
          ]}
        />
      </Card>

      <Card title="交通状况" size="small" style={{ marginBottom: 12 }}>
        <Input.TextArea
          value={trafficDraft}
          onChange={(e) => setTrafficDraft(e.target.value)}
          rows={3}
        />
        {amapResult.traffic_info && amapResult.traffic_info !== existingSurrounding.traffic_info && (
          <p style={{ color: "#1677ff", fontSize: 12, marginTop: 4 }}>
            以上为高德地图根据周边道路自动生成的交通状况描述
          </p>
        )}
      </Card>

      <p style={{ color: "#999", fontSize: 12 }}>
        提示：蓝色/绿色「新」标签为本次高德搜索新增的数据，无标签为已有数据。确认导入后所有数据将合并保存。
      </p>
    </Modal>
  );
}
