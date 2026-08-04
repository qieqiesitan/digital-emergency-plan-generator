// @ts-nocheck
import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Clock, Bot, User, RotateCcw } from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Badge from "@/mobile/components/ui/Badge";
import Spinner from "@/mobile/components/ui/Spinner";
import EmptyState from "@/mobile/components/ui/EmptyState";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { listVersions, rollbackVersion } from "@/services/planService";
import { formatRelativeTime } from "@/utils/formatters";

export default function VersionListScreen() {
  const { id: planId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ["versions", planId],
    queryFn: () => listVersions(planId!),
    enabled: !!planId,
  });

  const rollbackMutation = useMutation({
    mutationFn: (versionId: string) => rollbackVersion(planId!, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["versions", planId] });
      showToast?.("已回滚到选定版本", "success");
    },
    onError: () => showToast?.("回滚失败", "danger"),
  });

  const handleRollback = (versionId: string, versionNumber: number) => {
    if (window.confirm(`确定回滚到 v${versionNumber}？当前版本将保存为新版本。`)) {
      rollbackMutation.mutate(versionId);
    }
  };

  if (isLoading) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh flex items-center justify-center">
        <Spinner size="lg" />
      </SafeArea>
    );
  }

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="版本管理" showBack onBack={() => navigate(-1)} />
      <div className="px-md py-md">
        {versions.length === 0 ? (
          <EmptyState
            icon={<Clock size={40} className="text-neutral-300" />}
            title="暂无版本记录"
          />
        ) : (
          <div className="space-y-2">
            <div className="mb-md">
              <Badge variant="info">当前版本：v{versions[0]?.version_number ?? "-"}</Badge>
            </div>

            {versions.map((v) => (
              <motion.div key={v.id} whileTap={{ scale: 0.99 }}>
                <Card
                  pressable
                  className={`p-md ${v.is_current ? "bg-primary-50" : ""}`}
                  onClick={() => {
                    navigate(`/m/plans/${planId}/edit`);
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-sm">
                      <span className="text-h3 font-semibold">v{v.version_number}</span>
                      {v.is_current && <Badge variant="info">当前</Badge>}
                    </div>
                    {!v.is_current && (
                      <button
                        className="text-caption text-primary-600 font-medium flex items-center gap-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRollback(v.id, v.version_number);
                        }}
                      >
                        <RotateCcw size={14} /> 回滚
                      </button>
                    )}
                  </div>
                  <div className="flex items-center gap-xs mt-2">
                    <span className="text-caption text-neutral-400">
                      {new Date(v.created_at).toLocaleString("zh-CN")}
                    </span>
                    <span className="text-neutral-300">·</span>
                    <span className="flex items-center gap-1 text-caption text-neutral-400">
                      {v.created_by === "auto" ? (
                        <><Bot size={12} /> 自动创建</>
                      ) : (
                        <><User size={12} /> 手动创建</>
                      )}
                    </span>
                  </div>
                  {v.description && (
                    <p className="text-body-sm text-neutral-600 mt-2 line-clamp-2">{v.description}</p>
                  )}
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </SafeArea>
  );
}

