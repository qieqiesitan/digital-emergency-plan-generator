import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Input, Select, Space, Table, Tag, Tooltip } from "antd";
import type { TableColumnsType } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getDownloadUrl } from "@/services/exportService";
import { fetchCardSummaries, exportCards } from "@/services/riskNoticeCardService";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
import { PageHeader } from "@/components/common/PageHeader";
import type { CardSummary } from "@/types/riskNoticeCard";

/** 风险等级筛选项（与后端合法值一致）。 */
const LEVEL_OPTIONS = ["重大", "较大", "一般", "低", "未评估"];

/** 风险告知卡管理页（列表/筛选/勾选/批量导出）。 */
export default function RiskNoticeCardPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [selected, setSelected] = useState<string[]>([]);
  const [filters, setFilters] = useState<{ level?: string; keyword?: string }>({});
  const [exporting, setExporting] = useState(false);

  const { data = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["risk-notice-cards", enterpriseId, filters],
    queryFn: () => fetchCardSummaries(enterpriseId, filters),
    enabled: !!enterpriseId,
  });

  useEffect(() => {
    if (isError) {
      message.error("加载失败，请稍后重试");
    }
  }, [isError, message]);

  /** 统计行：总数 + 各风险等级分布与颜色（颜色复用后端 level_color）。 */
  const stats = useMemo(() => {
    const counts: Record<string, number> = {};
    const colors: Record<string, string> = {};
    for (const card of data) {
      counts[card.level] = (counts[card.level] ?? 0) + 1;
      colors[card.level] = card.level_color;
    }
    return { counts, colors };
  }, [data]);

  const openPreview = (objectId: string, ai = false) => {
    const base = `/enterprises/${enterpriseId}/risk-notice-cards/${objectId}`;
    navigate(ai ? `${base}?ai=1` : base);
  };

  const copyLink = async (card: CardSummary) => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${card.public_url}`);
      message.success("公开链接已复制");
    } catch {
      message.error("复制失败，请手动复制");
    }
  };

  const doExport = async (objectIds: string[]) => {
    if (exporting) return; // 防重入
    if (!objectIds.length) {
      message.warning("请先勾选要导出的风险点");
      return;
    }
    setExporting(true);
    try {
      const { file_key, warnings } = await exportCards(enterpriseId, objectIds);
      window.open(getDownloadUrl(file_key), "_blank");
      if (warnings.length) {
        message.warning(`部分卡片未导出：${warnings.length} 张`);
      }
      setSelected([]);
    } catch {
      message.error("导出失败，请稍后重试");
    } finally {
      setExporting(false);
    }
  };

  const exportAll = () => {
    if (exporting) return;
    if (!data.length) {
      message.warning("暂无可导出的风险点");
      return;
    }
    void doExport(data.map((card) => card.object_id));
  };

  const columns: TableColumnsType<CardSummary> = [
    {
      title: "风险点名称",
      dataIndex: "name",
      render: (name: string, record) => (
        <a onClick={() => openPreview(record.object_id)}>{name}</a>
      ),
    },
    { title: "所在分区", dataIndex: "zone_name", width: 120 },
    {
      title: "风险等级",
      dataIndex: "level",
      width: 90,
      render: (level: string, record) => <Tag color={record.level_color}>{level}</Tag>,
    },
    {
      title: "主要事故类型",
      dataIndex: "accident_types",
      render: (types: string[]) => (types.length ? types.join("、") : "—"),
    },
    {
      title: "安全标志",
      dataIndex: "signs",
      width: 130,
      render: (signs: CardSummary["signs"]) => (
        <Space size={2}>
          {signs.slice(0, 3).map((sign) => (
            <Tooltip title={sign.name} key={sign.svg_name}>
              <img
                src={`/signs/${sign.svg_name}.svg`}
                width={20}
                height={20}
                alt={sign.name}
                style={{ display: "block" }}
              />
            </Tooltip>
          ))}
        </Space>
      ),
    },
    { title: "责任单位", dataIndex: "responsible_unit", width: 130 },
    {
      title: "快照状态",
      dataIndex: "snapshot",
      width: 110,
      render: (snapshot: CardSummary["snapshot"], record) =>
        record.stale ? (
          <Tag color="orange">数据已变更</Tag>
        ) : snapshot ? (
          <Tag color="blue">
            V1.{snapshot.version} {snapshot.source === "rule" ? "规则" : "AI"}
          </Tag>
        ) : (
          <span>—</span>
        ),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      render: (_: unknown, record) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => openPreview(record.object_id)}>
            预览
          </Button>
          <Button type="link" size="small" onClick={() => openPreview(record.object_id, true)}>
            AI 优化
          </Button>
          <Button type="link" size="small" onClick={() => void copyLink(record)}>
            链接
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="风险告知卡"
        subtitle="基于风险点评估数据自动生成安全风险告知卡，可导出 Word 或复制公开链接"
        extra={
          <Space>
            <Button onClick={() => void refetch()}>刷新</Button>
            <Button
              type="primary"
              loading={exporting}
              disabled={exporting}
              onClick={exportAll}
            >
              批量导出 Word
            </Button>
          </Space>
        }
      />

      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          allowClear
          placeholder="风险等级"
          style={{ width: 140 }}
          value={filters.level}
          onChange={(value?: string) =>
            setFilters((f) => ({
              ...f,
              level: value === "全部" || !value ? undefined : value,
            }))
          }
          options={[
            { value: "全部", label: "全部" },
            ...LEVEL_OPTIONS.map((level) => ({ value: level, label: level })),
          ]}
        />
        <Input.Search
          allowClear
          placeholder="搜索风险点名称/责任单位"
          style={{ width: 240 }}
          onSearch={(value) =>
            setFilters((f) => ({ ...f, keyword: value || undefined }))
          }
        />
      </Space>

      {data.length > 0 && (
        <Space style={{ marginBottom: 12 }} wrap>
          <span>总数 {data.length}</span>
          {LEVEL_OPTIONS.map((level) => {
            const count = stats.counts[level] ?? 0;
            if (!count) return null;
            const color = stats.colors[level] ?? RISK_LEVEL_COLORS[level];
            return (
              <Tag key={level} color={color}>
                {level} {count}
              </Tag>
            );
          })}
        </Space>
      )}

      <Table<CardSummary>
        rowKey="object_id"
        loading={isLoading}
        dataSource={data}
        columns={columns}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys as string[]),
        }}
        pagination={{ pageSize: 20, showTotal: (total) => `共 ${total} 条` }}
        locale={{
          emptyText: isError ? "加载失败，请稍后重试" : "请先在风险管理中添加风险点",
        }}
      />

      {selected.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <Space>
            <span>已选 {selected.length} 项</span>
            <Button
              type="primary"
              loading={exporting}
              disabled={exporting}
              onClick={() => void doExport(selected)}
            >
              导出选中卡片 Word
            </Button>
            <Button onClick={() => setSelected([])}>清除选择</Button>
          </Space>
        </div>
      )}
    </div>
  );
}
