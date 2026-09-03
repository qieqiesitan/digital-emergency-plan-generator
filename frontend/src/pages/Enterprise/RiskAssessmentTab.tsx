import { useEffect, useState } from "react";
import ReportWorkspace from "@/components/report/ReportWorkspace";
import { riskAssessmentAdapter } from "@/services/reportAdapters";
import { getRiskAssessmentChapters } from "@/services/riskAssessmentService";
import type { ChapterDef } from "@/services/riskAssessmentService";

interface Props {
  enterpriseId: string;
}

export default function RiskAssessmentTab({ enterpriseId }: Props) {
  const [chapters, setChapters] = useState<ChapterDef[] | undefined>(undefined);
  useEffect(() => {
    // 章节定义：优先从后端 API 获取，失败静默，由工作台内置定义兜底
    getRiskAssessmentChapters(enterpriseId).then(setChapters).catch(() => {});
  }, [enterpriseId]);
  return (
    <ReportWorkspace
      adapter={riskAssessmentAdapter}
      enterpriseId={enterpriseId}
      kind="risk"
      chapters={chapters}
      meta={{
        emptyTitle: "尚未生成风险评估报告",
        emptyDesc: "根据法规要求，编制应急预案前需先完成风险评估。系统将基于风险分级管控数据自动生成。",
        generateLabel: "AI 生成风险评估报告",
      }}
    />
  );
}
