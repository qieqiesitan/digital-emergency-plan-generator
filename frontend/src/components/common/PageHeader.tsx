import { Button, Space, Typography } from "antd";
import type { ReactNode } from "react";

const { Title } = Typography;

interface PageHeaderProps {
  title: ReactNode;
  extra?: ReactNode;
  onBack?: () => void;
}

export function PageHeader({ title, extra, onBack }: PageHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 24,
      }}
    >
      <Space>
        {onBack && <Button onClick={onBack} type="text">&larr; 返回</Button>}
        <Title level={4} style={{ margin: 0 }}>
          {title}
        </Title>
      </Space>
      {extra && <Space>{extra}</Space>}
    </div>
  );
}
