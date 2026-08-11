import { useParams } from "react-router-dom";
import { Result, Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import RiskNoticeCard from "@/components/enterprise/RiskNoticeCard";
import { fetchPublicCard } from "@/services/riskNoticeCardService";

/** 公开只读页（/r/:token，无登录守卫）。 */
export default function PublicRiskNoticePage() {
  const { token = "" } = useParams<{ token: string }>();

  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["public-risk-notice", token],
    queryFn: () => fetchPublicCard(token),
    retry: false,
  });

  if (isLoading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }

  if (isError || !card) {
    return <Result status="404" title="卡片不存在或链接已失效" />;
  }

  return (
    <div style={{ margin: "0 auto", maxWidth: 480, padding: "24px 12px 16px" }}>
      <RiskNoticeCard card={card} />
      <div
        style={{
          color: "#8c8c8c",
          fontSize: 12,
          marginTop: 16,
          textAlign: "center",
        }}
      >
        公开只读页面 · 数据来自系统快照 · 无需登录
      </div>
    </div>
  );
}
