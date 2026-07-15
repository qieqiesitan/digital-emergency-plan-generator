import { Button, Space, Typography } from "antd";
import type { ReactNode } from "react";

const { Title, Text } = Typography;

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: string;
  extra?: ReactNode;
  onBack?: () => void;
  children?: ReactNode;
}

export function PageHeader({ title, subtitle, extra, onBack, children }: PageHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        marginBottom: 24,
        flexWrap: "wrap",
        gap: 12,
      }}
    >
      <div>
        <Space align="center">
          {onBack && <Button onClick={onBack} type="text">&larr; 返回</Button>}
          <Title level={4} style={{ margin: 0 }}>
            {title}
          </Title>
        </Space>
        {subtitle && (
          <Text type="secondary" style={{ fontSize: 13, display: "block", marginTop: 4 }}>
            {subtitle}
          </Text>
        )}
      </div>
      <Space wrap>
        {extra}
        {children}
      </Space>
    </div>
  );
}