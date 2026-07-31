import { useState, useMemo, useCallback } from "react";
import { Tree, Tag, Dropdown, message } from "antd";
import type { MenuProps } from "antd";
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
} from "@/types/riskManagement";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

// Types

export interface TreeNodeMeta {
  id: string;
  type: "zone" | "object" | "unit" | "event" | "measure";
  name: string;
}

interface Props {
  data: HierarchyZone[];
  onSelect: (node: TreeNodeMeta) => void;
  onRefresh: () => void;
}

// Helpers

const EMOJI: Record<TreeNodeMeta["type"], string> = {
  zone: "\U0001F3ED",
  object: "\U0001F4E6",
  unit: "\u2699\uFE0F",
  event: "\u26A0\uFE0F",
  measure: "\U0001F6E1\uFE0F",
};

const TYPE_LABEL: Record<TreeNodeMeta["type"], string> = {
  zone: "\u5206\u533a",
  object: "\u5206\u6790\u5bf9\u8c61",
  unit: "\u5355\u5143",
  event: "\u98ce\u9669\u4e8b\u4ef6",
  measure: "\u7ba1\u63a7\u63aa\u65bd",
};

const ACTION_ITEMS: Record<TreeNodeMeta["type"], MenuProps["items"]> = {
  zone: [
    { key: "add-object", label: "\u6dfb\u52a0\u5206\u6790\u5bf9\u8c61", icon: "<PlusOutlined />" },
    { type: "divider" },
    { key: "edit", label: "\u7f16\u8f91\u5206\u533a", icon: "<EditOutlined />" },
    { key: "delete", label: "\u5220\u9664\u5206\u533a", icon: "<DeleteOutlined />", danger: true },
  ],
  object: [
    { key: "add-unit", label: "\u6dfb\u52a0\u5355\u5143", icon: "<PlusOutlined />" },
    { key: "add-event", label: "\u6dfb\u52a0\u98ce\u9669\u4e8b\u4ef6", icon: "<PlusOutlined />" },
    { type: "divider" },
    { key: "ai-fill", label: "\U0001F916 \u667a\u80fd\u586b\u5145\u4e0b\u7ea7", icon: "<ThunderboltOutlined />" },
    { key: "edit", label: "\u7f16\u8f91\u5bf9\u8c61", icon: "<EditOutlined />" },
    { key: "delete", label: "\u5220\u9664\u5bf9\u8c61", icon: "<DeleteOutlined />", danger: true },
  ],
  unit: [
    { key: "add-event", label: "\u6dfb\u52a0\u98ce\u9669\u4e8b\u4ef6", icon: "<PlusOutlined />" },
    { type: "divider" },
    { key: "ai-fill", label: "\U0001F916 \u667a\u80fd\u586b\u5145\u4e0b\u7ea7", icon: "<ThunderboltOutlined />" },
    { key: "edit", label: "\u7f16\u8f91\u5355\u5143", icon: "<EditOutlined />" },
    { key: "delete", label: "\u5220\u9664\u5355\u5143", icon: "<DeleteOutlined />", danger: true },
  ],
  event: [
    { key: "add-measure", label: "\u6dfb\u52a0\u7ba1\u63a7\u63aa\u65bd", icon: "<PlusOutlined />" },
    { type: "divider" },
    { key: "edit", label: "\u7f16\u8f91\u4e8b\u4ef6", icon: "<EditOutlined />" },
    { key: "delete", label: "\u5220\u9664\u4e8b\u4ef6", icon: "<DeleteOutlined />", danger: true },
  ],
  measure: [
    { key: "edit", label: "\u7f16\u8f91\u63aa\u65bd", icon: "<EditOutlined />" },
    { key: "delete", label: "\u5220\u9664\u63aa\u65bd", icon: "<DeleteOutlined />", danger: true },
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
  const [hovered, setHovered] = useState(false);
  const menuItems = ACTION_ITEMS[meta.type];

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        maxWidth: "100%",
        overflow: "hidden",
        lineHeight: "28px",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
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
      {hovered && menuItems && menuItems.length > 0 && (
        <Dropdown
          menu={{
            items: menuItems,
            onClick: ({ key }) => onAction(key, meta),
          }}
          trigger={["click"]}
        >
          <span
            onClick={(e) => e.stopPropagation()}
            style={{
              cursor: "pointer",
              color: "#1677ff",
              fontSize: 14,
              flexShrink: 0,
              padding: "0 2px",
            }}
          >
            <PlusOutlined />
          </span>
        </Dropdown>
      )}
    </span>
  );
}

// Build tree data

function buildTreeData(zones: HierarchyZone[]): DataNode[] {
  function measuresToNodes(measures: HierarchyMeasure[]): DataNode[] {
    return measures.map((m) => ({
      key: "measure-" + m.id,
      title: "",
      isLeaf: true,
      _meta: {
        id: m.id,
        type: "measure" as const,
        name: m.description,
      },
      _riskLevel: null,
      _childCount: 0,
    }));
  }

  function eventsToNodes(events: HierarchyEvent[]): DataNode[] {
    return events.map((ev) => {
      const childNodes = measuresToNodes(ev.measures || []);
      return {
        key: "event-" + ev.id,
        title: "",
        children: childNodes.length > 0 ? childNodes : undefined,
        isLeaf: childNodes.length === 0,
        _meta: {
          id: ev.id,
          type: "event" as const,
          name: ev.accident_type,
        },
        _riskLevel: ev.risk_level,
        _childCount: childNodes.length,
      };
    });
  }

  function unitsToNodes(units: HierarchyUnit[]): DataNode[] {
    return units.map((u) => {
      const childNodes = eventsToNodes(u.events || []);
      return {
        key: "unit-" + u.id,
        title: "",
        children: childNodes.length > 0 ? childNodes : undefined,
        isLeaf: childNodes.length === 0,
        _meta: {
          id: u.id,
          type: "unit" as const,
          name: u.name,
        },
        _riskLevel: null,
        _childCount: childNodes.length,
      };
    });
  }

  function objectsToNodes(objects: HierarchyObject[]): DataNode[] {
    return objects.map((o) => {
      const unitNodes = unitsToNodes(o.units || []);
      const directEventNodes = eventsToNodes(
        (o.events || []).filter(
          (ev) =>
            !(o.units || []).some((u) =>
              (u.events || []).some((ue) => ue.id === ev.id)
            )
        )
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
        },
        _riskLevel: null,
        _childCount: allChildren.length,
        _isRiskPoint: o.is_risk_point,
      };
    });
  }

  return zones.map((z) => {
    const childNodes = objectsToNodes(z.objects || []);
    return {
      key: "zone-" + z.id,
      title: "",
      children: childNodes.length > 0 ? childNodes : undefined,
      isLeaf: childNodes.length === 0,
      _meta: {
        id: z.id,
        type: "zone" as const,
        name: z.name,
      },
      _riskLevel: null,
      _childCount: childNodes.length,
    };
  });
}

// Component

export default function RiskHierarchyTree({ data, onSelect, onRefresh, onAction }: Props) {
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
    (selectedKeys: React.Key[], info: { node: EventDataNode<DataNode> }) => {
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
