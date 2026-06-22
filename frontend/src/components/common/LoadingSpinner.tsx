import { Spin } from "antd";

export function LoadingSpinner({ tip = "加载中..." }: { tip?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: 48 }}>
      <Spin size="large" description={tip} />
    </div>
  );
}
