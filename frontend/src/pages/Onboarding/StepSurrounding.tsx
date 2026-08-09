import { useMemo, useState } from "react";
import { Button, Checkbox, Col, Divider, Empty, message, Modal, Row, Slider, Space } from "antd";
import { SearchOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  getSurrounding,
  searchAmapSurrounding,
  updateSurrounding,
  type AmapPoiTypeItem,
} from "@/services/enterpriseService";
import type { SurroundingInfo } from "@/types/enterprise";
import AmapSearchResultModal from "@/components/enterprise/AmapSearchResultModal";
import SurroundingAIGenerateModal from "@/components/enterprise/SurroundingAIGenerateModal";
import SurroundingInfoForm from "@/components/enterprise/SurroundingInfoForm";
import CandidatesReview from "./CandidatesReview";
import ImportDrawer from "./ImportDrawer";
import type { CandidateItem, ImportResult } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

const EMPTY_SURROUNDING: SurroundingInfo = { nearby_units: [], sensitive_targets: [], traffic_info: "" };

type PoiOption = { code: string; label: string; group: "nearby" | "sensitive" };

type SurroundingCandidate = CandidateItem & {
  name: string;
  direction: string;
  distance_m?: number;
  type?: string;
  main_risk?: string;
  target_type?: "sensitive" | "nearby";
};

// 与后端 AMAP_POI_KEYWORDS 保持同步（后端搜索响应携带 available_types，优先消费；此处为回退常量）
const AMAP_POI_OPTIONS: PoiOption[] = [
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

/** 解析请求错误：优先透出后端 detail（如 504「AI 响应超时」），其次 e.message，最后兜底文案 */
function errorDetail(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e) && e.response?.data?.detail) {
    return e.response.data.detail;
  }
  return e instanceof Error && e.message ? e.message : fallback;
}

export default function StepSurrounding({
  enterpriseId,
  onDone,
  onPrev,
  imported,
  onAddImported,
  onRemoveImported,
}: Props) {
  const queryClient = useQueryClient();
  const [amapConfigOpen, setAmapConfigOpen] = useState(false);
  const [amapRadius, setAmapRadius] = useState(5000);
  const [amapTypes, setAmapTypes] = useState<string[]>(AMAP_POI_OPTIONS.map(o => o.code));
  const [poiOptions, setPoiOptions] = useState<PoiOption[]>(AMAP_POI_OPTIONS);
  const [amapSearching, setAmapSearching] = useState(false);
  const [amapResult, setAmapResult] = useState<SurroundingInfo | null>(null);
  const [amapResultOpen, setAmapResultOpen] = useState(false);
  const [amapSearchedAddress, setAmapSearchedAddress] = useState("");
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  // 取消采纳后移回候选区的周边项（可重新编辑再采纳）
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);

  const {
    data: surrounding = EMPTY_SURROUNDING,
    isLoading: acceptedLoading,
  } = useQuery({
    queryKey: ["surrounding", enterpriseId],
    queryFn: () => getSurrounding(enterpriseId),
    enabled: !!enterpriseId,
  });

  // 步骤回显：已采纳区数据直接派生自后端 GET（周边单位 + 敏感目标）
  const acceptedItems = useMemo<SurroundingCandidate[]>(
    () => [
      ...(surrounding.nearby_units || []).map(u => ({
        _key: `nearby-${u.name}-${u.direction}`,
        name: u.name,
        direction: u.direction,
        distance_m: u.distance_m,
        main_risk: u.main_risk,
      })),
      ...(surrounding.sensitive_targets || []).map(t => ({
        _key: `sensitive-${t.name}-${t.direction}`,
        name: t.name,
        direction: t.direction,
        distance_m: t.distance_m,
        type: t.type,
        target_type: "sensitive" as const,
      })),
    ],
    [surrounding],
  );

  const displayCandidates = useMemo(
    () => [...candidates, ...(imported || [])],
    [candidates, imported],
  );

  const refreshCompletion = () => {
    queryClient.invalidateQueries({ queryKey: ["surrounding", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
  };

  const handleImported = (results: ImportResult[]) => {
    const result = results[0];
    if (!result) return;
    const items: CandidateItem[] = (result.candidates || []).map((raw, i) => ({
      ...raw,
      _key: raw._key || `imp-sur-${Date.now()}-${i}`,
      source: raw.source || result.source,
    }));
    onAddImported?.("surrounding", items);
  };

  const acceptImport = async (item: CandidateItem) => {
    const name = String(item.name || "").trim();
    if (!name) {
      message.info("候选缺少名称");
      return;
    }
    const next: SurroundingInfo = {
      nearby_units: [...(surrounding.nearby_units || [])],
      sensitive_targets: [...(surrounding.sensitive_targets || [])],
      traffic_info: surrounding.traffic_info || "",
    };
    const direction = String(item.direction || "N").toUpperCase();
    const distance_m = Number(item.distance_m) || 0;
    // 提取结果区分：带 type 无 main_risk 视为敏感目标，否则周边单位
    const isTarget =
      item.target_type === "sensitive" || Boolean(item.type && !item.main_risk);
    if (isTarget) {
      if (next.sensitive_targets.some(t => t.name === name && t.direction === direction)) {
        message.warning("已存在相同敏感目标");
        return;
      }
      next.sensitive_targets.push({
        name,
        direction,
        distance_m,
        type: String(item.type || ""),
      });
    } else {
      if (next.nearby_units.some(u => u.name === name && u.direction === direction)) {
        message.warning("已存在相同周边单位");
        return;
      }
      next.nearby_units.push({
        name,
        direction,
        distance_m,
        main_risk: String(item.main_risk || ""),
      });
    }
    try {
      await saveSurrounding.mutateAsync(next);
      setCandidates(prev => prev.filter(x => x._key !== item._key));
      onRemoveImported?.("surrounding", item._key);
      message.success(`已采纳：${name}`);
    } catch (e: unknown) {
      message.error(errorDetail(e, "保存失败，请重试"));
    }
  };

  const acceptAll = async () => {
    const items = displayCandidates;
    if (items.length === 0) return;
    const next: SurroundingInfo = {
      nearby_units: [...(surrounding.nearby_units || [])],
      sensitive_targets: [...(surrounding.sensitive_targets || [])],
      traffic_info: surrounding.traffic_info || "",
    };
    const skipped: string[] = [];
    for (const item of items) {
      const name = String(item.name || "").trim();
      if (!name) {
        skipped.push("缺少名称");
        continue;
      }
      const direction = String(item.direction || "N").toUpperCase();
      const distance_m = Number(item.distance_m) || 0;
      // 与 acceptImport 保持一致的归类：带 type 无 main_risk 视为敏感目标，否则周边单位
      const isTarget =
        item.target_type === "sensitive" || Boolean(item.type && !item.main_risk);
      if (isTarget) {
        if (next.sensitive_targets.some(t => t.name === name && t.direction === direction)) {
          skipped.push(name);
          continue;
        }
        next.sensitive_targets.push({
          name,
          direction,
          distance_m,
          type: String(item.type || ""),
        });
      } else {
        if (next.nearby_units.some(u => u.name === name && u.direction === direction)) {
          skipped.push(name);
          continue;
        }
        next.nearby_units.push({
          name,
          direction,
          distance_m,
          main_risk: String(item.main_risk || ""),
        });
      }
    }
    try {
      await saveSurrounding.mutateAsync(next);
      setCandidates([]);
      items.forEach(x => onRemoveImported?.("surrounding", x._key));
      const adopted = items.length - skipped.length;
      message.success(
        skipped.length > 0
          ? `已采纳 ${adopted} 条，跳过 ${skipped.length} 条重复/无效项`
          : `已全部采纳：${items.length} 条`,
      );
    } catch (e: unknown) {
      message.error(errorDetail(e, "批量采纳失败，请重试"));
    }
  };

  const unacceptAll = async () => {
    const items = acceptedItems;
    if (items.length === 0) return;
    try {
      // 周边为整体对象保存：清空单位/敏感目标即删除已保存数据，交通状况保留
      await saveSurrounding.mutateAsync({
        nearby_units: [],
        sensitive_targets: [],
        traffic_info: surrounding.traffic_info || "",
      });
      setCandidates(prev => [...prev, ...items]);
      message.success(`已全部取消采纳：${items.length} 条`);
    } catch (e: unknown) {
      message.error(errorDetail(e, "删除失败，请重试"));
    }
  };

  const saveSurrounding = useMutation({
    mutationFn: (data: SurroundingInfo) => updateSurrounding(enterpriseId, data),
    onSuccess: refreshCompletion,
  });

  const handleAmapSearch = async () => {
    setAmapConfigOpen(false);
    setAmapSearching(true);
    try {
      const result = await searchAmapSurrounding(enterpriseId, {
        radius: amapRadius,
        types: amapTypes.length > 0 ? amapTypes.join(",") : undefined,
      });
      // POI 类型选项优先用后端 available_types，若存在则更新，否则保留本地回退常量
      if (result.available_types && result.available_types.length > 0) {
        const mapped: PoiOption[] = result.available_types.map((t: AmapPoiTypeItem) => ({
          code: t.code,
          label: t.label,
          group: t.target_type,
        }));
        setPoiOptions(mapped);
        setAmapTypes(prev => {
          const valid = prev.filter(code => mapped.some(o => o.code === code));
          return valid.length > 0 ? valid : mapped.map(o => o.code);
        });
      }
      setAmapResult(result.surrounding);
      setAmapSearchedAddress(result.searched_address);
      setAmapResultOpen(true);
    } catch (e) {
      message.error(errorDetail(e, "高德搜索失败"));
    } finally {
      setAmapSearching(false);
    }
  };

  const handleAmapImport = async (merged: SurroundingInfo) => {
    await saveSurrounding.mutateAsync(merged);
    message.success("周边环境已更新");
    setAmapResultOpen(false);
    setAmapResult(null);
  };

  const nearbyCount = (surrounding.nearby_units || []).length;
  const targetCount = (surrounding.sensitive_targets || []).length;

  return (
    <div style={{ maxWidth: 760 }}>
      <h3>周边环境</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        周边单位、敏感目标与交通状况——外部风险与联动救援力量从这里来
      </p>

      <Space style={{ marginBottom: 12 }} wrap>
        <Button
          type="primary"
          icon={<SearchOutlined />}
          loading={amapSearching}
          onClick={() => setAmapConfigOpen(true)}
        >
          高德地图搜索导入
        </Button>
        <Button icon={<ThunderboltOutlined />} onClick={() => setAiModalOpen(true)}>
          AI 生成周边环境
        </Button>
        <Button onClick={() => setManualOpen(true)}>✍️ 手动填写</Button>
        <Button onClick={() => setImportOpen(true)}>📄 导入现有数据</Button>
      </Space>

      <div
        style={{
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: 12,
          background: "#fafafa",
          marginBottom: 12,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>当前已录入</div>
        {nearbyCount === 0 && targetCount === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无周边环境数据，可用高德地图搜索或 AI 生成"
            style={{ margin: "8px 0" }}
          />
        ) : (
          <div style={{ fontSize: 13, color: "#666" }}>
            周边单位 {nearbyCount} 个 · 敏感目标 {targetCount} 个
            {surrounding.traffic_info && (
              <div style={{ marginTop: 4 }}>交通状况：{surrounding.traffic_info}</div>
            )}
          </div>
        )}
      </div>

      {(acceptedLoading || acceptedItems.length > 0 || displayCandidates.length > 0) && (
        <CandidatesReview
          accepted={acceptedItems}
          candidates={displayCandidates}
          renderItem={(item: CandidateItem) => (
            <div>
              <b>{String(item.name || "")}</b>{" "}
              <span style={{ color: "#999", fontSize: 12 }}>
                {item.type && !item.main_risk ? "[敏感目标]" : "[周边单位]"}
                {item.direction ? ` ${String(item.direction)}` : ""}
              </span>
              <div style={{ color: "#666", fontSize: 12 }}>
                {[
                  item.distance_m ? `距离 ${String(item.distance_m)} 米` : "",
                  item.type ? `类型 ${String(item.type)}` : "",
                  item.main_risk ? `主要风险 ${String(item.main_risk)}` : "",
                ]
                  .filter(Boolean)
                  .join(" · ") || "信息待补充"}
              </div>
              {item.source && (
                <div style={{ color: "#999", fontSize: 11 }}>来源：{String(item.source)}</div>
              )}
            </div>
          )}
          onAccept={acceptImport}
          onModify={() => message.info("修改功能后续接入")}
          onDelete={(item) => {
            setCandidates(prev => prev.filter(x => x._key !== item._key));
            onRemoveImported?.("surrounding", item._key);
          }}
          onGenerateMore={() => setImportOpen(true)}
          generateMoreLabel="继续导入文件"
          onAcceptAll={acceptAll}
          onUnacceptAll={unacceptAll}
          acceptedLoading={acceptedLoading}
        />
      )}

      <Divider style={{ margin: "12px 0" }} />
      <div style={{ fontSize: 12, color: "#999", marginBottom: 12 }}>
        提示：高德搜索为客观数据，结果可在预览中勾选后直接导入；AI 生成后可在核对列表中逐条采纳。
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={onDone}>标记完成，下一步 →</Button>
      </div>

      {/* 高德搜索配置 */}
      <Modal
        title="高德地图搜索配置"
        open={amapConfigOpen}
        onCancel={() => setAmapConfigOpen(false)}
        onOk={handleAmapSearch}
        okText="开始搜索"
        confirmLoading={amapSearching}
        width={520}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>搜索半径</div>
          <Slider
            min={500}
            max={10000}
            step={500}
            value={amapRadius}
            onChange={setAmapRadius}
            marks={{ 500: "500m", 5000: "5km", 10000: "10km" }}
          />
        </div>
        <div style={{ marginBottom: 8, fontWeight: 500 }}>搜索类型（不选则搜索全部）</div>
        <Checkbox.Group value={amapTypes} onChange={(vals) => setAmapTypes(vals as string[])}>
          <Row gutter={[8, 8]}>
            {poiOptions.map(o => (
              <Col span={12} key={o.code}>
                <Checkbox value={o.code}>{o.label}</Checkbox>
              </Col>
            ))}
          </Row>
        </Checkbox.Group>
      </Modal>

      {/* 高德搜索结果预览与导入 */}
      {amapResult && (
        <AmapSearchResultModal
          visible={amapResultOpen}
          amapResult={amapResult}
          existingSurrounding={surrounding}
          searchedAddress={amapSearchedAddress}
          onCancel={() => {
            setAmapResultOpen(false);
            setAmapResult(null);
          }}
          onImport={handleAmapImport}
        />
      )}

      {/* AI 生成周边环境（内含问题问答 + 预览合并 + 保存） */}
      <SurroundingAIGenerateModal
        enterpriseId={enterpriseId}
        existingSurrounding={surrounding}
        visible={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onImported={refreshCompletion}
      />
      <SurroundingInfoForm
        enterpriseId={enterpriseId}
        surroundingInfo={surrounding}
        visible={manualOpen}
        onClose={() => {
          setManualOpen(false);
          refreshCompletion();
        }}
      />
      <ImportDrawer
        enterpriseId={enterpriseId}
        open={importOpen}
        mode="single"
        module="surrounding"
        onClose={() => setImportOpen(false)}
        onImported={handleImported}
      />
    </div>
  );
}
