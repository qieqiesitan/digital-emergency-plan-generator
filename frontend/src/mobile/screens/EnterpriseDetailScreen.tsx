// @ts-nocheck
import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Edit, AlertTriangle, Package, FileText,
  ChevronRight, Plus, Flame, Shield,
} from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Badge from "@/mobile/components/ui/Badge";
import Card from "@/mobile/components/ui/Card";
import SegmentedControl from "@/mobile/components/ui/SegmentedControl";
import Skeleton from "@/mobile/components/ui/Skeleton";
import { getEnterprise } from "@/services/enterpriseService";
import { getFullHierarchy } from "@/services/riskManagementService";
import { listResources } from "@/services/emergencyResourceService";

type TabKey = "info" | "risk" | "resource" | "report";

const TABS: { key: TabKey; label: string }[] = [
  { key: "info", label: "基本信息" },
  { key: "risk", label: "风险管控" },
  { key: "resource", label: "应急资源" },
  { key: "report", label: "调查报告" },
];

// 基本信息 Tab
function InfoTab({ enterprise }: { enterprise: Record<string, unknown> }) {
  const fields = [
    { label: "企业名称", value: enterprise.name },
    { label: "行业分类", value: enterprise.industry },
    { label: "经营范围", value: enterprise.business_scope },
    { label: "经济类型", value: enterprise.economic_type || "-" },
    { label: "员工人数", value: enterprise.employee_count ? `${enterprise.employee_count} 人` : "-" },
    { label: "地址", value: enterprise.address },
  ];

  return (
    <div className="space-y-1">
      {fields.map((f) => (
        <div key={f.label} className="flex justify-between items-center px-md py-3 bg-white border-b border-neutral-50 last:border-0">
          <span className="text-caption text-neutral-400">{f.label}</span>
          <span className="text-body text-neutral-900 max-w-[60%] text-right truncate">
            {String(f.value ?? "-")}
          </span>
        </div>
      ))}
      <div className="px-md py-3 bg-white border-t border-neutral-50 mt-sm">
        <p className="text-h3 font-semibold text-neutral-900 mb-2">统计</p>
        <div className="flex gap-md">
          <div className="flex-1 bg-neutral-50 rounded-md p-3 text-center">
            <p className="text-display text-primary-600 font-bold">{String(enterprise.risk_events_count ?? 0)}</p>
            <p className="text-caption text-neutral-400">风险事件</p>
          </div>
          <div className="flex-1 bg-neutral-50 rounded-md p-3 text-center">
            <p className="text-display text-primary-600 font-bold">{String(enterprise.resources_count ?? 0)}</p>
            <p className="text-caption text-neutral-400">应急资源</p>
          </div>
          <div className="flex-1 bg-neutral-50 rounded-md p-3 text-center">
            <p className="text-display text-primary-600 font-bold">{String(enterprise.plans_count ?? 0)}</p>
            <p className="text-caption text-neutral-400">预案</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// 风险管控 Tab（内嵌摘要）
function RiskTab({ enterpriseId }: { enterpriseId: string }) {
  const navigate = useNavigate();
  const { data: zones = [], isLoading } = useQuery({
    queryKey: ["risk-hierarchy", enterpriseId],
    queryFn: () => getFullHierarchy(enterpriseId),
    enabled: !!enterpriseId,
  });

  const rows = zones.flatMap((zone) =>
    (zone.objects || []).flatMap((obj) => {
      const objectEvents = (obj.events || []).map((ev) => ({ ...ev, object: obj.name, unit: null }));
      const unitEvents = (obj.units || []).flatMap((unit) =>
        (unit.events || []).map((ev) => ({ ...ev, object: obj.name, unit: unit.name }))
      );
      return [...objectEvents, ...unitEvents];
    })
  );

  if (isLoading) {
    return (
      <div className="px-md py-lg space-y-sm">
        {[1, 2, 3].map(i => <Skeleton key={i} variant="list-item" className="h-14" />)}
      </div>
    );
  }

  return (
    <div>
      {rows.length === 0 ? (
        <div className="px-md py-12 text-center">
          <AlertTriangle size={40} className="mx-auto text-neutral-300 mb-4" />
          <p className="text-h3 text-neutral-900 mb-2">暂无风险事件</p>
          <p className="text-body text-neutral-500 mb-4">请先在 Web 端维护风险分级管控数据</p>
          <button
            className="inline-flex items-center gap-xs px-4 py-2 bg-primary-600 text-white rounded-md font-medium"
            onClick={() => navigate(`/m/enterprises/${enterpriseId}/risk-management`)}
          >
            <Plus size={16} /> 查看风险管控
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between px-md py-3">
            <span className="text-caption text-neutral-400">{rows.length} 个风险事件</span>
            <button
              className="text-caption text-primary-600 flex items-center gap-xs"
              onClick={() => navigate(`/m/enterprises/${enterpriseId}/risk-management`)}
            >
              查看全部 <ChevronRight size={14} />
            </button>
          </div>
          {rows.slice(0, 5).map((row, index) => (
            <div key={`${row.id}-${index}`} className="flex items-center gap-md px-md py-3 bg-white border-b border-neutral-50">
              <div className="w-9 h-9 rounded-full bg-amber-50 flex items-center justify-center shrink-0">
                <Flame size={16} className="text-amber-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-body text-neutral-900 truncate">{row.accident_type}</p>
                <p className="text-caption text-neutral-400">
                  {zoneName(zones, row)}{row.unit ? ` · ${row.unit}` : ""}
                </p>
              </div>
              {row.risk_level && (
                <Badge variant="warning">{row.risk_level}</Badge>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function zoneName(zones, row) {
  for (const zone of zones) {
    for (const obj of zone.objects || []) {
      if (obj.name === row.object) return zone.name;
    }
  }
  return "未分区";
}

// 应急资源 Tab（内嵌列表）
function ResourceTab({ enterpriseId }: { enterpriseId: string }) {
  const navigate = useNavigate();
  const { data: resources = [], isLoading } = useQuery({
    queryKey: ["emergency-resources", enterpriseId],
    queryFn: () => listResources(enterpriseId, { page: 1, page_size: 50 }),
    enabled: !!enterpriseId,
  });

  if (isLoading) {
    return (
      <div className="px-md py-lg space-y-sm">
        {[1, 2, 3].map(i => <Skeleton key={i} variant="list-item" className="h-14" />)}
      </div>
    );
  }

  const items = Array.isArray(resources) ? resources : (resources as any)?.items ?? [];

  return (
    <div>
      {items.length === 0 ? (
        <div className="px-md py-12 text-center">
          <Package size={40} className="mx-auto text-neutral-300 mb-4" />
          <p className="text-h3 text-neutral-900 mb-2">暂无应急资源</p>
          <p className="text-body text-neutral-500 mb-4">添加企业的应急资源信息</p>
          <button
            className="inline-flex items-center gap-xs px-4 py-2 bg-primary-600 text-white rounded-md font-medium"
            onClick={() => navigate(`/m/enterprises/${enterpriseId}/resources`)}
          >
            <Plus size={16} /> 管理应急资源
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between px-md py-3">
            <span className="text-caption text-neutral-400">{items.length} 个应急资源</span>
            <button
              className="text-caption text-primary-600 flex items-center gap-xs"
              onClick={() => navigate(`/m/enterprises/${enterpriseId}/resources`)}
            >
              查看全部 <ChevronRight size={14} />
            </button>
          </div>
          {items.slice(0, 5).map((res: any) => (
            <div key={res.id} className="flex items-center gap-md px-md py-3 bg-white border-b border-neutral-50">
              <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center shrink-0">
                <Shield size={16} className="text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-body text-neutral-900 truncate">{res.name ?? "未命名"}</p>
                <p className="text-caption text-neutral-400">
                  {[res.type, res.quantity ? `${res.quantity}${res.unit ?? ""}` : ""].filter(Boolean).join(" · ")}
                </p>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// 调查报告 Tab
function ReportTab({ enterpriseId }: { enterpriseId: string }) {
  const navigate = useNavigate();

  return (
    <div className="px-md py-lg space-y-3">
      <Card pressable onClick={() => navigate(`/m/enterprises/${enterpriseId}/risk-assessment`)}>
        <div className="flex items-center gap-md">
          <div className="w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center text-amber-600">
            <AlertTriangle size={20} />
          </div>
          <div className="flex-1">
            <p className="text-body font-semibold text-neutral-900">风险评估报告</p>
            <p className="text-caption text-neutral-400">AI 辅助生成风险评估</p>
          </div>
          <ChevronRight size={16} className="text-neutral-400" />
        </div>
      </Card>
      <Card pressable onClick={() => navigate(`/m/enterprises/${enterpriseId}/resource-investigation`)}>
        <div className="flex items-center gap-md">
          <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
            <FileText size={20} />
          </div>
          <div className="flex-1">
            <p className="text-body font-semibold text-neutral-900">应急资源调查报告</p>
            <p className="text-caption text-neutral-400">AI 辅助生成资源调查报告</p>
          </div>
          <ChevronRight size={16} className="text-neutral-400" />
        </div>
      </Card>
    </div>
  );
}

export default function EnterpriseDetailScreen() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabKey>("info");

  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="企业详情" showBack onBack={() => navigate(-1)} />
        <div className="px-md space-y-md mt-md">
          <Skeleton variant="text" className="h-6 w-48" />
          <Skeleton variant="text" className="h-4 w-24" />
          <Skeleton variant="card" className="h-32" />
        </div>
      </SafeArea>
    );
  }

  if (!enterprise) return null;

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar
        title="企业详情"
        showBack
        onBack={() => navigate(-1)}
        rightActions={[{
          icon: <Edit size={24} />,
          label: "编辑",
          onPress: () => navigate(`/m/enterprises/${id}/edit`),
        }]}
      />
      <div className="px-md pt-md pb-sm">
        <h1 className="text-h1 text-neutral-900">{String(enterprise.name)}</h1>
        {enterprise.industry && (
          <Badge variant="default" className="mt-xs">
            {String(enterprise.industry)}
          </Badge>
        )}
      </div>
      <div className="sticky top-0 z-10 bg-neutral-50 px-md py-sm border-b border-neutral-100">
        <SegmentedControl
          segments={TABS.map(t => ({ key: t.key, label: t.label }))}
          activeKey={activeTab}
          onChange={(k) => setActiveTab(k as TabKey)}
        />
      </div>
      <div className="pb-md">
        {activeTab === "info" && <InfoTab enterprise={enterprise as Record<string, unknown>} />}
        {activeTab === "risk" && <RiskTab enterpriseId={id!} />}
        {activeTab === "resource" && <ResourceTab enterpriseId={id!} />}
        {activeTab === "report" && <ReportTab enterpriseId={id!} />}
      </div>
    </SafeArea>
  );
}
