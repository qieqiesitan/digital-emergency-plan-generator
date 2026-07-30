import { useState } from "react";
import {
  Button,
  Spin,
  Alert,
  Space,
  Tag,
  Descriptions,
  Divider,
  Empty,
  Modal,
  message,
} from "antd";
import {
  PlusOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  SettingOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EnvironmentOutlined,
  AppstoreOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getFullHierarchy, createZone } from "@/services/riskManagementService";
import RiskHierarchyTree from "@/components/enterprise/RiskHierarchyTree";
import type { TreeNodeMeta } from "@/components/enterprise/RiskHierarchyTree";
import type { HierarchyZone } from "@/types/riskManagement";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

// Types

interface Props {
  enterpriseId: string;
  floorPlanUrl?: string | null;
}

const NODE_TYPE_LABELS: Record<TreeNodeMeta["type"], string> = {
  zone: "分区",
  object: "分析对象",
  unit: "单元",
  event: "风险事件",
  measure: "管控措施",
};

const MEASURE_STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <ClockCircleOutlined style={{ color: "#fa8c16" }} />,
  implemented: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
  expired: <CloseCircleOutlined style={{ color: "#ff4d4f" }} />,
};

const MEASURE_CATEGORY_LABELS: Record<string, string> = {
  engineering: "工程技术",
  management: "管理措施",
  ppe: "个体防护",
  emergency: "应急处置",
};

// Add zone modal

function AddZoneModal({
  open,
  enterpriseId,
  onClose,
  onCreated,
}: {
  open: boolean;
  enterpriseId: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleOk = async () => {
    if (!name.trim()) {
      message.warning("请输入分区名称");
      return;
    }
    setSubmitting(true);
    try {
      await createZone(enterpriseId, {
        name: name.trim(),
        description: description.trim() || undefined,
      });
      message.success("分区创建成功");
      setName("");
      setDescription("");
      onCreated();
      onClose();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "创建失败";
      message.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (!submitting) {
      setName("");
      setDescription("");
      onClose();
    }
  };

  return (
    <Modal
      title="添加风险分区"
      open={open}
      onOk={handleOk}
      onCancel={handleCancel}
      confirmLoading={submitting}
      okText="创建"
      cancelText="取消"
      destroyOnClose
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 8 }}>
        <div>
          <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
            分区名称 <span style={{ color: "#ff4d4f" }}>*</span>
          </label>
          <input
            style={{
              width: "100%",
              padding: "6px 11px",
              border: "1px solid #d9d9d9",
              borderRadius: 6,
              fontSize: 14,
              lineHeight: "22px",
            }}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：生产车间A区、仓储区、配电房"
            onKeyDown={(e) => e.key === "Enter" && handleOk()}
            autoFocus
          />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
            分区描述
          </label>
          <textarea
            style={{
              width: "100%",
              padding: "6px 11px",
              border: "1px solid #d9d9d9",
              borderRadius: 6,
              fontSize: 14,
              lineHeight: "22px",
              resize: "vertical",
              minHeight: 72,
            }}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="描述该区域的主要风险特征..."
          />
        </div>
      </div>
    </Modal>
  );
}

// Detail panel

function DetailPanel({
  node,
  hierarchy,
}: {
  node: TreeNodeMeta;
  hierarchy: HierarchyZone[];
}) {
  const { id, type, name } = node;

  // Find the node in hierarchy data for richer display
  const findNodeInHierarchy = (): Record<string, unknown> | null => {
    if (type === "zone") {
      const z = hierarchy.find((z) => z.id === id);
      return z ? { description: z.description, objectCount: z.objects.length } : null;
    }
    for (const z of hierarchy) {
      for (const o of z.objects || []) {
        if (type === "object" && o.id === id) {
          return {
            category: o.category,
            isRiskPoint: o.is_risk_point,
            unitCount: (o.units || []).length,
            eventCount: (o.events || []).length,
            zoneName: z.name,
          };
        }
        for (const u of o.units || []) {
          if (type === "unit" && u.id === id) {
            return {
              unitType: u.unit_type,
              eventCount: (u.events || []).length,
              objectName: o.name,
              zoneName: z.name,
            };
          }
          for (const ev of u.events || []) {
            if (type === "event" && ev.id === id) {
              return {
                accidentType: ev.accident_type,
                description: ev.description,
                riskLevel: ev.risk_level,
                riskScore: ev.risk_score,
                methodType: ev.method_type,
                measureCount: (ev.measures || []).length,
                unitName: u.name,
                objectName: o.name,
                zoneName: z.name,
              };
            }
            for (const m of ev.measures || []) {
              if (type === "measure" && m.id === id) {
                return {
                  category: m.measure_category,
                  measureType: m.measure_type,
                  status: m.status,
                  description: m.description,
                  checkItems: m.check_items,
                  eventType: ev.accident_type,
                  unitName: u.name,
                  objectName: o.name,
                  zoneName: z.name,
                };
              }
            }
          }
        }
        for (const ev of o.events || []) {
          if (type === "event" && ev.id === id) {
            return {
              accidentType: ev.accident_type,
              description: ev.description,
              riskLevel: ev.risk_level,
              riskScore: ev.risk_score,
              methodType: ev.method_type,
              measureCount: (ev.measures || []).length,
              objectName: o.name,
              zoneName: z.name,
            };
          }
          for (const m of ev.measures || []) {
            if (type === "measure" && m.id === id) {
              return {
                category: m.measure_category,
                measureType: m.measure_type,
                status: m.status,
                description: m.description,
                checkItems: m.check_items,
                eventType: ev.accident_type,
                objectName: o.name,
                zoneName: z.name,
              };
            }
          }
        }
      }
    }
    return null;
  };

  const detail = findNodeInHierarchy();

  const renderBreadcrumb = () => {
    const parts: string[] = [];
    const d = detail as Record<string, unknown> | null;
    if (d?.zoneName) parts.push(d.zoneName as string);
    if (d?.objectName) parts.push(d.objectName as string);
    if (d?.unitName) parts.push(d.unitName as string);
    if (parts.length > 0) {
      return (
        <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 8 }}>
          {"🗂 "}
          {parts.join(" > ")}
        </div>
      );
    }
    return null;
  };

  const renderBasicInfo = () => (
    <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
      <Descriptions.Item label="ID">{id}</Descriptions.Item>
      <Descriptions.Item label="类型">{NODE_TYPE_LABELS[type]}</Descriptions.Item>
      <Descriptions.Item label="名称">{name}</Descriptions.Item>
    </Descriptions>
  );

  const renderMeasureDetail = () => {
    const d = detail as Record<string, unknown> | null;
    if (!d) return null;
    const category = d.category as string;
    const status = d.status as string;
    return (
      <>
        <Divider style={{ margin: "12px 0" }} />
        <Descriptions column={1} size="small">
          <Descriptions.Item label="措施类别">
            <Tag>{MEASURE_CATEGORY_LABELS[category] || category}</Tag>
          </Descriptions.Item>
          {d.measureType && (
            <Descriptions.Item label="措施类型">
              {d.measureType as string}
            </Descriptions.Item>
          )}
          <Descriptions.Item label="状态">
            {MEASURE_STATUS_ICONS[status]}{" "}
            <span style={{ marginLeft: 4 }}>
              {status === "pending"
                ? "待实施"
                : status === "implemented"
                ? "已实施"
                : status === "expired"
                ? "已过期"
                : status}
            </span>
          </Descriptions.Item>
          {d.description && (
            <Descriptions.Item label="描述">
              {d.description as string}
            </Descriptions.Item>
          )}
        </Descriptions>
        {(d.checkItems as { name: string; standard: string; frequency: string }[])
          ?.length > 0 && (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
              检查项目
            </div>
            {(d.checkItems as { name: string; standard: string; frequency: string }[]).map(
              (ci: { name: string; standard: string; frequency: string }, idx: number) => (
                <div
                  key={idx}
                  style={{
                    fontSize: 12,
                    color: "#595959",
                    padding: "4px 0",
                    borderBottom:
                      idx < (d.checkItems as unknown[]).length - 1
                        ? "1px solid #f0f0f0"
                        : "none",
                  }}
                >
                  <div style={{ fontWeight: 500 }}>{ci.name}</div>
                  <div style={{ color: "#8c8c8c" }}>
                    标准: {ci.standard} | 频次: {ci.frequency}
                  </div>
                </div>
              )
            )}
          </>
        )}
      </>
    );
  };

  const renderEventDetail = () => {
    const d = detail as Record<string, unknown> | null;
    if (!d) return null;
    const riskLevel = d.riskLevel as string | null;
    const riskScore = d.riskScore as string | null;
    return (
      <>
        <Divider style={{ margin: "12px 0" }} />
        <Descriptions column={1} size="small">
          {d.accidentType && (
            <Descriptions.Item label="事故类型">
              <Tag color="orange">{d.accidentType as string}</Tag>
            </Descriptions.Item>
          )}
          {riskLevel && (
            <Descriptions.Item label="风险等级">
              <Tag color={RISK_LEVEL_COLORS[riskLevel] || "#d9d9d9"}>
                {riskLevel}
              </Tag>
            </Descriptions.Item>
          )}
          {riskScore && (
            <Descriptions.Item label="风险分值">
              <span style={{ fontFamily: "monospace", fontWeight: 600 }}>
                {riskScore}
              </span>
            </Descriptions.Item>
          )}
          {d.methodType && (
            <Descriptions.Item label="评估方法">
              {d.methodType as string}
            </Descriptions.Item>
          )}
          {d.description && (
            <Descriptions.Item label="描述">
              {d.description as string}
            </Descriptions.Item>
          )}
          {d.measureCount !== undefined && (
            <Descriptions.Item label="管控措施数">
              {d.measureCount as number}
            </Descriptions.Item>
          )}
        </Descriptions>
      </>
    );
  };

  const renderObjectDetail = () => {
    const d = detail as Record<string, unknown> | null;
    if (!d) return null;
    return (
      <>
        <Divider style={{ margin: "12px 0" }} />
        <Descriptions column={1} size="small">
          {d.category && (
            <Descriptions.Item label="类别">
              <Tag>{d.category as string}</Tag>
            </Descriptions.Item>
          )}
          <Descriptions.Item label="风险点">
            {d.isRiskPoint ? (
              <Tag color="red">
                <ExclamationCircleOutlined /> 是
              </Tag>
            ) : (
              <Tag>否</Tag>
            )}
          </Descriptions.Item>
          {d.unitCount !== undefined && (
            <Descriptions.Item label="单元数">
              {d.unitCount as number}
            </Descriptions.Item>
          )}
          {d.eventCount !== undefined && (
            <Descriptions.Item label="直接事件数">
              {d.eventCount as number}
            </Descriptions.Item>
          )}
        </Descriptions>
      </>
    );
  };

  const renderZoneDetail = () => {
    const d = detail as Record<string, unknown> | null;
    if (!d) return null;
    return (
      <>
        <Divider style={{ margin: "12px 0" }} />
        <Descriptions column={1} size="small">
          {d.description && (
            <Descriptions.Item label="描述">
              {d.description as string}
            </Descriptions.Item>
          )}
          {d.objectCount !== undefined && (
            <Descriptions.Item label="分析对象数">
              {d.objectCount as number}
            </Descriptions.Item>
          )}
        </Descriptions>
      </>
    );
  };

  return (
    <div>
      <h4 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 600 }}>
        {"📌 "}
        {NODE_TYPE_LABELS[type]}详情
      </h4>
      {renderBreadcrumb()}
      {renderBasicInfo()}
      {type === "zone" && renderZoneDetail()}
      {type === "object" && renderObjectDetail()}
      {type === "event" && renderEventDetail()}
      {type === "measure" && renderMeasureDetail()}
    </div>
  );
}

// Main component

export default function RiskManagementTab({
  enterpriseId,
  floorPlanUrl,
}: Props) {
  const [selectedNode, setSelectedNode] = useState<TreeNodeMeta | null>(null);
  const [addZoneOpen, setAddZoneOpen] = useState(false);

  const {
    data: hierarchy,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<HierarchyZone[]>({
    queryKey: ["risk-hierarchy", enterpriseId],
    queryFn: () => getFullHierarchy(enterpriseId),
  });

  if (isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" tip="加载风险分级管控数据..." />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert
        type="error"
        message="数据加载失败"
        description={
          error instanceof Error ? error.message : "未知错误"
        }
        showIcon
        action={
          <Button size="small" onClick={() => refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  const hierarchyData = hierarchy || [];

  return (
    <div style={{ display: "flex", gap: 20, height: "100%", minHeight: 480 }}>
      {/* Left: tree area */}
      <div
        style={{
          flex: 1,
          minWidth: 360,
          background: "#fff",
          borderRadius: 8,
          padding: 16,
          boxShadow: "0 2px 8px rgba(0,0,0,.06)",
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Toolbar */}
        <div
          style={{
            marginBottom: 12,
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddZoneOpen(true)}
          >
            添加分区
          </Button>
          <Button icon={<ThunderboltOutlined />}>
            {"🚀 智能导引"}
          </Button>
          <Button icon={<BarChartOutlined />}>
            {"📊 可视化总览"}
          </Button>
          <Button icon={<SettingOutlined />}>
            {"⚙ 评估方法"}
          </Button>
        </div>

        {/* Tree */}
        <div style={{ flex: 1, overflow: "auto" }}>
          <RiskHierarchyTree
            data={hierarchyData}
            onSelect={(node) => setSelectedNode(node)}
            onRefresh={() => refetch()}
          />
        </div>
      </div>

      {/* Right: detail panel */}
      <div
        style={{
          width: 320,
          flexShrink: 0,
          background: "#fff",
          borderRadius: 8,
          padding: 16,
          boxShadow: "0 2px 8px rgba(0,0,0,.06)",
          overflow: "auto",
        }}
      >
        {selectedNode ? (
          <DetailPanel node={selectedNode} hierarchy={hierarchyData} />
        ) : (
          <Empty
            description="点击层级树中的节点查看详情"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ marginTop: 60 }}
          />
        )}
      </div>

      {/* Add zone modal */}
      <AddZoneModal
        open={addZoneOpen}
        enterpriseId={enterpriseId}
        onClose={() => setAddZoneOpen(false)}
        onCreated={() => refetch()}
      />
    </div>
  );
}
