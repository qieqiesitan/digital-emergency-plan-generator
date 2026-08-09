// @ts-nocheck
import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown, ChevronRight, FileText,
  Target, Factory, Check,
} from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Badge from "@/mobile/components/ui/Badge";
import Button from "@/mobile/components/ui/Button";
import Chip from "@/mobile/components/ui/Chip";
import ProgressBar from "@/mobile/components/ui/ProgressBar";
import Skeleton from "@/mobile/components/ui/Skeleton";
import EmptyState from "@/mobile/components/ui/EmptyState";
import BottomSheet from "@/mobile/components/ui/BottomSheet";
import FAB from "@/mobile/components/ui/FAB";
import { useToast } from "@/mobile/components/ui/Toast";
import { useAppStore } from "@/mobile/store/appStore";
import { getDashboard } from "@/services/dashboardService";
import { listEnterprises } from "@/services/enterpriseService";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import { getEnterprisePlanSummary } from "@/services/planService";
import { fromNow } from "@/utils/formatters";

const PLAN_TYPE_LABELS: Record<string, string> = {
  comprehensive: "综合",
  special: "专项",
  onsite: "现场",
};

const PLAN_TYPE_COLORS: Record<string, "info" | "warning" | "success"> = {
  comprehensive: "info",
  special: "warning",
  onsite: "success",
};

const QUICK_ACTIONS = [
  {
    type: "comprehensive",
    icon: <FileText size={20} />,
    title: "新建综合应急预案",
    desc: "从企业信息自动生成完整框架",
  },
  {
    type: "special",
    icon: <Target size={20} />,
    title: "新建专项应急预案",
    desc: "针对特定事故类型（火灾、触电等）",
  },
  {
    type: "onsite",
    icon: <Factory size={20} />,
    title: "新建现场处置方案",
    desc: "一线操作卡片式应急处置步骤",
  },
];

export default function DashboardScreen() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const {
    currentEnterpriseId, currentEnterpriseName,
    setCurrentEnterprise,
  } = useAppStore();
  const [enterpriseSheetOpen, setEnterpriseSheetOpen] = useState(false);

  // 获取企业列表
  const enterprisesQuery = useQuery({
    queryKey: ["enterprises"],
    queryFn: async () => {
      const res = await listEnterprises({ page: 1, page_size: 100 });
      return res.data.items;
    },
    staleTime: 60000,
  });

  const enterprises = enterprisesQuery.data ?? [];

  // 自动选择当前企业
  const activeEnterpriseId = useMemo(() => {
    if (currentEnterpriseId) return currentEnterpriseId;
    if (enterprises.length > 0) {
      setCurrentEnterprise(enterprises[0].id, enterprises[0].name);
      return enterprises[0].id;
    }
    return null;
  }, [currentEnterpriseId, enterprises, setCurrentEnterprise]);

  const activeEnterpriseName = useMemo(() => {
    if (currentEnterpriseName) return currentEnterpriseName;
    if (enterprises.length > 0) return enterprises[0].name;
    return null;
  }, [currentEnterpriseName, enterprises]);

  // 获取 Dashboard 数据
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", activeEnterpriseId],
    queryFn: getDashboard,
    enabled: !!activeEnterpriseId,
    staleTime: 60000,
    refetchOnMount: true,
  });

  // 获取预案汇总
  const summaryQuery = useQuery({
    queryKey: ["enterprise-plan-summary", activeEnterpriseId],
    queryFn: getEnterprisePlanSummary,
    enabled: !!activeEnterpriseId,
    staleTime: 60000,
  });

  // 获取企业数据完成度
  const completionQuery = useQuery({
    queryKey: ["completion", activeEnterpriseId],
    queryFn: () => getEnterpriseCompletion(activeEnterpriseId!),
    enabled: !!activeEnterpriseId,
    staleTime: 60000,
  });

  const stats = dashboardQuery.data?.stats;
  const recentPlans = dashboardQuery.data?.recent_plans ?? [];
  const isLoading = dashboardQuery.isLoading || summaryQuery.isLoading;
  const undoneModules = (completionQuery.data?.modules ?? []).filter(m => !m.done);

  // 计算当前企业的预案统计
  const planStats = useMemo(() => {
    const s = summaryQuery.data?.find(e => e.enterprise_id === activeEnterpriseId);
    return {
      total: s?.total ?? 0,
      comprehensive: s?.comprehensive_count ?? 0,
      special: s?.special_count ?? 0,
      onsite: s?.onsite_count ?? 0,
    };
  }, [summaryQuery.data, activeEnterpriseId]);

  const handleSelectEnterprise = (id: string, name: string) => {
    setCurrentEnterprise(id, name);
    setEnterpriseSheetOpen(false);
    showToast?.(`已切换到 ${name}`, "info");
  };

  const handleQuickAction = (type: string) => {
    if (!activeEnterpriseId) {
      showToast?.("请先添加企业", "warning");
      return;
    }
    navigate(`/m/plans/new?enterprise_id=${activeEnterpriseId}&type=${type}`);
  };

  const handleCompletionAction = () => {
    if (!activeEnterpriseId) return;
    if (undoneModules.length === 0) {
      navigate(`/m/plans/new?enterprise_id=${activeEnterpriseId}`);
    } else {
      navigate(`/m/enterprises/${activeEnterpriseId}`);
    }
  };

  const SPEED_DIAL_ACTIONS = QUICK_ACTIONS.map(a => ({
    icon: a.icon,
    label: a.title.replace("新建", "").trim(),
    onPress: () => handleQuickAction(a.type),
  }));

  // 如果正在加载，显示骨架屏
  if (isLoading && !dashboardQuery.data) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="工作台" largeTitle />
        <div className="px-md space-y-md">
          <Skeleton variant="text" className="h-4 w-48" />
          <div className="flex gap-md overflow-hidden">
            {[1, 2, 3].map(i => (
              <Skeleton key={i} variant="card" className="min-w-[116px] h-24" />
            ))}
          </div>
          {[1, 2, 3].map(i => (
            <Skeleton key={`act-${i}`} variant="list-item" className="h-14" />
          ))}
          <Skeleton variant="text" className="h-4 w-24 mt-lg" />
          {[1, 2, 3].map(i => (
            <Skeleton key={`rec-${i}`} variant="list-item" className="h-20" />
          ))}
        </div>
      </SafeArea>
    );
  }

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh pb-[calc(var(--tabbar-height)+80px)]">
      <NavBar title="工作台" largeTitle />

      {/* 企业数据完成度卡片 */}
      {/* 加载中：查询 key 含企业 id，切换企业时旧企业数据不会复用，直接显示骨架屏 */}
      {!completionQuery.isError && completionQuery.isLoading && (
        <Card className="mx-md mt-md mb-md bg-primary-50 border border-primary-600">
          <div className="flex items-center justify-between">
            <Skeleton variant="text" className="h-4 w-36" />
            <Skeleton variant="text" className="h-4 w-12" />
          </div>
          <Skeleton variant="text" className="h-1.5 mt-sm" />
          <div className="flex gap-xs mt-sm">
            <Skeleton variant="text" className="h-6 w-16 rounded-full" />
            <Skeleton variant="text" className="h-6 w-16 rounded-full" />
          </div>
        </Card>
      )}

      {completionQuery.isError && !completionQuery.data && (
        <Card className="mx-md mt-md mb-md bg-primary-50 border border-primary-600">
          <div className="flex items-center justify-between">
            <p className="text-body font-semibold text-neutral-900">企业数据完成度</p>
            <Button
              variant="ghost"
              size="sm"
              loading={completionQuery.isFetching}
              onClick={() => completionQuery.refetch()}
            >
              重试
            </Button>
          </div>
          <p className="text-caption text-danger mt-xs">完成度加载失败，请检查网络后重试</p>
        </Card>
      )}

      {completionQuery.data && (
        <Card className="mx-md mt-md mb-md bg-primary-50 border border-primary-600">
          <div className="flex items-center justify-between mb-xs">
            <p className="text-body font-semibold text-neutral-900">企业数据完成度</p>
            <span className="text-h3 font-bold text-primary-600">
              {completionQuery.data.percent}%
            </span>
          </div>
          <ProgressBar percent={completionQuery.data.percent} />
          {undoneModules.length > 0 && (
            <div className="flex flex-wrap gap-xs mt-sm">
              {undoneModules.map((m) => (
                <Chip key={m.key} variant="warning">
                  {m.label}
                </Chip>
              ))}
            </div>
          )}
          <div className="mt-sm">
            <Button size="sm" onClick={handleCompletionAction}>
              {undoneModules.length === 0 ? "去生成预案" : "去补数据"}
            </Button>
          </div>
        </Card>
      )}

      <div className="px-md space-y-md">

        {/* 企业切换器 */}
        <button
          className="flex items-center gap-xs text-left"
          onClick={() => setEnterpriseSheetOpen(true)}
        >
          <span className="text-h3 font-semibold text-neutral-900">
            {activeEnterpriseName ?? "暂未添加企业"}
          </span>
          <ChevronDown size={14} className="text-neutral-400" />
          {!activeEnterpriseId && (
            <span className="text-caption text-primary-600 ml-sm">去添加 →</span>
          )}
        </button>

        {/* 日期 */}
        <p className="text-caption text-neutral-400 -mt-xs">
          {new Date().toLocaleDateString("zh-CN", {
            year: "numeric", month: "long", day: "numeric", weekday: "long",
          })}
        </p>

        {/* 统计卡片组 */}
        <div className="flex gap-md overflow-x-auto snap-x snap-mandatory hide-scrollbar">
          <div className="min-w-[116px] h-24 bg-white rounded-md shadow-card flex flex-col justify-center p-md snap-start">
            <p className="text-display text-primary-600 font-bold">
              {planStats.total}
            </p>
            <p className="text-caption text-neutral-400 mt-xs">预案总数</p>
          </div>
          <div className="min-w-[116px] h-24 bg-white rounded-md shadow-card flex flex-col justify-center p-md snap-start">
            <p className="text-display text-green-600 font-bold">
              {stats?.completed_plan_count ?? 0}
            </p>
            <p className="text-caption text-neutral-400 mt-xs">已完成</p>
          </div>
          <div className="min-w-[116px] h-24 bg-white rounded-md shadow-card flex flex-col justify-center p-md snap-start">
            <p className="text-display text-neutral-900 font-bold">
              {stats?.enterprise_count ?? enterprises.length}
            </p>
            <p className="text-caption text-neutral-400 mt-xs">管理企业</p>
          </div>
        </div>

        {/* 快捷操作 */}
        <div>
          <p className="text-h2 mb-sm">快捷操作</p>
          <div className="space-y-3">
            {QUICK_ACTIONS.map((action) => (
              <motion.div
                key={action.type}
                whileTap={{ scale: 0.99 }}
              >
                <Card
                  pressable
                  className="flex items-center px-md h-14 gap-md"
                  onClick={() => handleQuickAction(action.type)}
                >
                  <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 shrink-0">
                    {action.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-body font-semibold text-neutral-900">
                      {action.title}
                    </p>
                    <p className="text-caption text-neutral-400 truncate">
                      {action.desc}
                    </p>
                  </div>
                  <ChevronRight size={16} className="text-neutral-400 shrink-0" />
                </Card>
              </motion.div>
            ))}
          </div>
        </div>

        {/* 最近编辑 */}
        <div>
          <div className="flex items-center justify-between mb-sm">
            <p className="text-h2">最近编辑</p>
            <button
              className="text-caption text-primary-600"
              onClick={() => navigate("/m/plans")}
            >
              查看全部 →
            </button>
          </div>

          {recentPlans.length === 0 ? (
            <EmptyState
              icon={<FileText size={40} className="text-neutral-300" />}
              title="暂无编辑记录"
              description="创建第一个预案开始使用"
              action="新建预案"
              onAction={() => handleQuickAction("comprehensive")}
            />
          ) : (
            <div className="space-y-3">
              {recentPlans.slice(0, 5).map((plan) => (
                <motion.div key={plan.id} whileTap={{ scale: 0.99 }}>
                  <Card
                    pressable
                    className="flex items-start gap-md p-md"
                    onClick={() => navigate(`/m/plans/${plan.id}/edit`)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-h3 font-semibold text-neutral-900 truncate">
                        {plan.title}
                      </p>
                      <p className="text-caption text-neutral-400 mt-1">
                        {plan.enterprise_name} · {fromNow(plan.updated_at)}
                      </p>
                      <div className="flex gap-xs mt-2">
                        <Badge variant={PLAN_TYPE_COLORS[plan.plan_type] ?? "default"}>
                          {PLAN_TYPE_LABELS[plan.plan_type] ?? plan.plan_type}
                        </Badge>
                        <Badge
                          variant={plan.status === "completed" ? "success" : plan.status === "generating" ? "info" : "default"}
                        >
                          {plan.status === "completed" ? "已完成" : plan.status === "generating" ? "生成中" : "草稿"}
                        </Badge>
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-neutral-400 mt-1 shrink-0" />
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </div>

      </div>

      {/* 企业切换 BottomSheet */}
      <BottomSheet
        open={enterpriseSheetOpen}
        onClose={() => setEnterpriseSheetOpen(false)}
        height="60%"
      >
        <div className="p-md">
          <p className="text-h2 mb-md">选择工作企业</p>
          <div className="space-y-1">
            {enterprises.map((ent) => (
              <button
                key={ent.id}
                className="flex items-center gap-md w-full px-sm py-3 rounded-md active:bg-neutral-50"
                onClick={() => handleSelectEnterprise(ent.id, ent.name)}
              >
                <div className="w-11 h-11 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 font-semibold text-body shrink-0">
                  {ent.name.charAt(0)}
                </div>
                <span className="flex-1 text-left text-body text-neutral-900">
                  {ent.name}
                </span>
                {activeEnterpriseId === ent.id && (
                  <Check size={20} className="text-primary-600 shrink-0" />
                )}
              </button>
            ))}
          </div>
          <button
            className="mt-md w-full py-3 text-center text-body text-primary-600 border-t border-neutral-100 pt-md"
            onClick={() => {
              setEnterpriseSheetOpen(false);
              navigate("/m/enterprises");
            }}
          >
            管理企业 →
          </button>
        </div>
      </BottomSheet>

      {/* FAB */}
      <FAB speedDialActions={SPEED_DIAL_ACTIONS} />
    </SafeArea>
  );
}

