import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Badge, Button, Input, Select, Space, Table, Tag, Tooltip } from "antd";
import type { TableColumnsType } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getControlList, exportControlList, listZones } from "@/services/riskManagementService";
import type { ControlListRow } from "@/services/riskManagementService";
import { listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
import { PageHeader } from "@/components/common/PageHeader";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

const LEVEL_OPTIONS = ["重大", "较大", "一般", "低"];
const CONTROL_LEVEL_OPTIONS = ["岗位", "班组", "部门", "企业"];

type ListFilters = {
  floor_id?: string;
  zone_id?: string;
  level?: string;
  control_level?: string;
  keyword?: string;
};

function LevelTag({ level }: { level?: string }) {
  const color = level ? RISK_LEVEL_COLORS[level] : undefined;
  if (!color) return <span>—</span>;
  return <Tag color={color}>{level}</Tag>;
}

/** 风险分级管控清单页（筛选 + 分页 + Excel 导出）。 */
export default function RiskControlListPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [filters, setFilters] = useState<ListFilters>({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [exporting, setExporting] = useState(false);

  const { data: floors = [] } = useQuery({
    queryKey: ["enterprise-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: zones = [] } = useQuery({
    queryKey: ["risk-zones", enterpriseId],
    queryFn: () => listZones(enterpriseId),
    enabled: !!enterpriseId,
  });

  // 后端 control-list 未传 floor_id 时 _resolve_zone_floor 缺省解析默认楼层；
  // 前端分区下拉按「所选楼层 ?? 默认楼层」过滤，与后端查询口径保持一致。
  const activeFloorId = filters.floor_id ?? floors.find(f => f.is_default)?.id;
  const zoneOptions = useMemo(
    () =>
      zones
        .filter(z => !activeFloorId || z.floor_id === activeFloorId)
        .map(z => ({ label: z.name, value: z.id })),
    [zones, activeFloorId],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["risk-control-list", enterpriseId, filters, page, pageSize],
    queryFn: () => getControlList(enterpriseId, { ...filters, page, size: pageSize }),
    enabled: !!enterpriseId,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const patchFilters = (patch: Partial<ListFilters>) => {
    setFilters(f => ({ ...f, ...patch }));
    setPage(1);
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const res = await exportControlList(enterpriseId, filters);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "risk_control_list.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch {
      message.error("导出失败，请稍后重试");
    } finally {
      setExporting(false);
    }
  };

  const columns: TableColumnsType<ControlListRow> = [
    { title: "分区", dataIndex: "zone", width: 110, ellipsis: true },
    { title: "风险点", dataIndex: "object", width: 130, ellipsis: true },
    { title: "单元", dataIndex: "unit", width: 90, ellipsis: true },
    { title: "事故类型", dataIndex: "accident", width: 110, ellipsis: true },
    { title: "固有等级", dataIndex: "inherent", width: 80, render: (level?: string) => <LevelTag level={level} /> },
    { title: "现有等级", dataIndex: "current", width: 80, render: (level?: string) => <LevelTag level={level} /> },
    { title: "管控层级", dataIndex: "control_level", width: 85 },
    {
      title: "未闭环隐患",
      dataIndex: "open_hazard_count",
      width: 110,
      render: (count?: number) =>
        count && count > 0 ? <Badge color="red" text={`未闭环 ${count}`} /> : <span>—</span>,
    },
    {
      title: "管控措施",
      dataIndex: "measures",
      ellipsis: true,
      render: (measures: string) => (
        <Tooltip title={measures}><span>{measures}</span></Tooltip>
      ),
    },
    { title: "责任单位", dataIndex: "unit_name", width: 120, ellipsis: true },
    { title: "责任人", dataIndex: "person", width: 85 },
    { title: "联系电话", dataIndex: "phone", width: 120, render: (phone?: string) => phone || "-" },
  ];

  return (
    <div>
      <PageHeader
        title="风险分级管控清单"
        subtitle="按楼层/分区/等级/管控层级筛选，支持导出 Excel 台账"
        onBack={() => navigate(-1)}
        extra={
          <Button type="primary" loading={exporting} onClick={() => void handleExport()}>
            导出 Excel
          </Button>
        }
      />

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="楼层"
          style={{ width: 150 }}
          value={filters.floor_id}
          options={floors.map(f => ({ label: f.name, value: f.id }))}
          onChange={value => patchFilters({ floor_id: value, zone_id: undefined })}
        />
        <Select
          allowClear
          placeholder="分区"
          style={{ width: 150 }}
          value={filters.zone_id}
          options={zoneOptions}
          disabled={!!filters.floor_id && zoneOptions.length === 0}
          onChange={value => patchFilters({ zone_id: value })}
        />
        <Select
          allowClear
          placeholder="风险等级"
          style={{ width: 140 }}
          value={filters.level}
          options={LEVEL_OPTIONS.map(level => ({ label: level, value: level }))}
          onChange={value => patchFilters({ level: value })}
        />
        <Select
          allowClear
          placeholder="管控层级"
          style={{ width: 140 }}
          value={filters.control_level}
          options={CONTROL_LEVEL_OPTIONS.map(level => ({ label: level, value: level }))}
          onChange={value => patchFilters({ control_level: value })}
        />
        <Input.Search
          allowClear
          placeholder="搜索分区/风险点名称"
          style={{ width: 220 }}
          onSearch={value => patchFilters({ keyword: value || undefined })}
        />
      </Space>

      <Table<ControlListRow>
        rowKey={(record, index) => `${record.zone}-${record.object}-${record.accident}-${index}`}
        loading={isLoading}
        dataSource={items}
        columns={columns}
        scroll={{ x: 1220 }}
        locale={{ emptyText: isError ? "加载失败，请稍后重试" : "暂无管控清单数据" }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: t => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />
    </div>
  );
}
