import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Row, Col, Card, Tag, Button, Modal, Select, Input,
  Space, message, Popconfirm, Typography, Empty, Spin,
} from "antd";
import {
  PlusOutlined, StarFilled, StarOutlined, CopyOutlined,
  EditOutlined, DeleteOutlined, EyeOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listMethods, deleteMethod, duplicateMethod,
  createMethod,
} from "@/services/riskManagementService";
import type { RiskAssessmentMethod, MethodConfig, MethodType } from "@/types/riskManagement";
import { renderMatrixData, RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

const { Title, Text } = Typography;

interface Props {
  enterpriseId?: string;
}

const METHOD_TYPE_LABELS: Record<string, string> = {
  LS: "LS", LEC: "LEC", COAL_LS: "COAL_LS", DIRECT: "直接判定",
};

const TEMPLATE_OPTIONS: { value: string; label: string }[] = [
  { value: "LS", label: "LS 风险评估法" },
  { value: "LEC", label: "LEC 评价法" },
  { value: "COAL_LS", label: "COAL_LS 法" },
  { value: "DIRECT", label: "空白模板" },
];

function buildDefaultConfig(methodType: string): MethodConfig {
  const base: MethodConfig = {
    version: "1.0", formula: "", display_name: "",
    parameters: [],
    risk_thresholds: [],
  };
  if (methodType === "LS") {
    base.formula = "R = L x S";
    base.display_name = METHOD_TYPE_LABELS.LS;
    base.parameters = [
      {
        key: "L", label: "事故发生的可能性", type: "integer", range: [1, 5],
        levels: [
          { value: 1, label: "极不可能", desc: "几乎不发生" },
          { value: 2, label: "较不可能", desc: "很少发生" },
          { value: 3, label: "可能", desc: "有时发生" },
          { value: 4, label: "很可能", desc: "经常发生" },
          { value: 5, label: "极有可能", desc: "频繁发生" },
        ],
      },
      {
        key: "S", label: "事故后果严重程度", type: "integer", range: [1, 5],
        levels: [
          { value: 1, label: "轻微", desc: "无伤害或轻微伤害" },
          { value: 2, label: "较小", desc: "轻微伤害" },
          { value: 3, label: "中等", desc: "较大伤害" },
          { value: 4, label: "严重", desc: "严重伤害" },
          { value: 5, label: "极严重", desc: "死亡或重大损失" },
        ],
      },
    ];
    base.risk_thresholds = [
      { min: 20, max: 25, level: "重大", color: "#ff4d4f", action: "立即整改", deadline: "立即" },
      { min: 15, max: 19, level: "较大", color: "#fa8c16", action: "立即或近期整改", deadline: "近期" },
      { min: 9, max: 14, level: "一般", color: "#fadb14", action: "2年内治理", deadline: "2年" },
      { min: 1, max: 8, level: "低", color: "#52c41a", action: "有条件有经费时治理", deadline: "有条件时" },
    ];
  } else if (methodType === "LEC") {
    base.formula = "D = L x E x C";
    base.display_name = METHOD_TYPE_LABELS.LEC;
    base.parameters = [
      {
        key: "L", label: "事故发生的可能性", type: "integer", range: [0, 10],
        levels: [
          { value: 0, label: "实际不可能", desc: "" },
          { value: 0.2, label: "极不可能", desc: "" },
          { value: 0.5, label: "很不可能", desc: "" },
          { value: 1, label: "可能性小", desc: "" },
          { value: 3, label: "可能但不经常", desc: "" },
          { value: 6, label: "相当可能", desc: "" },
          { value: 10, label: "完全可能", desc: "" },
        ],
      },
      {
        key: "E", label: "人员暴露于危险环境的频繁程度", type: "integer", range: [0, 10],
        levels: [
          { value: 0.5, label: "非常罕见", desc: "" },
          { value: 1, label: "每年几次", desc: "" },
          { value: 2, label: "每月一次", desc: "" },
          { value: 3, label: "每周一次", desc: "" },
          { value: 6, label: "每天一次", desc: "" },
          { value: 10, label: "连续暴露", desc: "" },
        ],
      },
      {
        key: "C", label: "发生事故产生的后果", type: "integer", range: [1, 100],
        levels: [
          { value: 1, label: "轻微", desc: "" },
          { value: 3, label: "较小", desc: "" },
          { value: 7, label: "严重", desc: "" },
          { value: 15, label: "重大", desc: "" },
          { value: 40, label: "灾难性", desc: "" },
          { value: 100, label: "特大灾难", desc: "" },
        ],
      },
    ];
    base.risk_thresholds = [
      { min: 320, max: 9999, level: "重大", color: "#ff4d4f", action: "立即停止作业整改", deadline: "立即" },
      { min: 160, max: 319, level: "较大", color: "#fa8c16", action: "立即或近期整改", deadline: "近期" },
      { min: 70, max: 159, level: "一般", color: "#fadb14", action: "限期整改", deadline: "限期" },
      { min: 0, max: 69, level: "低", color: "#52c41a", action: "日常管理", deadline: "持续" },
    ];
  }
  return base;
}

function MatrixThumbnail({ config }: { config: MethodConfig }) {
  const thresholds = config.risk_thresholds?.length
    ? config.risk_thresholds.map(t => ({ ...t }))
    : undefined;

  let matrixData: { l: number; s: number; r: number; level: string; color: string }[][] = [];

  if (config.parameters?.length >= 2) {
    matrixData = renderMatrixData("LS", thresholds as any);
  } else {
    matrixData = renderMatrixData("LS");
  }

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 2, width: 180, height: 180 }}>
        <div style={{ fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>L\S</div>
        {[1, 2, 3, 4, 5].map(s => (
          <div key={`h-${s}`} style={{ fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>{s}</div>
        ))}
        {matrixData.map((row, li) => (
          <>
            <div key={`lh-${li}`} style={{ fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>{li + 1}</div>
            {row.map((cell, si) => (
              <div
                key={`${li}-${si}`}
                style={{
                  backgroundColor: cell.color,
                  borderRadius: 2,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 9,
                  color: "#fff",
                  fontWeight: 600,
                }}
              >
                {cell.r}
              </div>
            ))}
          </>
        ))}
      </div>
    </div>
  );
}

export default function RiskMethodListPage({ enterpriseId: propEid }: Props) {
  const { id: paramEid } = useParams<{ id: string }>();
  const enterpriseId = propEid || paramEid!;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newMethodType, setNewMethodType] = useState<string>("LS");
  const [newMethodName, setNewMethodName] = useState("");
  const [creating, setCreating] = useState(false);

  const { data: methods, isLoading } = useQuery({
    queryKey: ["risk-methods", enterpriseId],
    queryFn: () => listMethods(enterpriseId),
    enabled: !!enterpriseId,
  });

  const deleteMut = useMutation({
    mutationFn: (mid: string) => deleteMethod(enterpriseId, mid),
    onSuccess: () => {
      message.success("已删除");
      queryClient.invalidateQueries({ queryKey: ["risk-methods", enterpriseId] });
    },
    onError: () => message.error("删除失败"),
  });

  const duplicateMut = useMutation({
    mutationFn: (mid: string) => duplicateMethod(enterpriseId, mid),
    onSuccess: () => {
      message.success("已复制");
      queryClient.invalidateQueries({ queryKey: ["risk-methods", enterpriseId] });
    },
    onError: () => message.error("复制失败"),
  });

  const handleCreate = async () => {
    if (!newMethodName.trim()) { message.warning("请输入方法名称"); return; }
    setCreating(true);
    try {
      const config = buildDefaultConfig(newMethodType);
      await createMethod(enterpriseId, { method_type: newMethodType, name: newMethodName.trim(), config });
      message.success("创建成功");
      setCreateModalOpen(false);
      setNewMethodName("");
      queryClient.invalidateQueries({ queryKey: ["risk-methods", enterpriseId] });
    } catch {
      message.error("创建失败");
    } finally {
      setCreating(false);
    }
  };

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "80px auto" }} />;

  const systemMethods = (methods || []).filter(m => m.is_system);
  const enterpriseMethods = (methods || []).filter(m => !m.is_system);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>风险评估方法管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
          新建方法
        </Button>
      </div>

      {(!methods || methods.length === 0) && <Empty description="暂无评估方法" />}

      {systemMethods.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <Title level={5} style={{ marginBottom: 12, color: "#1677ff" }}>系统方法</Title>
          <Row gutter={[16, 16]}>
            {systemMethods.map(method => (
              <Col key={method.id} xs={24} sm={12} lg={8}>
                <Card
                  size="small"
                  style={{ borderColor: "#1677ff" }}
                  title={
                    <Space>
                      <Tag color="blue">{METHOD_TYPE_LABELS[method.method_type] || method.method_type}</Tag>
                      <Text strong>{method.name}</Text>
                    </Space>
                  }
                  actions={[
                    <Button key="view" type="link" icon={<EyeOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods/${method.id}`)}>查看</Button>,
                    <Button key="copy" type="link" icon={<CopyOutlined />} onClick={() => duplicateMut.mutate(method.id)}>复制</Button>,
                  ]}
                >
                  <div style={{ fontFamily: "monospace", color: "#1677ff", fontWeight: 600, marginBottom: 4 }}>
                    {method.config?.formula || "-"}
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {method.config?.parameters?.map(p => `${p.label}(${p.range?.[0]}-${p.range?.[1]})`).join(" x ") || "-"}
                  </Text>
                  <MatrixThumbnail config={method.config} />
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}

      {enterpriseMethods.length > 0 && (
        <div>
          <Title level={5} style={{ marginBottom: 12 }}>企业方法</Title>
          <Row gutter={[16, 16]}>
            {enterpriseMethods.map(method => (
              <Col key={method.id} xs={24} sm={12} lg={8}>
                <Card
                  size="small"
                  title={
                    <Space>
                      <Tag>{METHOD_TYPE_LABELS[method.method_type] || method.method_type}</Tag>
                      <Text strong>{method.name}</Text>
                    </Space>
                  }
                  actions={[
                    <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods/${method.id}?mode=edit`)}>编辑</Button>,
                    <Button key="active" type="link" icon={method.is_active ? <StarFilled style={{ color: "#faad14" }} /> : <StarOutlined />}>默认</Button>,
                    <Popconfirm key="del" title="确认删除？" onConfirm={() => deleteMut.mutate(method.id)}>
                      <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ fontFamily: "monospace", color: "#1677ff", fontWeight: 600, marginBottom: 4 }}>
                    {method.config?.formula || "-"}
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {method.config?.parameters?.map(p => `${p.label}(${p.range?.[0]}-${p.range?.[1]})`).join(" x ") || "-"}
                  </Text>
                  <MatrixThumbnail config={method.config} />
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}

      <Modal
        title="新建风险评估方法"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateModalOpen(false); setNewMethodName(""); }}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <div>
            <Text strong style={{ display: "block", marginBottom: 4 }}>模板</Text>
            <Select
              value={newMethodType}
              onChange={setNewMethodType}
              options={TEMPLATE_OPTIONS}
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <Text strong style={{ display: "block", marginBottom: 4 }}>方法名称</Text>
            <Input
              value={newMethodName}
              onChange={e => setNewMethodName(e.target.value)}
              placeholder="输入方法名称"
            />
          </div>
        </Space>
      </Modal>
    </div>
  );
}
