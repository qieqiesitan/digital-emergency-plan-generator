import { useState, useEffect, useMemo, useCallback } from "react";
import { Modal, Input, Button, Tree, Alert, Spin, message } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  ThunderboltOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import {
  aiSmartGuide,
  createZone,
  createObject,
  createUnit,
  createEvent,
  createMeasure,
} from "@/services/riskManagementService";
import type {
  HierarchyZone,
  HierarchyObject,
  HierarchyUnit,
  HierarchyEvent,
  HierarchyMeasure,
} from "@/types/riskManagement";

interface Props {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
  enterpriseId: string;
}

type Step = "input" | "loading" | "preview";

type NodeType = "zone" | "object" | "unit" | "event" | "measure";

interface TreeNodeMeta {
  nodeType: NodeType;
  source: Record<string, unknown>;
  parentZoneIdx: number;
  parentObjectIdx: number;
  parentUnitIdx: number;
  parentEventIdx: number;
}

interface Counts {
  zones: number;
  objects: number;
  events: number;
  measures: number;
}

const NODE_ICONS: Record<NodeType, string> = {
  zone: "\u{1F3ED}",
  object: "\u{1F4E6}",
  unit: "\u{2699}\u{FE0F}",
  event: "\u{26A0}\u{FE0F}",
  measure: "\u{1F6E1}\u{FE0F}",
};

function getNodeDisplayName(source: Record<string, unknown>, nodeType: NodeType): string {
  switch (nodeType) {
    case "zone":
    case "object":
    case "unit":
      return (source.name as string) || "\u672A\u547D\u540D";
    case "event":
      return (source.accident_type as string) || (source.description as string) || "\u672A\u547D\u540D\u4E8B\u4EF6";
    case "measure":
      return (source.description as string) || "\u672A\u547D\u540D\u63AA\u65BD";
  }
}

function collectAllKeys(hierarchy: HierarchyZone[]): React.Key[] {
  const keys: React.Key[] = [];
  hierarchy.forEach((z, zi) => {
    keys.push("z-" + zi);
    (z.objects || []).forEach((o, oi) => {
      keys.push("z-" + zi + "-o-" + oi);
      (o.units || []).forEach((u, ui) => {
        keys.push("z-" + zi + "-o-" + oi + "-u-" + ui);
        (u.events || []).forEach((ev, ei) => {
          keys.push("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei);
          (ev.measures || []).forEach((_m, mi) => {
            keys.push("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei + "-m-" + mi);
          });
        });
      });
      (o.events || []).forEach((ev, ei) => {
        keys.push("z-" + zi + "-o-" + oi + "-ev-" + ei);
        (ev.measures || []).forEach((_m, mi) => {
          keys.push("z-" + zi + "-o-" + oi + "-ev-" + ei + "-m-" + mi);
        });
      });
    });
  });
  return keys;
}

function countChecked(
  hierarchy: HierarchyZone[],
  checkedKeys: React.Key[],
): Counts {
  const set = new Set(checkedKeys.map(String));
  const c: Counts = { zones: 0, objects: 0, events: 0, measures: 0 };
  hierarchy.forEach((z, zi) => {
    if (set.has("z-" + zi)) c.zones++;
    (z.objects || []).forEach((o, oi) => {
      if (set.has("z-" + zi + "-o-" + oi)) c.objects++;
      (o.units || []).forEach((u, ui) => {
        (u.events || []).forEach((ev, ei) => {
          if (set.has("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei)) c.events++;
          (ev.measures || []).forEach((_m, mi) => {
            if (set.has("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei + "-m-" + mi)) c.measures++;
          });
        });
      });
      (o.events || []).forEach((ev, ei) => {
        if (set.has("z-" + zi + "-o-" + oi + "-ev-" + ei)) c.events++;
        (ev.measures || []).forEach((_m, mi) => {
          if (set.has("z-" + zi + "-o-" + oi + "-ev-" + ei + "-m-" + mi)) c.measures++;
        });
      });
    });
  });
  return c;
}

export default function RiskSmartGuideModal({
  open,
  onClose,
  onRefresh,
  enterpriseId,
}: Props) {
  const [step, setStep] = useState<Step>("input");
  const [description, setDescription] = useState("");
  const [hierarchy, setHierarchy] = useState<HierarchyZone[]>([]);
  const [checkedKeys, setCheckedKeys] = useState<React.Key[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [nameOverrides, setNameOverrides] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setStep("input");
      setDescription("");
      setHierarchy([]);
      setCheckedKeys([]);
      setExpandedKeys([]);
      setEditingKey(null);
      setNameOverrides({});
    }
  }, [open]);

  const guideMut = useMutation({
    mutationFn: () => aiSmartGuide(enterpriseId, description),
    onSuccess: (data) => {
      setHierarchy(data.hierarchy);
      const allKeys = collectAllKeys(data.hierarchy);
      setCheckedKeys(allKeys);
      setExpandedKeys(allKeys.filter((k) => String(k).startsWith("z-") && String(k).split("-").length === 2));
      setStep("preview");
    },
    onError: (e: Error) => {
      message.error("AI \u5206\u6790\u5931\u8D25: " + (e?.message || "\u8BF7\u91CD\u8BD5"));
      setStep("input");
    },
  });

  const handleStartAnalysis = () => {
    if (!description.trim()) {
      message.warning("\u8BF7\u5148\u63CF\u8FF0\u533A\u57DF\u60C5\u51B5");
      return;
    }
    setStep("loading");
    guideMut.mutate();
  };

  const importMut = useMutation({
    mutationFn: async () => {
      const keySet = new Set(checkedKeys.map(String));
      let totalCreated = 0;

      for (let zi = 0; zi < hierarchy.length; zi++) {
        const zone = hierarchy[zi];
        const zoneKey = "z-" + zi;
        if (!keySet.has(zoneKey)) continue;

        const zoneName = nameOverrides[zoneKey] || zone.name;
        const createdZone = await createZone(enterpriseId, {
          name: zoneName,
          description: zone.description || undefined,
        });
        totalCreated++;

        for (let oi = 0; oi < (zone.objects || []).length; oi++) {
          const obj = zone.objects![oi];
          const objKey = "z-" + zi + "-o-" + oi;
          if (!keySet.has(objKey)) continue;

          const objName = nameOverrides[objKey] || obj.name;
          const createdObj = await createObject(enterpriseId, {
            zone_id: createdZone.id,
            name: objName,
            category: obj.category || undefined,
            is_risk_point: obj.is_risk_point,
          });
          totalCreated++;

          for (let ui = 0; ui < (obj.units || []).length; ui++) {
            const unit = obj.units![ui];
            const unitKey = "z-" + zi + "-o-" + oi + "-u-" + ui;
            const unitName = nameOverrides[unitKey] || unit.name;
            const createdUnit = await createUnit(enterpriseId, createdObj.id, {
              object_id: createdObj.id,
              name: unitName,
              unit_type: unit.unit_type || undefined,
            });
            totalCreated++;

            for (let ei = 0; ei < (unit.events || []).length; ei++) {
              const ev = unit.events![ei];
              const evKey = "z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei;
              if (!keySet.has(evKey)) continue;

              const evName = nameOverrides[evKey] || ev.accident_type;
              const createdEv = await createEvent(enterpriseId, createdUnit.id, {
                unit_id: createdUnit.id,
                accident_type: evName,
                description: ev.description || undefined,
                method_type: ev.method_type || "LS",
                method_params: ev.method_params || {},
              });
              totalCreated++;

              for (let mi = 0; mi < (ev.measures || []).length; mi++) {
                const m = ev.measures![mi];
                const mKey = "z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei + "-m-" + mi;
                if (!keySet.has(mKey)) continue;

                const mDesc = nameOverrides[mKey] || m.description;
                await createMeasure(enterpriseId, createdEv.id, {
                  event_id: createdEv.id,
                  measure_category: m.measure_category || "engineering",
                  measure_type: m.measure_type || undefined,
                  description: mDesc,
                  check_items: m.check_items || [],
                });
                totalCreated++;
              }
            }
          }

          for (let ei = 0; ei < (obj.events || []).length; ei++) {
            const ev = obj.events![ei];
            const evKey = "z-" + zi + "-o-" + oi + "-ev-" + ei;
            if (!keySet.has(evKey)) continue;

            const evName = nameOverrides[evKey] || ev.accident_type;
            const createdEv = await createEvent(enterpriseId, createdObj.id, {
              object_id: createdObj.id,
              accident_type: evName,
              description: ev.description || undefined,
              method_type: ev.method_type || "LS",
              method_params: ev.method_params || {},
            });
            totalCreated++;

            for (let mi = 0; mi < (ev.measures || []).length; mi++) {
              const m = ev.measures![mi];
              const mKey = "z-" + zi + "-o-" + oi + "-ev-" + ei + "-m-" + mi;
              if (!keySet.has(mKey)) continue;

              const mDesc = nameOverrides[mKey] || m.description;
              await createMeasure(enterpriseId, createdEv.id, {
                event_id: createdEv.id,
                measure_category: m.measure_category || "engineering",
                measure_type: m.measure_type || undefined,
                description: mDesc,
                check_items: m.check_items || [],
              });
              totalCreated++;
            }
          }
        }
      }

      return totalCreated;
    },
    onSuccess: (count: number) => {
      message.success("\u6210\u529F\u5BFC\u5165 " + count + " \u6761\u6570\u636E");
      onRefresh();
      onClose();
    },
    onError: (e: Error) => {
      message.error("\u5BFC\u5165\u5931\u8D25: " + (e?.message || "\u672A\u77E5\u9519\u8BEF"));
    },
  });

  const treeData = useMemo<DataNode[]>(() => {
    function buildMeasures(
      measures: HierarchyMeasure[],
      zi: number,
      oi: number,
      ui: number,
      ei: number,
      prefix: string,
    ): DataNode[] {
      return measures.map((m, mi) => {
        const key = prefix + "-m-" + mi;
        return {
          key,
          title: "",
          isLeaf: true,
          _meta: {
            nodeType: "measure" as const,
            source: m as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: ui,
            parentEventIdx: ei,
          },
        };
      });
    }

    function buildEvents(
      events: HierarchyEvent[],
      zi: number,
      oi: number,
      ui: number,
      prefix: string,
    ): DataNode[] {
      return events.map((ev, ei) => {
        const key = prefix + "-ev-" + ei;
        const childNodes = buildMeasures(ev.measures || [], zi, oi, ui, ei, key);
        return {
          key,
          title: "",
          children: childNodes.length > 0 ? childNodes : undefined,
          isLeaf: childNodes.length === 0,
          _meta: {
            nodeType: "event" as const,
            source: ev as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: ui,
            parentEventIdx: ei,
          },
        };
      });
    }

    function buildUnits(
      units: HierarchyUnit[],
      zi: number,
      oi: number,
      prefix: string,
    ): DataNode[] {
      return units.map((u, ui) => {
        const key = prefix + "-u-" + ui;
        const childNodes = buildEvents(u.events || [], zi, oi, ui, key);
        return {
          key,
          title: "",
          children: childNodes.length > 0 ? childNodes : undefined,
          isLeaf: childNodes.length === 0,
          _meta: {
            nodeType: "unit" as const,
            source: u as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: ui,
            parentEventIdx: -1,
          },
        };
      });
    }

    function buildObjects(
      objects: HierarchyObject[],
      zi: number,
    ): DataNode[] {
      return objects.map((o, oi) => {
        const key = "z-" + zi + "-o-" + oi;
        const unitNodes = buildUnits(o.units || [], zi, oi, key);
        const directEvNodes = buildEvents(
          (o.events || []).filter(
            (ev) => !(o.units || []).some((u) => (u.events || []).some((ue) => ue.id === ev.id)),
          ),
          zi,
          oi,
          -1,
          key,
        );
        const allChildren = [...unitNodes, ...directEvNodes];
        return {
          key,
          title: "",
          children: allChildren.length > 0 ? allChildren : undefined,
          isLeaf: allChildren.length === 0,
          _meta: {
            nodeType: "object" as const,
            source: o as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: -1,
            parentEventIdx: -1,
          },
        };
      });
    }

    return hierarchy.map((z, zi) => {
      const key = "z-" + zi;
      const childNodes = buildObjects(z.objects || [], zi);
      return {
        key,
        title: "",
        children: childNodes.length > 0 ? childNodes : undefined,
        isLeaf: childNodes.length === 0,
        _meta: {
          nodeType: "zone" as const,
          source: z as unknown as Record<string, unknown>,
          parentZoneIdx: zi,
          parentObjectIdx: -1,
          parentUnitIdx: -1,
          parentEventIdx: -1,
        },
      };
    });
  }, [hierarchy]);

  const startEdit = useCallback((key: string, currentName: string) => {
    setEditingKey(key);
    setEditValue(currentName);
  }, []);

  const saveEdit = useCallback(() => {
    if (editingKey) {
      setNameOverrides((prev) => ({ ...prev, [editingKey]: editValue }));
    }
    setEditingKey(null);
  }, [editingKey, editValue]);

  const cancelEdit = useCallback(() => {
    setEditingKey(null);
  }, []);

  const titleRender = useCallback(
    (nodeData: DataNode) => {
      const meta = (nodeData as DataNode & { _meta?: TreeNodeMeta })._meta;
      if (!meta) return <span>{String(nodeData.title)}</span>;

      const nodeType = meta.nodeType;
      const key = String(nodeData.key);
      const isEditing = editingKey === key;
      const displayName = nameOverrides[key] || getNodeDisplayName(meta.source, nodeType);

      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            maxWidth: "100%",
          }}
        >
          <span style={{ flexShrink: 0 }}>{NODE_ICONS[nodeType]}</span>
          {isEditing ? (
            <span
              style={{ display: "inline-flex", alignItems: "center", gap: 4, flex: 1 }}
              onClick={(e) => e.stopPropagation()}
            >
              <Input
                size="small"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onPressEnter={saveEdit}
                style={{ width: 160 }}
                autoFocus
              />
              <Button size="small" type="link" onClick={saveEdit}>
                {"\u4FDD\u5B58"}
              </Button>
              <Button size="small" type="link" onClick={cancelEdit}>
                {"\u53D6\u6D88"}
              </Button>
            </span>
          ) : (
            <>
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                  minWidth: 0,
                }}
              >
                {displayName}
              </span>
              <Button
                size="small"
                type="link"
                icon={<EditOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  startEdit(key, displayName);
                }}
                style={{ flexShrink: 0, padding: "0 4px", fontSize: 12 }}
              />
            </>
          )}
        </span>
      );
    },
    [editingKey, editValue, nameOverrides, startEdit, saveEdit, cancelEdit],
  );

  const handleCheck = useCallback((keys: React.Key[] | { checked: React.Key[]; halfChecked: React.Key[] }) => {
    if (Array.isArray(keys)) {
      setCheckedKeys(keys);
    } else {
      setCheckedKeys(keys.checked);
    }
  }, []);

  const counts = useMemo(() => countChecked(hierarchy, checkedKeys), [hierarchy, checkedKeys]);

  const footer = (() => {
    if (step === "input") {
      return [
        <Button key="cancel" onClick={onClose}>
          {"\u53D6\u6D88"}
        </Button>,
        <Button
          key="analyze"
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={handleStartAnalysis}
          loading={guideMut.isPending}
        >
          {"\u4E0B\u4E00\u6B65\u2192AI \u5206\u6790"}
        </Button>,
      ];
    }
    if (step === "loading") {
      return null;
    }
    return [
      <Button key="back" onClick={() => setStep("input")}>
        {"\u8FD4\u56DE\u4FEE\u6539"}
      </Button>,
      <Button key="cancel" onClick={onClose}>
        {"\u53D6\u6D88"}
      </Button>,
      <Button
        key="import"
        type="primary"
        loading={importMut.isPending}
        onClick={() => importMut.mutate()}
        disabled={checkedKeys.length === 0}
      >
        {"\u786E\u8BA4\u5E76\u5BFC\u5165\u5168\u90E8"}
      </Button>,
    ];
  })();

  return (
    <Modal
      title="AI \u667A\u80FD\u751F\u6210\u98CE\u9669\u5C42\u7EA7"
      open={open}
      onCancel={onClose}
      width={720}
      footer={footer}
      destroyOnClose
    >
      {step === "input" && (
        <div>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>
            {"\u8BF7\u63CF\u8FF0\u9700\u8981 AI \u5206\u6790\u7684\u533A\u57DF\u60C5\u51B5"}
          </div>
          <Input.TextArea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={"\u50A8\u7F50\u533A\u67093\u4E2A5000m\u00B3\u539F\u6CB9\u50A8\u7F50..."}
            rows={6}
            maxLength={2000}
            showCount
          />
          <div
            style={{
              marginTop: 10,
              padding: "8px 12px",
              background: "#f0f5ff",
              borderRadius: 6,
              fontSize: 13,
              color: "#2f54eb",
              display: "flex",
              alignItems: "flex-start",
              gap: 6,
            }}
          >
            <span style={{ flexShrink: 0 }}>{"\uD83D\uDCA1"}</span>
            <span>
              {"\u8BF7\u8BE6\u7EC6\u63CF\u8FF0\u533A\u57DF\u5185\u7684\u8BBE\u5907\u3001\u5DE5\u827A\u3001\u7269\u6599\u3001\u5468\u8FB9\u73AF\u5883\u7B49\u4FE1\u606F\uFF0C\u63CF\u8FF0\u8D8A\u8BE6\u7EC6\uFF0CAI \u751F\u6210\u7684\u5C42\u7EA7\u7ED3\u6784\u8D8A\u51C6\u786E\u3002\u652F\u6301\u4E2D\u6587\u81EA\u7136\u8BED\u8A00\u8F93\u5165\u3002"}
            </span>
          </div>
        </div>
      )}

      {step === "loading" && (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin size="large" />
          <p style={{ marginTop: 20, color: "#8c8c8c", fontSize: 14 }}>
            {"AI \u6B63\u5728\u5206\u6790\u533A\u57DF\u63CF\u8FF0\uFF0C\u751F\u6210\u98CE\u9669\u5C42\u7EA7\u7ED3\u6784\u2026"}
          </p>
        </div>
      )}

      {step === "preview" && (
        <div>
          <Alert
            type="warning"
            showIcon
            message="AI \u751F\u6210\u6570\u636E\u8BF7\u6838\u5B9E\u540E\u786E\u8BA4\u5BFC\u5165"
            style={{ marginBottom: 12 }}
          />

          <div
            style={{
              maxHeight: 420,
              overflow: "auto",
              border: "1px solid #f0f0f0",
              borderRadius: 6,
              padding: "8px 12px",
            }}
          >
            {treeData.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
                {"AI \u672A\u80FD\u751F\u6210\u5C42\u7EA7\u7ED3\u6784\uFF0C\u8BF7\u8FD4\u56DE\u4FEE\u6539\u63CF\u8FF0\u540E\u91CD\u8BD5"}
              </div>
            ) : (
              <Tree
                checkable
                treeData={treeData}
                checkedKeys={checkedKeys}
                expandedKeys={expandedKeys}
                onExpand={(keys) => setExpandedKeys(keys)}
                onCheck={handleCheck}
                titleRender={titleRender}
                showLine={{ showLeafIcon: false }}
                blockNode
                style={{ background: "transparent", fontSize: 13 }}
              />
            )}
          </div>

          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              background: "#fafafa",
              borderRadius: 6,
              fontSize: 13,
              color: "#595959",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span style={{ fontWeight: 500 }}>{"\u9009\u4E2D\u6C47\u603B\uFF1A"}</span>
            <span>
              {counts.zones}{"\u5206\u533A \u00B7 "}{counts.objects}{"\u5BF9\u8C61 \u00B7 "}{counts.events}{"\u4E8B\u4EF6 \u00B7 "}{counts.measures}{"\u63AA\u65BD"}
            </span>
          </div>
        </div>
      )}
    </Modal>
  );
}
