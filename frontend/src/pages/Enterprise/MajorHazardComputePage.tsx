import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Collapse,
  Descriptions,
  Empty,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import {
  CheckCircleOutlined,
  FileWordOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import {
  computeCalculation,
  downloadUnitReport,
  listCalculations,
  listUnits,
  previewCalculation,
} from "@/services/majorHazardService";
import type {
  MajorHazardCalculation,
  MajorHazardPreviewResult,
  PreviewChemicalItem,
} from "@/types/majorHazard";
import { ALPHA_HINT, formatQty, levelColor } from "@/utils/majorHazardFormat";

const { Text, Paragraph } = Typography;

/**
 * 防抖：改动输入后等 `delay` 毫秒再触发请求。
 *
 * 内联实现而不引依赖——只需要十来行，为它装一个包不划算。
 * 预览要防抖是因为用户调暴露人数时会连续触发十几次请求。
 */
function useDebounced<T>(value: T, delay = 500): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function MajorHazardComputePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const qc = useQueryClient();
  const { message } = AntApp.useApp();

  const [unitId, setUnitId] = useState<string>(sp.get("unitId") ?? "");
  const [population, setPopulation] = useState<number>(0);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);

  const debouncedPopulation = useDebounced(population, 500);

  const { data: units } = useQuery({
    queryKey: ["major-hazard-units", id],
    queryFn: () => listUnits(id!),
    enabled: !!id,
  });

  /**
   * 实际使用的单元 id：显式选过就用选的，否则回落列表第一个。
   *
   * 用派生值而不是 useEffect 同步——后者会触发 react-hooks/set-state-in-effect，
   * 而且"默认选第一个"本来就是渲染期的计算，不该走状态同步。
   */
  const effectiveUnitId = unitId || units?.[0]?.id || "";

  const onSelectUnit = (v: string) => {
    setUnitId(v);
    sp.set("unitId", v);
    setSp(sp, { replace: true });
  };

  /**
   * 预览：只算不写快照。
   * retry: false —— 422（单元未录品种）是业务状态，不该重试。
   */
  const preview = useQuery<MajorHazardPreviewResult>({
    queryKey: ["major-hazard-preview", effectiveUnitId, debouncedPopulation],
    queryFn: () => previewCalculation(effectiveUnitId, debouncedPopulation),
    enabled: !!effectiveUnitId,
    retry: false,
  });

  const { data: history } = useQuery({
    queryKey: ["major-hazard-calculations", effectiveUnitId],
    queryFn: () => listCalculations(effectiveUnitId),
    enabled: !!effectiveUnitId,
  });

  /** 单元未录品种时后端返回 422，这里当"待录入"状态处理，不弹错误。 */
  const isEmptyUnit =
    !!preview.error &&
    (preview.error as { response?: { status?: number } })?.response?.status === 422;

  const doCompute = async () => {
    setSaving(true);
    try {
      const snap = await computeCalculation(effectiveUnitId, population);
      message.success(`已固化第 ${snap.seq} 次计算结果`);
      qc.invalidateQueries({ queryKey: ["major-hazard-calculations", effectiveUnitId] });
    } catch {
      // 全局拦截器已提示
    } finally {
      setSaving(false);
    }
  };

  /**
   * 导出辨识报告。报告必须有结论，故以"是否已有快照"为准禁用按钮；
   * 后端仍会再拦一次（422），这里用 warning 显示原因而不是报错。
   */
  const doExport = async () => {
    setExporting(true);
    try {
      await downloadUnitReport(effectiveUnitId);
      message.success("辨识报告已开始下载");
    } catch (err) {
      message.warning(err instanceof Error ? err.message : "报告导出失败");
    } finally {
      setExporting(false);
    }
  };

  const chemColumns: TableColumnsType<PreviewChemicalItem> = [
    { title: "危险化学品", dataIndex: "name" },
    { title: "qi(t)", width: 100, render: (_, r) => formatQty(r.q) },
    { title: "Qi(t)", width: 100, render: (_, r) => formatQty(r.Q) },
    { title: "βi", width: 80, render: (_, r) => formatQty(r.beta, 3) },
    { title: "qi/Qi", width: 100, render: (_, r) => formatQty(r.q_over_Q) },
    {
      title: "βi×qi/Qi",
      width: 120,
      render: (_, r) => formatQty(r.beta_times_q_over_Q),
    },
  ];

  const historyColumns: TableColumnsType<MajorHazardCalculation> = [
    { title: "序号", dataIndex: "seq", width: 70 },
    {
      title: "计算时间",
      width: 180,
      render: (_, r) =>
        r.calculated_at ? new Date(r.calculated_at).toLocaleString("zh-CN") : "—",
    },
    { title: "暴露人数", dataIndex: "exposed_population", width: 100 },
    { title: "α", width: 70, render: (_, r) => formatQty(r.alpha, 2) },
    { title: "s", width: 90, render: (_, r) => formatQty(r.s_value) },
    { title: "R", width: 90, render: (_, r) => formatQty(r.r_value) },
    {
      title: "等级",
      width: 90,
      render: (_, r) => (
        <Tag color={levelColor(r.level)}>{r.is_major_hazard ? r.level ?? "构成" : "不构成"}</Tag>
      ),
    },
  ];

  const selectedUnit = useMemo(
    () => units?.find((u) => u.id === effectiveUnitId),
    [units, effectiveUnitId],
  );

  return (
    <>
      <PageHeader
        title="计算与分级"
        subtitle="按 GB 18218-2018 式(1) 辨识、式(2) 分级"
        extra={
          <Space>
            <Select
              style={{ minWidth: 220 }}
              placeholder="选择单元"
              value={effectiveUnitId || undefined}
              onChange={onSelectUnit}
              options={(units ?? []).map((u) => ({
                value: u.id,
                label: `${u.name}（${u.unit_type === "storage" ? "储存单元" : "生产单元"}）`,
              }))}
            />
            <Button onClick={() => preview.refetch()} icon={<ReloadOutlined />}>
              重新预览
            </Button>
          </Space>
        }
      />

      {!effectiveUnitId && <Empty description="请先选择要计算的单元" />}

      {effectiveUnitId && (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {isEmptyUnit && (
            <Alert
              type="info"
              showIcon
              message="该单元尚未录入危险化学品"
              description="单元内没有任何品种时无法计算——空单元不是“不构成重大危险源”，而是数据未填。"
              action={
                <Button
                  size="small"
                  type="primary"
                  onClick={() =>
                    navigate(`/enterprises/${id}/major-hazard/units/${effectiveUnitId}`)
                  }
                >
                  去录入品种
                </Button>
              }
            />
          )}

          <Card
            title={
              <Space>
                <span>厂外 500m 内可能暴露人员数量</span>
                <InputNumber
                  min={0}
                  style={{ width: 120 }}
                  value={population}
                  onChange={(v) => setPopulation(v ?? 0)}
                />
              </Space>
            }
            extra={<Text type="secondary" style={{ fontSize: 12 }}>α 档位：{ALPHA_HINT}</Text>}
          >
            <div
              style={{
                border: "1px dashed #bfbfbf",
                background: "#fafafa",
                borderRadius: 6,
                padding: 16,
              }}
            >
              <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 8 }}>
                预览（未保存）——改动上方人数后自动重算，点「固化本次结果」才写入快照
              </div>
              {preview.isLoading && <Text type="secondary">计算中…</Text>}
              {!preview.isLoading && !preview.data && !isEmptyUnit && (
                <Text type="secondary">暂无预览结果</Text>
              )}
              {preview.data && (
                <Descriptions column={4} size="small">
                  <Descriptions.Item label="α">
                    {formatQty(preview.data.alpha, 2)}
                  </Descriptions.Item>
                  <Descriptions.Item label="s = Σqi/Qi">
                    {formatQty(preview.data.s_value)}
                  </Descriptions.Item>
                  <Descriptions.Item label="R = α×Σβi×(qi/Qi)">
                    <Text strong>{formatQty(preview.data.r_value)}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="等级">
                    <Tag color={levelColor(preview.data.level)}>
                      {preview.data.is_major_hazard
                        ? preview.data.level ?? "构成"
                        : "不构成"}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>
              )}
            </div>

            <Space style={{ marginTop: 12 }}>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                loading={saving}
                disabled={!preview.data}
                onClick={doCompute}
              >
                固化本次结果
              </Button>
              <Tooltip
                title={
                  history?.length
                    ? undefined
                    : "请先固化一次计算结果——没有结论的报告不能导出"
                }
              >
                <Button
                  icon={<FileWordOutlined />}
                  loading={exporting}
                  disabled={!history?.length}
                  onClick={doExport}
                >
                  导出辨识报告
                </Button>
              </Tooltip>
              <Text type="secondary" style={{ fontSize: 12 }}>
                快照不可修改；改了数据要重算，会产生新的一条记录
              </Text>
            </Space>

            {preview.data?.chemicals?.length ? (
              <Collapse
                style={{ marginTop: 12 }}
                items={[
                  {
                    key: "detail",
                    label: `逐品种计算明细（${preview.data.chemicals.length} 项）`,
                    children: (
                      <Table<PreviewChemicalItem>
                        rowKey="name"
                        size="small"
                        pagination={false}
                        dataSource={preview.data.chemicals}
                        columns={chemColumns}
                      />
                    ),
                  },
                ]}
              />
            ) : null}
          </Card>

          <Card
            title={<Space><ThunderboltOutlined />计算历史（不可变快照）</Space>}
            extra={
              selectedUnit && (
                <Button
                  onClick={() =>
                    navigate(
                      `/enterprises/${id}/major-hazard/record?unitId=${effectiveUnitId}`,
                    )
                  }
                >
                  档案与备案
                </Button>
              )
            }
          >
            <Paragraph type="secondary" style={{ fontSize: 12 }}>
              每次固化产生一条快照，记录当时的全部输入与结论，可原样复算。
            </Paragraph>
            <Table<MajorHazardCalculation>
              rowKey="id"
              size="small"
              dataSource={history ?? []}
              columns={historyColumns}
              pagination={{ defaultPageSize: 10, showSizeChanger: true }}
              locale={{ emptyText: "尚无计算记录，点上方「固化本次结果」生成第一条" }}
              expandable={{
                expandedRowRender: (r) => (
                  <Text type="secondary">
                    公式版本 {r.formula_version} | α={formatQty(r.alpha, 2)} | s=
                    {formatQty(r.s_value)} | R={formatQty(r.r_value)}
                  </Text>
                ),
              }}
            />
          </Card>
        </Space>
      )}
    </>
  );
}
