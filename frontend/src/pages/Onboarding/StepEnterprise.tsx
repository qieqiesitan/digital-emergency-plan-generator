import { Button } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
}

export default function StepEnterprise({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const { data: enterprise, isError } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });

  if (isError) {
    return (
      <div style={{ maxWidth: 720 }}>
        <h3>企业信息</h3>
        <p style={{ color: "#fa8c16" }}>企业不存在或已删除</p>
        <Button onClick={onPrev}>返回</Button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <h3>企业信息</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        先确认企业是谁——这是整份预案的事实基础
      </p>
      <EnterpriseInfoCards
        enterprise={enterprise}
        onSaved={async () => {
          queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
          queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
        }}
      />
      <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
        <Button type="primary" onClick={onDone}>
          标记完成，下一步 →
        </Button>
      </div>
    </div>
  );
}
