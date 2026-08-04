// @ts-nocheck
import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Plus, Sparkles, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Badge from "@/mobile/components/ui/Badge";
import Input from "@/mobile/components/ui/Input";
import BottomSheet from "@/mobile/components/ui/BottomSheet";
import EmptyState from "@/mobile/components/ui/EmptyState";
import FAB from "@/mobile/components/ui/FAB";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { listRiskSources, createRiskSource, deleteRiskSource } from "@/services/riskSourceService";
import type { RiskSource } from "@/types/riskSource";

const LEVEL_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  "重大": { dot: "bg-red-500", bg: "bg-red-50", text: "text-red-700" },
  "较大": { dot: "bg-orange-500", bg: "bg-orange-50", text: "text-orange-700" },
  "一般": { dot: "bg-yellow-500", bg: "bg-yellow-50", text: "text-yellow-700" },
  "低": { dot: "bg-green-500", bg: "bg-green-50", text: "text-green-700" },
};

const LEVEL_ORDER = ["重大", "较大", "一般", "低"];

export default function RiskSourceListScreen() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newLevel, setNewLevel] = useState("一般");
  const [aiOpen, setAiOpen] = useState(false);

  const { data: riskSources = [] } = useQuery({
    queryKey: ["risk-sources", enterpriseId],
    queryFn: async () => {
      const res = await listRiskSources(enterpriseId!, { page_size: 200 });
      return res.data.items;
    },
    enabled: !!enterpriseId,
  });

  const sorted = [...riskSources].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.risk_level) - LEVEL_ORDER.indexOf(b.risk_level)
  );

  const levelCounts = {
    high: sorted.filter(r => r.risk_level === "重大" || r.risk_level === "较大").length,
    medium: sorted.filter(r => r.risk_level === "一般").length,
    low: sorted.filter(r => r.risk_level === "低").length,
  };

  const addMutation = useMutation({
    mutationFn: () =>
      createRiskSource(enterpriseId!, {
        name: newName,
        location: newLocation || undefined,
        description: newDesc || undefined,
        risk_level: newLevel as RiskSource["risk_level"],
        likelihood: "中",
        severity: "中",
        categories: [],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-sources", enterpriseId] });
      showToast?.("风险源已添加", "success");
      setAddOpen(false);
      setNewName("");
      setNewLocation("");
      setNewDesc("");
    },
    onError: () => showToast?.("添加失败", "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: (rid: string) => deleteRiskSource(enterpriseId!, rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-sources", enterpriseId] });
      showToast?.("已删除", "success");
    },
    onError: () => showToast?.("删除失败", "danger"),
  });

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh pb-20">
      <NavBar
        title="风险源管理"
        showBack
        onBack={() => navigate(-1)}
        rightActions={[{
          icon: <Sparkles size={22} />,
          label: "AI生成",
          onPress: () => setAiOpen(true),
        }]}
      />

      {/* 统计条 */}
      <div className="px-md py-sm flex gap-sm">
        <Badge variant="danger">高风险 {levelCounts.high}</Badge>
        <Badge variant="warning">中风险 {levelCounts.medium}</Badge>
        <Badge variant="default">低风险 {levelCounts.low}</Badge>
      </div>

      {/* 列表 */}
      <div className="px-md space-y-2">
        {sorted.map((rs) => (
          <motion.div key={rs.id} whileTap={{ scale: 0.99 }}>
            <Card pressable className="flex items-start gap-md">
              <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${LEVEL_COLORS[rs.risk_level]?.dot ?? "bg-neutral-300"}`} />
              <div className="flex-1 min-w-0">
                <p className="text-h3 font-semibold text-neutral-900">{rs.name}</p>
                <p className="text-body-sm text-neutral-600 mt-0.5">{rs.location || "-"}</p>
                {rs.control_measures && (
                  <p className="text-caption text-neutral-400 mt-1 truncate">{rs.control_measures}</p>
                )}
              </div>
              <button
                className="text-red-400 p-1 shrink-0"
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm("确定删除此风险源？")) {
                    deleteMutation.mutate(rs.id);
                  }
                }}
              >
                删除
              </button>
            </Card>
          </motion.div>
        ))}

        {sorted.length === 0 && (
          <div className="py-lg">
            <EmptyState
              icon={<AlertTriangle size={40} className="text-neutral-300" />}
              title="暂无风险源数据"
              description="点击右下角 + 添加或使用 AI 智能识别"
            />
            <Card pressable className="mt-md p-md" onClick={() => setAiOpen(true)}>
              <div className="flex items-center gap-md">
                <div className="w-10 h-10 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600">
                  <Sparkles size={20} />
                </div>
                <div>
                  <p className="text-body font-semibold text-neutral-900">AI 智能分析生成风险源</p>
                  <p className="text-caption text-neutral-400">上传或填写企业信息，AI 自动识别潜在风险源</p>
                </div>
              </div>
            </Card>
          </div>
        )}
      </div>

      {/* 新增 BottomSheet */}
      <BottomSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        height="60%"
      >
        <div className="p-md space-y-md">
          <p className="text-h2">新增风险源</p>
          <Input label="风险源名称" required value={newName} onChange={setNewName} placeholder="如：火灾" />
          <Input label="位置" value={newLocation} onChange={setNewLocation} placeholder="如：生产车间A区" />
          <Input label="管控措施" value={newDesc} onChange={setNewDesc} placeholder="简要描述管控措施" multiline />
          <div className="flex gap-sm">
            {["重大", "较大", "一般", "低"].map(level => (
              <button
                key={level}
                className={`flex-1 py-2 rounded-md text-body-sm font-medium ${newLevel === level ? "bg-primary-600 text-white" : "bg-neutral-100 text-neutral-600"}`}
                onClick={() => setNewLevel(level)}
              >
                {level}
              </button>
            ))}
          </div>
          <button
            className="w-full h-11 bg-primary-600 text-white rounded-md font-semibold disabled:opacity-50"
            disabled={!newName.trim() || addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            {addMutation.isPending ? "添加中…" : "确认添加"}
          </button>
        </div>
      </BottomSheet>

      {/* AI生成 BottomSheet */}
      <BottomSheet open={aiOpen} onClose={() => setAiOpen(false)} height="60%">
        <div className="p-md space-y-md">
          <div className="flex items-center gap-sm">
            <Sparkles size={24} className="text-indigo-600" />
            <p className="text-h2">AI 智能识别风险源</p>
          </div>
          <p className="text-body text-neutral-500">
            AI 将根据企业基本信息（行业、经营范围等）自动识别潜在风险源，并预填风险等级和管控措施。
          </p>
          <p className="text-caption text-neutral-400">
            API: POST /api/v1/enterprises/{enterpriseId}/risk-sources/generate
          </p>
          <button
            className="w-full h-11 bg-indigo-600 text-white rounded-md font-semibold"
            onClick={() => {
              showToast?.("AI 生成功能需对接后端 API", "info");
              setAiOpen(false);
            }}
          >
            ✨ 开始分析
          </button>
        </div>
      </BottomSheet>

      <FAB icon={<Plus size={24} />} onClick={() => setAddOpen(true)} />
    </SafeArea>
  );
}
