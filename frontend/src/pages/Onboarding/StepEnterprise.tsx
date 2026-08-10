import { Button } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import EnterpriseInfoWorkspace from "@/components/enterprise/EnterpriseInfoWorkspace";
import type { CandidateItem } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
  /** 资料包导入后分发到本步骤的候选（含来源文件） */
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

export default function StepEnterprise({
  enterpriseId,
  onDone,
  onPrev,
  imported,
  onAddImported,
  onRemoveImported,
}: Props) {
  const { isError } = useQuery({
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
      <div>
        <h3>企业信息</h3>
        <p style={{ color: "#666", fontSize: 13 }}>
          先确认企业是谁——这是整份预案的事实基础
        </p>
      </div>
      <EnterpriseInfoWorkspace
        enterpriseId={enterpriseId}
        onDone={onDone}
        imported={imported}
        onAddImported={onAddImported}
        onRemoveImported={onRemoveImported}
      />
    </div>
  );
}
