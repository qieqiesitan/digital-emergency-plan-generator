import { useNavigate } from "react-router-dom";
import { Alert, Button, Card, Col, Row, Skeleton, Space, Statistic, Typography } from "antd";
import {
  BankOutlined,
  FileTextOutlined,
  FireOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { getPlatformOverview } from "@/services/platformService";

const { Text } = Typography;

/** 严重度：一、二级重大危险源是监管重点，非 0 时按警示色显示。 */
const DANGER = "#cf1322";

export default function PlatformOverviewPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["platform-overview"],
    queryFn: getPlatformOverview,
  });

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  if (isError || !data) {
    return (
      <Alert
        type="error"
        showIcon
        message="跨企业总览加载失败"
        description="网络异常或服务暂不可用，请检查连接后重试。数据未丢失，恢复后会自动显示。"
        action={
          <Button size="small" onClick={() => refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  const level12 = data.major_hazard_level_1_2;

  const cards = [
    {
      key: "enterprises",
      title: "企业数",
      value: data.enterprises,
      icon: <BankOutlined />,
      hint: "进入企业列表",
    },
    {
      key: "risk_points",
      title: "风险点",
      value: data.risk_points,
      icon: <FileTextOutlined />,
      hint: "按企业查看风险分级管控",
    },
    {
      key: "hazards",
      title: "隐患",
      value: data.hazards,
      icon: <WarningOutlined />,
      hint: "按企业查看隐患排查治理",
    },
    {
      key: "major_hazard_units",
      title: "重大危险源单元",
      value: data.major_hazard_units,
      icon: <FireOutlined />,
      hint: "按企业查看重大危险源",
    },
    {
      key: "major_hazard_level_1_2",
      title: "一、二级重大危险源",
      value: level12,
      icon: <SafetyCertificateOutlined />,
      hint: "监管重点：按企业查看重大危险源",
      danger: level12 > 0,
    },
    {
      key: "work_tickets",
      title: "作业票",
      value: data.work_tickets,
      icon: <ToolOutlined />,
      hint: "按企业查看特殊作业",
    },
  ];

  return (
    <>
      <PageHeader
        title="跨企业总览"
        subtitle="这里是全平台汇总，单企业详情请进入企业驾驶舱"
        extra={
          <Button onClick={() => refetch()}>刷新</Button>
        }
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="平台运营视角"
        description="以下数字是全部企业的合计值。风险点 / 隐患 / 重大危险源 / 作业票都是按企业维度管理的，点击卡片进入企业列表后选择企业查看明细。"
      />

      <Row gutter={[16, 16]}>
        {cards.map((card) => (
          <Col xs={12} sm={8} lg={8} xxl={4} key={card.key}>
            <Card hoverable onClick={() => navigate("/enterprises")}>
              <Statistic
                title={card.title}
                value={card.value}
                prefix={card.icon}
                styles={{ content: { color: card.danger ? DANGER : undefined } }}
              />
              <Space style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {card.hint}
                </Text>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </>
  );
}
