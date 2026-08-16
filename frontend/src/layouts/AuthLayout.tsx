import { Outlet } from "react-router-dom";
import { Layout, Typography } from "antd";
import AppIcon from "@/components/common/AppIcon";

const { Content } = Layout;
const { Title, Paragraph } = Typography;

export function AuthLayout() {
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <div
        style={{
          display: "flex",
          minHeight: "100vh",
        }}
      >
        {/* 左侧品牌区 */}
        <div
          style={{
            flex: 1,
            background: "linear-gradient(135deg, #1a365d 0%, #2563eb 100%)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: 48,
            color: "#fff",
          }}
        >
          <AppIcon name="safety" size={64} style={{ marginBottom: 24 }} />
          <Title level={2} style={{ color: "#fff", marginBottom: 8 }}>
            数字化应急预案自动生成系统
          </Title>
          <Paragraph style={{ color: "rgba(255,255,255,0.7)", fontSize: 16 }}>
            基于 GB/T 29639-2020 标准，AI 辅助编制
          </Paragraph>
        </div>

        {/* 右侧表单区 */}
        <div
          style={{
            flex: 1,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            background: "#f5f5f5",
          }}
        >
          <Content style={{ width: 400, padding: 24 }}>
            <Outlet />
          </Content>
        </div>
      </div>
    </Layout>
  );
}
