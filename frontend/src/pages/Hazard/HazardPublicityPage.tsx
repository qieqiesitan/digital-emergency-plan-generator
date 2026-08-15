import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Card,
  Empty,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { CopyOutlined, PrinterOutlined, ReloadOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getHazardPublicity, resetHazardPublicityToken } from "@/services/hazardService";
import type { HazardPublicityItem } from "@/types/hazard";
import { PageHeader } from "@/components/common/PageHeader";

const { Text } = Typography;

const LEVEL_LABELS: Record<string, string> = {
  major: "重大",
  general: "一般",
};

const SCOPE_OPTIONS = [
  { label: "全部", value: "all" },
  { label: "进行中", value: "ongoing" },
  { label: "已闭环", value: "closed" },
];

function tokenCacheKey(eid: string): string {
  return `hazard_publicity_token:${eid}`;
}

function readCachedToken(eid: string): { token: string; link: string } | null {
  try {
    const raw = localStorage.getItem(tokenCacheKey(eid));
    return raw ? (JSON.parse(raw) as { token: string; link: string }) : null;
  } catch {
    return null;
  }
}

/** 企业内隐患公示页（§11.2）：公示列表（scope 过滤）+ 公开 token 管理 + 打印样式。 */
export default function HazardPublicityPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  // 以企业 id 作 key 强制重挂载，避免跨企业切换时残留上一企业的 token 缓存
  return <HazardPublicityContent key={enterpriseId} enterpriseId={enterpriseId} />;
}

function HazardPublicityContent({ enterpriseId }: { enterpriseId: string }) {
  const navigate = useNavigate();
  const { message, modal } = AntApp.useApp();
  const [scope, setScope] = useState<string>("all");
  const [tokenInfo, setTokenInfo] = useState<{ token: string; link: string } | null>(() =>
    readCachedToken(enterpriseId),
  );
  const [tokenLoading, setTokenLoading] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["hazard-publicity", enterpriseId, scope],
    queryFn: () => getHazardPublicity(enterpriseId, scope === "all" ? undefined : scope),
    enabled: !!enterpriseId,
  });

  const publicUrl = tokenInfo ? `${window.location.origin}${tokenInfo.link}` : "";

  const copyLink = async () => {
    if (!publicUrl) return;
    try {
      await navigator.clipboard.writeText(publicUrl);
      message.success("公开链接已复制");
    } catch {
      message.error("复制失败，请手动复制");
    }
  };

  const handleResetToken = () => {
    modal.confirm({
      title: tokenInfo ? "确认重置公示链接？" : "生成公示链接？",
      content: tokenInfo
        ? "重置后原链接将立即失效，需要重新公示新链接。"
        : "将生成一个公开脱敏公示链接，可对外公示企业隐患整改情况。",
      okText: tokenInfo ? "确认重置" : "生成",
      cancelText: "取消",
      onOk: close => {
        setTokenLoading(true);
        resetHazardPublicityToken(enterpriseId)
          .then(result => {
            setTokenInfo(result);
            localStorage.setItem(tokenCacheKey(enterpriseId), JSON.stringify(result));
            message.success(tokenInfo ? "链接已重置" : "链接已生成");
            close();
          })
          .catch(() => {
            message.error("操作失败，请稍后重试");
          })
          .finally(() => setTokenLoading(false));
      },
    });
  };

  const columns: TableColumnsType<HazardPublicityItem> = [
    { title: "编号", dataIndex: "code", width: 110 },
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v}</span>
        </Tooltip>
      ),
    },
    {
      title: "等级",
      dataIndex: "level",
      width: 80,
      render: (v: string) => {
        if (!v) return <span>—</span>;
        return (
          <Tag color={v === "major" ? "red" : "blue"}>{LEVEL_LABELS[v] || v}</Tag>
        );
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: string) => <span>{v}</span>,
    },
    {
      title: "整改情况",
      dataIndex: "rectification",
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v}</span>
        </Tooltip>
      ),
    },
    { title: "来源", dataIndex: "source_type", width: 110 },
  ];

  if (isLoading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }

  return (
    <div className="hazard-publicity-page">
      <style>{`@media print {
        .hazard-publicity-page .hazard-publicity-actions,
        .hazard-publicity-page button,
        .hazard-publicity-page .ant-segmented { display: none !important; }
      }`}</style>
      <PageHeader
        title="隐患公示"
        subtitle="面向全员公示隐患整改情况，可打印公告或生成公开脱敏链接"
        onBack={() => navigate(-1)}
        extra={
          <Space wrap className="hazard-publicity-actions">
            <Button icon={<ReloadOutlined />} onClick={() => void refetch()}>
              刷新
            </Button>
            <Button icon={<PrinterOutlined />} onClick={() => window.print()}>
              打印
            </Button>
          </Space>
        }
      />

      <Card
        size="small"
        title="公开链接（数据已脱敏，无需登录）"
        className="hazard-publicity-actions"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            {tokenInfo ? (
              <Button icon={<CopyOutlined />} onClick={() => void copyLink()}>
                复制公开链接
              </Button>
            ) : null}
            <Button danger loading={tokenLoading} onClick={handleResetToken}>
              {tokenInfo ? "重置链接" : "生成链接"}
            </Button>
          </Space>
        }
      >
        {tokenInfo ? (
          <Space wrap>
            <SafetyCertificateOutlined style={{ color: "#52c41a", fontSize: 16 }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              当前公开 token：
            </Text>
            <Typography.Text code style={{ fontSize: 13 }}>
              {tokenInfo.token}
            </Typography.Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              链接 {publicUrl}
            </Text>
          </Space>
        ) : (
          <Text type="secondary">
            尚未生成公开链接。点击「生成链接」后将创建公开脱敏公示页（/h/:token）。
          </Text>
        )}
      </Card>

      <Card
        size="small"
        title="公示列表"
        extra={
          <Segmented
            options={SCOPE_OPTIONS}
            value={scope}
            onChange={value => setScope(String(value))}
          />
        }
      >
        {isError || !data ? (
          <Empty description="公示数据加载失败，请稍后重试">
            <Button type="primary" onClick={() => void refetch()}>
              重新加载
            </Button>
          </Empty>
        ) : (
          <Table<HazardPublicityItem>
            rowKey="code"
            dataSource={data}
            columns={columns}
            size="middle"
            scroll={{ x: 760 }}
            pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
            locale={{ emptyText: "暂无公示数据" }}
          />
        )}
      </Card>
    </div>
  );
}
