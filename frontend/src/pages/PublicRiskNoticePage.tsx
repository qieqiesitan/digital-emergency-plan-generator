import axios from "axios";
import { useParams } from "react-router-dom";
import { Button, Result, Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import RiskNoticeCard from "@/components/enterprise/RiskNoticeCard";
import { fetchPublicCard } from "@/services/riskNoticeCardService";

/** 公开只读页（/r/:token，无登录守卫）。 */
export default function PublicRiskNoticePage() {
  const { token = "" } = useParams<{ token: string }>();

  const { data: card, error, isLoading, isError, refetch } = useQuery({
    queryKey: ["public-risk-notice", token],
    queryFn: () => fetchPublicCard(token),
    retry: false,
  });

  if (isLoading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }

  if (isError || !card) {
    // 非 404（如网络错误）用 warning 语义图标 + 重试；404/无数据保持规格统一文案
    const isNetworkError =
      isError && !(axios.isAxiosError(error) && error.response?.status === 404);
    if (isNetworkError) {
      return (
        <Result
          status="warning"
          title="卡片不存在或链接已失效"
          extra={
            <Button type="primary" onClick={() => void refetch()}>
              重新加载
            </Button>
          }
        />
      );
    }
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
