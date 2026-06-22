import { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spin, Button, Typography, message, Table, Tag, Collapse, Statistic, Row, Col, Card } from "antd";
import { ArrowLeftOutlined, DownloadOutlined } from "@ant-design/icons";
import { getRiskAssessmentPreview, downloadRiskAssessment } from "@/services/riskAssessmentService";
import type { RiskAssessmentPreview } from "@/types/riskAssessment";

const { Title, Text } = Typography;

/* ── 风险等级判定 ── */
function getRiskLevelTag(r: number) {
  if (r <= 8)   return { label: "低风险",  color: "green" };
  if (r <= 12)  return { label: "一般风险", color: "orange" };
  if (r <= 16)  return { label: "较大风险", color: "volcano" };
  return                      { label: "重大风险", color: "red" };
}

/* ── 从 HTML 中解析 L×S 风险评估计算表 ── */
interface RiskTableRow {
  key: number;
  accidentType: string;
  l: number;
  s: number;
  r: number;
  level: string;
}

function parseRiskTable(html: string): RiskTableRow[] {
  const rows: RiskTableRow[] = [];
  const trRegex = /<tr[^>]*>[\s\S]*?<\/tr>/gi;
  const tdRegex = /<td[^>]*>([\s\S]*?)<\/td>/gi;

  const matches = html.match(trRegex) || [];
  for (const tr of matches) {
    const tds: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = tdRegex.exec(tr)) !== null) {
      tds.push(m[1].replace(/<[^>]+>/g, "").trim());
    }
    tdRegex.lastIndex = 0;

    // 需要至少 5 列：事故类型, L, S, R, 风险等级
    if (tds.length >= 5) {
      const l = parseInt(tds[1], 10);
      const s = parseInt(tds[2], 10);
      const r = parseInt(tds[3], 10);
      const isHeader =
        tds[0].includes("事故类型") || tds[0].includes("序号") ||
        tds[0].includes("风险") && tds[1].includes("L");
      if (!isNaN(l) && !isNaN(s) && !isNaN(r) && !isHeader) {
        rows.push({
          key: rows.length + 1,
          accidentType: tds[0],
          l,
          s,
          r,
          level: tds[4] || getRiskLevelTag(r).label,
        });
      }
    }
  }
  return rows;
}

/* ── 统计各风险等级数量 ── */
function countByLevel(rows: RiskTableRow[]) {
  const counts: Record<string, number> = { "重大风险": 0, "较大风险": 0, "一般风险": 0, "低风险": 0 };
  for (const row of rows) {
    const tag = getRiskLevelTag(row.r);
    counts[tag.label] = (counts[tag.label] || 0) + 1;
  }
  return counts;
}

const levelColorMap: Record<string, string> = {
  "重大风险": "#cf1322",
  "较大风险": "#d4380d",
  "一般风险": "#d46b08",
  "低风险": "#389e0d",
};

const levelBgMap: Record<string, string> = {
  "重大风险": "#fff1f0",
  "较大风险": "#fff2e8",
  "一般风险": "#fffbe6",
  "低风险": "#f6ffed",
};

export default function RiskAssessmentPreview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<RiskAssessmentPreview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getRiskAssessmentPreview(id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [id]);

  const handleExport = async () => {
    if (id) {
      try { await downloadRiskAssessment(id); }
      catch (err: any) { message.error(err.message || "下载失败"); }
    }
  };

  const riskRows = useMemo(() => (data ? parseRiskTable(data.html) : []), [data]);
  const levelCounts = useMemo(() => countByLevel(riskRows), [riskRows]);

  /* ── 评估计算表列定义 ── */
  const columns = [
    { title: "序号", dataIndex: "key", width: 60, align: "center" as const },
    { title: "事故类型", dataIndex: "accidentType", ellipsis: true },
    {
      title: "可能性 L",
      dataIndex: "l",
      width: 80,
      align: "center" as const,
      render: (v: number) => <Text strong>{v}</Text>,
    },
    {
      title: "严重性 S",
      dataIndex: "s",
      width: 80,
      align: "center" as const,
      render: (v: number) => <Text strong>{v}</Text>,
    },
    {
      title: "风险值 R(L×S)",
      dataIndex: "r",
      width: 100,
      align: "center" as const,
      render: (v: number) => <Text strong style={{ fontSize: 15 }}>{v}</Text>,
    },
    {
      title: "风险等级",
      dataIndex: "level",
      width: 100,
      align: "center" as const,
      render: (_: string, record: RiskTableRow) => {
        const tag = getRiskLevelTag(record.r);
        return <Tag color={tag.color}>{tag.label}</Tag>;
      },
    },
  ];

  // L/S 判定准则参考表
  const lCriteria = [
    { level: 1, desc: "有充分、有效的防范控制监测保护措施，极不可能发生" },
    { level: 2, desc: "危害一旦发生能及时发现并定期监测，过去偶尔发生" },
    { level: 3, desc: "曾发生类似事故，或在异常情况下可能发生" },
    { level: 4, desc: "危害常发生，控制措施不当或未有效执行" },
    { level: 5, desc: "没有防范监测控制措施，正常情况下经常发生" },
  ];

  const sCriteria = [
    { level: 1, desc: "无伤亡，不需要疏散，无财产损失" },
    { level: 2, desc: "轻微受伤，小范围疏散，财产损失 ＜10 万元" },
    { level: 3, desc: "截肢/骨折/慢性病，疏散整个功能分区，财产损失 ＜10 万元" },
    { level: 4, desc: "丧失劳动能力，疏散整个楼层，财产损失 ＜25 万元" },
    { level: 5, desc: "死亡，疏散整个建筑，财产损失 ≥50 万元" },
  ];

  const rCriteria = [
    { r: "20-25", label: "重大", action: "在采取措施降低危害前不能继续作业，对改进措施进行评估", color: "red" },
    { r: "15-16", label: "较大", action: "采取紧急措施降低风险，建立运行控制程序，定期检查测量评估", color: "volcano" },
    { r: "9-12", label: "一般", action: "可考虑建立目标、操作规程，加强培训及沟通", color: "orange" },
    { r: "≤8", label: "低", action: "可考虑建立操作规程、作业指导书，定期检查", color: "green" },
  ];

  if (loading) return <Spin size="large" />;
  if (!data) return <div>报告不存在</div>;

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 16 }}>
      {/* 工具栏 */}
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/enterprises/${id}`)}>
          返回企业详情
        </Button>
        <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport}>
          下载 Word
        </Button>
      </div>

      {/* ── L×S 风险评估计算表 ── */}
      {riskRows.length > 0 && (
        <Card
          size="small"
          title={<Title level={5} style={{ margin: 0 }}>L×S 风险评估计算表</Title>}
          style={{ marginBottom: 20 }}
        >
          {/* 风险等级分布统计 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            {Object.entries(levelCounts).map(([level, count]) => (
              <Col span={6} key={level}>
                <Card
                  size="small"
                  style={{ background: levelBgMap[level], borderColor: levelColorMap[level] }}
                  bodyStyle={{ padding: "10px 16px" }}
                >
                  <Statistic
                    title={level}
                    value={count}
                    valueStyle={{ color: levelColorMap[level], fontSize: 24 }}
                    suffix="项"
                  />
                </Card>
              </Col>
            ))}
          </Row>

          {/* 评估计算表 */}
          <Table
            dataSource={riskRows}
            columns={columns}
            pagination={false}
            size="small"
            bordered
            style={{ marginBottom: 16 }}
            summary={() => (
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={2}>
                  <Text strong>合计 {riskRows.length} 种事故类型</Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={1} colSpan={4}>
                  <Text type="secondary">
                    最大风险值 R={Math.max(...riskRows.map((r) => r.r))}，
                    等级 {getRiskLevelTag(Math.max(...riskRows.map((r) => r.r))).label}
                  </Text>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            )}
          />

          {/* 判定准则参考（折叠） */}
          <Collapse
            ghost
            size="small"
            items={[
              {
                key: "criteria",
                label: <Text type="secondary" style={{ fontSize: 12 }}>L 可能性 / S 严重性 / R 风险等级 判定准则（点击展开）</Text>,
                children: (
                  <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 280 }}>
                      <Text strong style={{ fontSize: 12 }}>事故发生的可能性 L</Text>
                      <Table
                        dataSource={lCriteria}
                        columns={[
                          { title: "L", dataIndex: "level", width: 50, align: "center" as const },
                          { title: "判定标准", dataIndex: "desc" },
                        ]}
                        pagination={false}
                        size="small"
                        bordered
                      />
                    </div>
                    <div style={{ flex: 1, minWidth: 280 }}>
                      <Text strong style={{ fontSize: 12 }}>事件后果严重性 S</Text>
                      <Table
                        dataSource={sCriteria}
                        columns={[
                          { title: "S", dataIndex: "level", width: 50, align: "center" as const },
                          { title: "判定标准", dataIndex: "desc" },
                        ]}
                        pagination={false}
                        size="small"
                        bordered
                      />
                    </div>
                    <div style={{ width: "100%" }}>
                      <Text strong style={{ fontSize: 12 }}>安全风险等级判定准则及控制措施 R</Text>
                      <Table
                        dataSource={rCriteria}
                        columns={[
                          { title: "R 值", dataIndex: "r", width: 70, align: "center" as const },
                          {
                            title: "等级",
                            dataIndex: "label",
                            width: 70,
                            align: "center" as const,
                            render: (v: string) => <Tag color={rCriteria.find((c) => c.label === v)?.color}>{v}</Tag>,
                          },
                          { title: "应采取的行动/控制措施", dataIndex: "action" },
                        ]}
                        pagination={false}
                        size="small"
                        bordered
                      />
                    </div>
                  </div>
                ),
              },
            ]}
          />
        </Card>
      )}

      {/* 无数据时显示基本矩阵 */}
      {riskRows.length === 0 && (
        <Card
          size="small"
          title={<Title level={5} style={{ margin: 0 }}>L×S 风险矩阵参考</Title>}
          style={{ marginBottom: 20 }}
        >
          <Text type="secondary">
            报告中未检测到 L×S 评估数据表。报告正文中可能已包含风险矩阵内容，请查看下方报告。
          </Text>
        </Card>
      )}

      {/* 报告正文 */}
      <div
        style={{
          background: "#fff",
          padding: "60px 80px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          maxWidth: 794,
          margin: "0 auto",
        }}
      >
        <style>{`
          .risk-report-content table {
            border-collapse: collapse;
            width: 100%;
            margin: 12px 0;
            font-size: 13px;
          }
          .risk-report-content table th,
          .risk-report-content table td {
            border: 1px solid #333;
            padding: 6px 10px;
            text-align: left;
            vertical-align: top;
          }
          .risk-report-content table th {
            background-color: #f0f0f0;
            font-weight: bold;
          }
          .risk-report-content table tr:nth-child(even) td {
            background-color: #fafafa;
          }
        `}</style>
        <div
          className="risk-report-content"
          dangerouslySetInnerHTML={{ __html: data.html }}
        />
      </div>
    </div>
  );
}
