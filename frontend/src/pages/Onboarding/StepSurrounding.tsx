import { useState } from "react";
import { Button, Checkbox, Col, Divider, Empty, message, Modal, Row, Slider, Space } from "antd";
import { SearchOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSurrounding, searchAmapSurrounding, updateSurrounding } from "@/services/enterpriseService";
import type { SurroundingInfo } from "@/types/enterprise";
import AmapSearchResultModal from "@/components/enterprise/AmapSearchResultModal";
import SurroundingAIGenerateModal from "@/components/enterprise/SurroundingAIGenerateModal";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
}

const EMPTY_SURROUNDING: SurroundingInfo = { nearby_units: [], sensitive_targets: [], traffic_info: "" };

// 与后端 AMAP_POI_KEYWORDS 保持同步（后端仅在搜索返回时携带 available_types）
const AMAP_POI_OPTIONS: { code: string; label: string; group: "nearby" | "sensitive" }[] = [
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

export default function StepSurrounding({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const [amapConfigOpen, setAmapConfigOpen] = useState(false);
  const [amapRadius, setAmapRadius] = useState(5000);
  const [amapTypes, setAmapTypes] = useState<string[]>(AMAP_POI_OPTIONS.map(o => o.code));
  const [amapSearching, setAmapSearching] = useState(false);
  const [amapResult, setAmapResult] = useState<SurroundingInfo | null>(null);
  const [amapResultOpen, setAmapResultOpen] = useState(false);
  const [amapSearchedAddress, setAmapSearchedAddress] = useState("");
  const [aiModalOpen, setAiModalOpen] = useState(false);

  const { data: surrounding = EMPTY_SURROUNDING } = useQuery({
    queryKey: ["surrounding", enterpriseId],
    queryFn: () => getSurrounding(enterpriseId),
    enabled: !!enterpriseId,
  });

  const refreshCompletion = () => {
    queryClient.invalidateQueries({ queryKey: ["surrounding", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
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
      setAmapResult(result.surrounding);
      setAmapSearchedAddress(result.searched_address);
      setAmapResultOpen(true);
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (e as Error)?.message ||
        "高德搜索失败";
      message.error(detail);
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
            {AMAP_POI_OPTIONS.map(o => (
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
    </div>
  );
}
