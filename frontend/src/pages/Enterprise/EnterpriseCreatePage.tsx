import { useNavigate } from "react-router-dom";
import { message } from "antd";
import axios from "axios";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

export default function EnterpriseCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createEnterprise,
    onSuccess: (data) => {
      message.success("企业创建成功");
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      navigate(`/enterprises/${data.id}`);
    },
    onError: (err: unknown) => message.error(extractDetail(err) || "创建失败"),
  });
  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="新建企业" onBack={() => navigate("/enterprises")} />
      <EnterpriseInfoCards
        onCreate={async (values) => {
          mutation.mutate(values as never);
        }}
      />
    </div>
  );
}
