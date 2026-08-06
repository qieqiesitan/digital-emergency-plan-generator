// @ts-nocheck
import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { getFullHierarchy } from "@/services/riskManagementService";
import { flattenHierarchyEvents } from "@/utils/riskHierarchyEvents";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Badge from "@/mobile/components/ui/Badge";
import EmptyState from "@/mobile/components/ui/EmptyState";

const LEVEL_ORDER = ["重大", "较大", "一般", "低"];

export default function RiskManagementListScreen() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: zones = [] } = useQuery({
    queryKey: ["risk-hierarchy", enterpriseId],
    queryFn: () => getFullHierarchy(enterpriseId!),
    enabled: !!enterpriseId,
  });

  const rows = flattenHierarchyEvents(zones).sort(
    (a, b) => LEVEL_ORDER.indexOf(a.risk_level) - LEVEL_ORDER.indexOf(b.risk_level)
  );

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh pb-20">
      <NavBar title="风险分级管控" showBack onBack={() => navigate(-1)} />
      <div className="px-md pt-sm space-y-2">
        {rows.length === 0 ? (
          <EmptyState title="暂无风险事件" description="请先在 Web 端维护风险分级管控数据" />
        ) : rows.map((row, index) => (
          <Card key={`${row.id}-${index}`} className="p-md">
            <div className="flex items-center gap-sm">
              <div className="flex-1 min-w-0">
                <p className="text-h3 font-semibold text-neutral-900">{row.accident_type}</p>
                <p className="text-caption text-neutral-500 mt-0.5">
                  {row.zone} · {row.object}{row.unit ? ` · ${row.unit}` : ""}
                </p>
              </div>
              {row.risk_level && <Badge variant="warning">{row.risk_level}</Badge>}
            </div>
          </Card>
        ))}
      </div>
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2">
        <button className="flex items-center gap-1 text-primary-600 text-caption" onClick={() => navigate(-1)}>
          <ChevronLeft size={14} /> 返回企业详情
        </button>
      </div>
    </SafeArea>
  );
}
