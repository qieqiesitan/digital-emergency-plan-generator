import { useMemo, useCallback } from "react";
import { Tree, Tag, Tooltip, Button } from "antd";
import type { DataNode, EventDataNode } from "antd/es/tree";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type {
  HierarchyZone,
  HierarchyObject,
  HierarchyUnit,
  HierarchyEvent,
  HierarchyMeasure,
  RiskZoneFloorPlanPolygon,
} from "@/types/riskManagement";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

// Types

export interface TreeNodeMeta {
  id: string;
  type: "zone" | "object" | "unit" | "event" | "measure";
  name: string;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
  parentId?: string;
  parentType?: "zone" | "object" | "unit" | "event";
}

interface Props {
  data: HierarchyZone[];
  onSelect: (node: TreeNodeMeta) => void;
  onRefresh?: () => void;
  onAction: (action: string, meta: TreeNodeMeta) => void;
}

// Helpers

const EMOJI: Record<TreeNodeMeta["type"], string> = {
  zone: "\u{1F3ED}",
  object: "\u{1F4E6}",
  unit: "\u2699\uFE0F",
  event: "\u26A0\uFE0F",
  measure: "\u{1F6E1}\uFE0F",
};

const ACTION_ITEMS: Record<TreeNodeMeta["type"], { key: string; label: string; icon: React.ReactNode }[]> = {
  zone: [
    { key: "add-object", label: "添加分析对象", icon: <PlusOutlined /> },
    { key: "edit", label: "编辑分区", icon: <EditOutlined /> },
    { key: "delete", label: "删除分区", icon: <DeleteOutlined /> },
  ],
  object: [
    { key: "add-unit", label: "添加单元", icon: <PlusOutlined /> },
    { key: "add-event", label: "添加风险事件", icon: <PlusOutlined /> },
    { key: "ai-fill", label: "智能填充下级", icon: <ThunderboltOutlined /> },
    { key: "edit", label: "编辑对象", icon: <EditOutlined /> },
    { key: "delete", label: "删除对象", icon: <DeleteOutlined /> },
  ],
  unit: [
    { key: "add-event", label: "添加风险事件", icon: <PlusOutlined /> },
    { key: "ai-fill", label: "智能填充下级", icon: <ThunderboltOutlined /> },
    { key: "edit", label: "编辑单元", icon: <EditOutlined /> },
    { key: "delete", label: "删除单元", icon: <DeleteOutlined /> },
  ],
  event: [
    { key: "add-measure", label: "添加管控措施", icon: <PlusOutlined /> },
    { key: "edit", label: "编辑事件", icon: <EditOutlined /> },
    { key: "delete", label: "删除事件", icon: <DeleteOutlined /> },
  ],
  measure: [
    { key: "edit", label: "编辑措施", icon: <EditOutlined /> },
    { key: "delete", label: "删除措施", icon: <DeleteOutlined /> },
  ],
};

// Title Row

function TitleRow({
  meta,
  riskLevel,
  childCount,
  isRiskPoint,
  onAction,
}: {
  meta: TreeNodeMeta;
  riskLevel?: string | null;
  childCount: number;
  isRiskPoint?: boolean;
  onAction: (key: string, meta: TreeNodeMeta) => void;
}) {
  const actions = ACTION_ITEMS[meta.type];

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        width: "100%",
        minWidth: 0,
        overflow: "hidden",
        lineHeight: "28px",
      }}
    >
      <span style={{ flexShrink: 0 }}>
        {isRiskPoint && <span style={{ color: "#ff4d4f", marginRight: 2 }}>{"\u25C6"}</span>}
        {EMOJI[meta.type]}
      </span>
      <span
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          flex: 1,
          minWidth: 0,
        }}
      >
        {meta.name}
      </span>
      {riskLevel && (
        <Tag
          color={RISK_LEVEL_COLORS[riskLevel] || "#d9d9d9"}
          style={{ margin: 0, fontSize: 11, lineHeight: "18px" }}
        >
          {riskLevel}
        </Tag>
      )}
      {childCount > 0 && (
        <span
          style={{
            fontSize: 11,
            color: "#8c8c8c",
            background: "#f5f5f5",
            borderRadius: 10,
            padding: "0 6px",
            lineHeight: "20px",
            flexShrink: 0,
          }}
        >
          {childCount}
        </span>
      )}
      {actions.length > 0 && (
        <span
          style={{
            marginLeft: "auto",
            display: "inline-flex",
            alignItems: "center",
            gap: 2,
            flexShrink: 0,
            paddingLeft: 8,
          }}
        >
          {actions.map((action) => (
            <Tooltip key={action.key} title={action.label}>
              <Button
                type="text"
                size="small"
                icon={action.icon}
                aria-label={action.label}
                onClick={(event) => {
                  event.stopPropagation();
                  onAction(action.key, meta);
                }}
                style={{ color: action.key === "delete" ? "#ff4d4f" : "#1677ff" }}
              />
            </Tooltip>
          ))}
        </span>
      )}
    </span>
  );
}

// Build tree data

function buildTreeData(zones: HierarchyZone[]): DataNode[] {
  function measuresToNodes(measures: HierarchyMeasure[], parentId: string): DataNode[] {
    return measures.map((m) => ({
      key: "measure-" + m.id,
      title: "",
      isLeaf: true,
      _meta: {
        id: m.id,
        type: "measure" as const,
        name: m.description,
        parentId,
        parentType: "event" as const,
      },
      _riskLevel: null,
      _childCount: 0,
    }));
  }

  function eventsToNodes(events: HierarchyEvent[], parentId: string, parentType: "unit" | "object"): DataNode[] {
    return events.map((ev) => {
      const childNodes = measuresToNodes(ev.measures || [], ev.id);
      return {
        key: "event-" + ev.id,
        title: "",
        children: childNodes.length > 0 ? childNodes : undefined,
        isLeaf: childNodes.length === 0,
        _meta: {
          id: ev.id,
          type: "event" as const,
          name: ev.accident_type,
          parentId,
          parentType,
        },
        _riskLevel: ev.risk_level,
        _childCount: childNodes.length,
      };
    });
  }

  function unitsToNodes(units: HierarchyUnit[], parentId: string): DataNode[] {
    return units.map((u) => {
      const childNodes = eventsToNodes(u.events || [], u.id, "unit");
      return {
        key: "unit-" + u.id,
        title: "",
        children: childNodes.length > 0 ? childNodes : undefined,
        isLeaf: childNodes.length === 0,
        _meta: {
          id: u.id,
          type: "unit" as const,
          name: u.name,
          parentId,
          parentType: "object" as const,
        },
        _riskLevel: null,
        _childCount: childNodes.length,
      };
    });
  }

  function objectsToNodes(objects: HierarchyObject[], parentId: string): DataNode[] {
    return objects.map((o) => {
      const unitNodes = unitsToNodes(o.units || [], o.id);
      const directEventNodes = eventsToNodes(
        (o.events || []).filter(
          (ev) =>
            !(o.units || []).some((u) =>
              (u.events || []).some((ue) => ue.id === ev.id)
            )
        ),
        o.id,
        "object"
      );
      const allChildren = [...unitNodes, ...directEventNodes];
      return {
        key: "object-" + o.id,
        title: "",
        children: allChildren.length > 0 ? allChildren : undefined,
        isLeaf: allChildren.length === 0,
        _meta: {
          id: o.id,
          type: "object" as const,
          name: o.name,
          parentId,
          parentType: "zone" as const,
        },
        _riskLevel: null,
        _childCount: allChildren.length,
        _isRiskPoint: o.is_risk_point,
      };
    });
  }

  return zones.map((z) => {
    const childNodes = objectsToNodes(z.objects || [], z.id);
    return {
      key: "zone-" + z.id,
      title: "",
      children: childNodes.length > 0 ? childNodes : undefined,
      isLeaf: childNodes.length === 0,
      _meta: {
          id: z.id,
          type: "zone" as const,
          name: z.name,
          floor_plan_polygon: z.floor_plan_polygon,
      },
      _riskLevel: null,
      _childCount: childNodes.length,
    };
  });
}

// Component

export default function RiskHierarchyTree({ data, onSelect, onAction }: Props) {
  const treeData = useMemo(() => buildTreeData(data), [data]);
  const totalNodes = useMemo(
    () =>
      data.reduce(
        (acc, z) =>
          acc +
          1 +
          (z.objects || []).reduce(
            (oa, o) =>
              oa +
              1 +
              (o.units || []).reduce(
                (ua, u) =>
                  ua +
                  1 +
                  (u.events || []).reduce(
                    (ea, ev) => ea + 1 + (ev.measures || []).length,
                    0
                  ),
                0
              ) +
              (o.events || []).reduce(
                (ea, ev) => ea + 1 + (ev.measures || []).length,
                0
              ),
            0
          ),
        0
      ),
    [data]
  );

  const handleSelect = useCallback(
    (_selectedKeys: React.Key[], info: { node: EventDataNode<DataNode> }) => {
      const meta = (info.node as DataNode & { _meta?: TreeNodeMeta })._meta;
      if (meta) {
        onSelect(meta);
      }
    },
    [onSelect]
  );

  const handleAction = useCallback(
    (key: string, meta: TreeNodeMeta) => {
      onAction(key, meta);
    },
    [onAction]
  );

  const titleRender = useCallback(
    (nodeData: DataNode) => {
      const n = nodeData as DataNode & {
        _meta?: TreeNodeMeta;
        _riskLevel?: string | null;
        _childCount?: number;
        _isRiskPoint?: boolean;
      };
      if (!n._meta) return <span>{String(nodeData.title)}</span>;
      return (
        <TitleRow
          meta={n._meta}
          riskLevel={n._riskLevel}
          childCount={n._childCount ?? 0}
          isRiskPoint={n._isRiskPoint}
          onAction={handleAction}
        />
      );
    },
    [handleAction]
  );

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          padding: 40,
          textAlign: "center",
          color: "#8c8c8c",
          fontSize: 14,
        }}
      >
        {"\u6682\u65e0\u98ce\u9669\u5206\u533a\u6570\u636e\uff0c\u8bf7\u5148\u6dfb\u52a0\u5206\u533a"}
      </div>
    );
  }

  return (
    <Tree
      treeData={treeData}
      titleRender={titleRender}
      onSelect={handleSelect}
      showLine={{ showLeafIcon: false }}
      blockNode
      defaultExpandAll={totalNodes < 100}
      virtual={totalNodes > 200}
      height={totalNodes > 200 ? 600 : undefined}
      style={{
        background: "transparent",
        fontSize: 13,
      }}
    />
  );
}
