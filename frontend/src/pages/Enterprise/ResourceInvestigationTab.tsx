import { useEffect, useState } from "react";
import ReportWorkspace from "@/components/report/ReportWorkspace";
import { resourceInvestigationAdapter } from "@/services/reportAdapters";
import { getResourceInvestigationChapters } from "@/services/resourceInvestigationService";
import type { ChapterDef } from "@/services/riskAssessmentService";

interface Props {
  enterpriseId: string;
}

export default function ResourceInvestigationTab({ enterpriseId }: Props) {
  const [chapters, setChapters] = useState<ChapterDef[] | undefined>(undefined);
  useEffect(() => {
    // 章节定义：优先从后端 API 获取，失败静默，由工作台内置定义兜底
    getResourceInvestigationChapters(enterpriseId).then(setChapters).catch(() => {});
  }, [enterpriseId]);
  return (
    <ReportWorkspace
      adapter={resourceInvestigationAdapter}
      enterpriseId={enterpriseId}
      kind="resource"
      chapters={chapters}
      meta={{
        emptyTitle: "尚未生成应急资源调查报告",
        emptyDesc: "根据法规要求，编制应急预案前需先完成应急资源调查。系统将基于已录入的应急资源数据自动生成。",
        generateLabel: "AI 生成应急资源调查报告",
      }}
    />
  );
}
