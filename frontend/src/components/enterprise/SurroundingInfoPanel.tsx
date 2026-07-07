import { useState } from "react";
import { Table, Button, Select, Input, InputNumber, Modal, Space, message, Card, Slider, Checkbox, Row, Col, Divider } from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined, SearchOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateSurrounding, searchAmapSurrounding } from "@/services/enterpriseService";
import SurroundingAIGenerateModal from "./SurroundingAIGenerateModal";
import AmapSearchResultModal from "./AmapSearchResultModal";
import type { SurroundingInfo, NearbyUnit, SensitiveTarget } from "@/types/enterprise";

interface Props {
  enterpriseId: string;
  surroundingInfo: SurroundingInfo;
  onRefresh: () => void;
}

const DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

type EditMode = "nearby" | "target";
type EditRecord = { mode: EditMode; index: number | null };

const emptyNearby: NearbyUnit = { name: "", direction: "N", distance_m: 0, main_risk: "" };
const emptyTarget: SensitiveTarget = { name: "", direction: "N", distance_m: 0, type: "" };

export default function SurroundingInfoPanel({ enterpriseId, surroundingInfo, onRefresh }: Props) {
  const queryClient = useQueryClient();
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [amapConfigOpen, setAmapConfigOpen] = useState(false);
  const [amapSearching, setAmapSearching] = useState(false);
  const [amapResultOpen, setAmapResultOpen] = useState(false);
  const [amapResult, setAmapResult] = useState<SurroundingInfo | null>(null);
  const [amapSearchedAddress, setAmapSearchedAddress] = useState("");
  const [amapRadius, setAmapRadius] = useState(5000);
  const [amapSelectedTypes, setAmapSelectedTypes] = useState<string[]>([
    "消防站", "派出所", "综合医院", "加油站", "化工厂",
    "学校", "商场|超市", "住宅区|小区", "公园|广场",
  ]);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editRecord, setEditRecord] = useState<EditRecord>({ mode: "nearby", index: null });
  const [editForm, setEditForm] = useState<NearbyUnit | SensitiveTarget>({ ...emptyNearby });
  const [trafficDraft, setTrafficDraft] = useState(surroundingInfo.traffic_info || "");
  const [trafficEditing, setTrafficEditing] = useState(false);

  const nearbyUnits = surroundingInfo.nearby_units || [];
  const sensitiveTargets = surroundingInfo.sensitive_targets || [];

  const mutateSurrounding = useMutation({
    mutationFn: (d: SurroundingInfo) => updateSurrounding(enterpriseId, d),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
      onRefresh();
    },
    onError: () => message.error("保存失败"),
  });

  const handleOpenAdd = (mode: EditMode) => {
    setEditRecord({ mode, index: null });
    setEditForm(mode === "nearby" ? { ...emptyNearby } : { ...emptyTarget });
    setEditModalOpen(true);
  };

  const handleOpenEdit = (mode: EditMode, index: number, record: NearbyUnit | SensitiveTarget) => {
    setEditRecord({ mode, index });
    setEditForm({ ...record });
    setEditModalOpen(true);
  };

  const handleSaveEdit = () => {
    const newSurrounding: SurroundingInfo = {
      nearby_units: [...nearbyUnits],
      sensitive_targets: [...sensitiveTargets],
      traffic_info: surroundingInfo.traffic_info,
    };

    if (editRecord.mode === "nearby") {
      if (editRecord.index === null) {
        newSurrounding.nearby_units.push(editForm as NearbyUnit);
      } else {
        newSurrounding.nearby_units[editRecord.index] = editForm as NearbyUnit;
      }
    } else {
      if (editRecord.index === null) {
        newSurrounding.sensitive_targets.push(editForm as SensitiveTarget);
      } else {
        newSurrounding.sensitive_targets[editRecord.index] = editForm as SensitiveTarget;
      }
    }

    mutateSurrounding.mutate(newSurrounding);
    setEditModalOpen(false);
  };

  const handleDelete = (mode: EditMode, index: number) => {
    Modal.confirm({
      title: "确认删除？",
      content: "删除后不可恢复",
      onOk: () => {
        const newSurrounding: SurroundingInfo = {
          nearby_units: [...nearbyUnits],
          sensitive_targets: [...sensitiveTargets],
          traffic_info: surroundingInfo.traffic_info,
        };
        if (mode === "nearby") {
          newSurrounding.nearby_units.splice(index, 1);
        } else {
          newSurrounding.sensitive_targets.splice(index, 1);
        }
        mutateSurrounding.mutate(newSurrounding);
      },
    });
  };

  const handleSaveTraffic = () => {
    const newSurrounding: SurroundingInfo = {
      nearby_units: [...nearbyUnits],
      sensitive_targets: [...sensitiveTargets],
      traffic_info: trafficDraft,
    };
    mutateSurrounding.mutate(newSurrounding, {
      onSuccess: () => setTrafficEditing(false),
    });
  };

  const nearbyColumns = [
    { title: "名称", dataIndex: "name", width: 180 },
    { title: "方位", dataIndex: "direction", width: 80 },
    { title: "距离(m)", dataIndex: "distance_m", width: 90 },
    { title: "主要风险", dataIndex: "main_risk" },
    {
      title: "操作",
      width: 120,
      render: (_: unknown, record: NearbyUnit, index: number) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />}
            onClick={() => handleOpenEdit("nearby", index, record)} />
          <Button type="link" size="small" danger icon={<DeleteOutlined />}
            onClick={() => handleDelete("nearby", index)} />
        </Space>
      ),
    },
  ];

  const targetColumns = [
    { title: "名称", dataIndex: "name", width: 180 },
    { title: "方位", dataIndex: "direction", width: 80 },
    { title: "距离(m)", dataIndex: "distance_m", width: 90 },
    { title: "类型", dataIndex: "type" },
    {
      title: "操作",
      width: 120,
      render: (_: unknown, record: SensitiveTarget, index: number) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />}
            onClick={() => handleOpenEdit("target", index, record)} />
          <Button type="link" size="small" danger icon={<DeleteOutlined />}
            onClick={() => handleDelete("target", index)} />
        </Space>
      ),
    },
  ];

  // ponytail: POI keywords synced with backend AMAP_POI_KEYWORDS
  const AMAP_POI_OPTIONS = [
    { code: "消防站", label: "消防站", group: "nearby" },
    { code: "派出所", label: "派出所", group: "nearby" },
    { code: "综合医院", label: "综合医院", group: "nearby" },
    { code: "加油站", label: "加油站/加气站", group: "nearby" },
    { code: "化工厂", label: "化工厂", group: "nearby" },
    { code: "学校", label: "学校", group: "sensitive" },
    { code: "商场|超市", label: "商场/超市", group: "sensitive" },
    { code: "住宅区|小区", label: "住宅区", group: "sensitive" },
    { code: "公园|广场", label: "公园/广场", group: "sensitive" },
  ];

  const handleOpenAmapConfig = () => {
    setAmapConfigOpen(true);
  };

  const handleAmapSearchExecute = async () => {
    setAmapConfigOpen(false);
    setAmapSearching(true);
    try {
      const result = await searchAmapSurrounding(enterpriseId, {
        radius: amapRadius,
        types: amapSelectedTypes.join(","),
      });
      setAmapResult(result.surrounding);
      setAmapSearchedAddress(result.searched_address);
      setAmapResultOpen(true);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || "搜索失败";
      message.error(detail);
    } finally {
      setAmapSearching(false);
    }
  };

  const handleAmapImport = async (merged: SurroundingInfo) => {
    await mutateSurrounding.mutateAsync(merged);
    setAmapResultOpen(false);
    setAmapResult(null);
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenAdd("nearby")}>
          添加周边单位
        </Button>
        <Button icon={<PlusOutlined />} onClick={() => handleOpenAdd("target")}>
          添加敏感目标
        </Button>
        <Button icon={<ThunderboltOutlined />} onClick={() => setAiModalOpen(true)}>
          AI 智能生成
        </Button>
        <Button
          icon={<SearchOutlined />}
          loading={amapSearching}
          onClick={handleOpenAmapConfig}
          style={{ color: "#1677ff", borderColor: "#1677ff" }}
        >
          高德地图搜索
        </Button>
      </Space>

      <Card title="周边单位" size="small" style={{ marginBottom: 16 }}>
        <Table
          dataSource={nearbyUnits}
          rowKey={(r: any) => (r as any)._key || ((r as any)._key = crypto.randomUUID?.() || `k-${Math.random()}`)}
          columns={nearbyColumns}
          pagination={false}
          size="small"
          locale={{ emptyText: "暂无数据，点击「添加周边单位」开始录入" }}
        />
      </Card>

      <Card title="敏感目标" size="small" style={{ marginBottom: 16 }}>
        <Table
          dataSource={sensitiveTargets}
          rowKey={(r: any) => (r as any)._key || ((r as any)._key = crypto.randomUUID?.() || `k-${Math.random()}`)}
          columns={targetColumns}
          pagination={false}
          size="small"
          locale={{ emptyText: "暂无数据，点击「添加敏感目标」开始录入" }}
        />
      </Card>

      <Card
        title="交通状况"
        size="small"
        extra={
          trafficEditing ? (
            <Space>
              <Button size="small" onClick={() => { setTrafficDraft(surroundingInfo.traffic_info || ""); setTrafficEditing(false); }}>
                取消
              </Button>
              <Button size="small" type="primary" loading={mutateSurrounding.isPending} onClick={handleSaveTraffic}>
                保存
              </Button>
            </Space>
          ) : (
            <Button size="small" icon={<EditOutlined />} onClick={() => { setTrafficDraft(surroundingInfo.traffic_info || ""); setTrafficEditing(true); }}>
              编辑
            </Button>
          )
        }
      >
        {trafficEditing ? (
          <Input.TextArea
            value={trafficDraft}
            onChange={(e) => setTrafficDraft(e.target.value)}
            rows={3}
            placeholder="请输入交通状况描述..."
          />
        ) : (
          <p style={{ margin: 0 }}>{surroundingInfo.traffic_info || "暂无数据"}</p>
        )}
      </Card>

      {/* Add/Edit Modal */}
      <Modal
        title={
          editRecord.index === null
            ? (editRecord.mode === "nearby" ? "新增周边单位" : "新增敏感目标")
            : (editRecord.mode === "nearby" ? "编辑周边单位" : "编辑敏感目标")
        }
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={handleSaveEdit}
        confirmLoading={mutateSurrounding.isPending}
        width={500}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 16 }}>
          <Input
            placeholder="名称"
            value={(editForm as NearbyUnit).name}
            onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
          />
          <Select
            placeholder="方位"
            value={(editForm as NearbyUnit).direction}
            onChange={(v) => setEditForm((f) => ({ ...f, direction: v }))}
            options={DIRECTIONS.map((d) => ({ value: d, label: d }))}
            style={{ width: "100%" }}
          />
          <InputNumber
            placeholder="距离（米）"
            value={(editForm as NearbyUnit).distance_m}
            onChange={(v) => setEditForm((f) => ({ ...f, distance_m: v || 0 }))}
            style={{ width: "100%" }}
          />
          {editRecord.mode === "nearby" ? (
            <Input
              placeholder="主要风险"
              value={(editForm as NearbyUnit).main_risk}
              onChange={(e) => setEditForm((f) => ({ ...f, main_risk: e.target.value }))}
            />
          ) : (
            <Input
              placeholder="类型（如学校、医院、住宅区等）"
              value={(editForm as SensitiveTarget).type}
              onChange={(e) => setEditForm((f) => ({ ...f, type: e.target.value }))}
            />
          )}
        </div>
      </Modal>

      <SurroundingAIGenerateModal
        enterpriseId={enterpriseId}
        existingSurrounding={surroundingInfo}
        visible={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onImported={() => {
          setAiModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
          onRefresh();
        }}
      />

      {/* Amap Search Config Modal */}
      <Modal
        title="高德地图搜索配置"
        open={amapConfigOpen}
        onCancel={() => setAmapConfigOpen(false)}
        onOk={handleAmapSearchExecute}
        okText="开始搜索"
        width={560}
      >
        <div style={{ marginBottom: 20 }}>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>搜索半径</div>
          <Row gutter={16} align="middle">
            <Col flex="auto">
              <Slider
                min={500}
                max={10000}
                step={500}
                value={amapRadius}
                onChange={setAmapRadius}
                marks={{ 500: "500m", 5000: "5km", 10000: "10km" }}
              />
            </Col>
            <Col>
              <InputNumber
                min={500}
                max={10000}
                step={500}
                value={amapRadius}
                onChange={(v) => setAmapRadius(v || 5000)}
                suffix="m"
                style={{ width: 120 }}
              />
            </Col>
          </Row>
        </div>

        <Divider style={{ margin: "12px 0" }} />

        <div style={{ marginBottom: 8, fontWeight: 500 }}>搜索类型（周边单位）</div>
        <Checkbox.Group
          value={amapSelectedTypes}
          onChange={(vals) => setAmapSelectedTypes(vals as string[])}
          style={{ marginBottom: 12 }}
        >
          <Row gutter={[8, 8]}>
            {AMAP_POI_OPTIONS.filter((o) => o.group === "nearby").map((o) => (
              <Col span={12} key={o.code}>
                <Checkbox value={o.code}>{o.label}</Checkbox>
              </Col>
            ))}
          </Row>
        </Checkbox.Group>

        <div style={{ marginBottom: 8, fontWeight: 500 }}>搜索类型（敏感目标）</div>
        <Checkbox.Group
          value={amapSelectedTypes}
          onChange={(vals) => setAmapSelectedTypes(vals as string[])}
        >
          <Row gutter={[8, 8]}>
            {AMAP_POI_OPTIONS.filter((o) => o.group === "sensitive").map((o) => (
              <Col span={12} key={o.code}>
                <Checkbox value={o.code}>{o.label}</Checkbox>
              </Col>
            ))}
          </Row>
        </Checkbox.Group>

        <Divider style={{ margin: "12px 0" }} />
        <p style={{ color: "#999", fontSize: 12, margin: 0 }}>
          提示：搜索结果将合并到已有数据中，可在预览页面编辑后再导入。
        </p>
      </Modal>

      {/* Amap Search Result Preview Modal */}
      {amapResult && (
        <AmapSearchResultModal
          visible={amapResultOpen}
          amapResult={amapResult}
          existingSurrounding={surroundingInfo}
          searchedAddress={amapSearchedAddress}
          onCancel={() => { setAmapResultOpen(false); setAmapResult(null); }}
          onImport={handleAmapImport}
        />
      )}
    </div>
  );
}
