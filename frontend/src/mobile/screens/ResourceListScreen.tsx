import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Sparkles, Package } from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Chip from "@/mobile/components/ui/Chip";
import Input from "@/mobile/components/ui/Input";
import BottomSheet from "@/mobile/components/ui/BottomSheet";
import EmptyState from "@/mobile/components/ui/EmptyState";
import FAB from "@/mobile/components/ui/FAB";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { listResources, createResource, deleteResource } from "@/services/emergencyResourceService";

const RESOURCE_CATEGORIES = ["全部", "消防", "急救", "防护", "通讯", "照明", "破拆", "其他"];

export default function ResourceListScreen() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [activeCategory, setActiveCategory] = useState("全部");
  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState("消防");
  const [newQty, setNewQty] = useState("1");
  const [newUnit, setNewUnit] = useState("个");
  const [newLocation, setNewLocation] = useState("");
  const [newPerson, setNewPerson] = useState("");

  const { data: resources = [] } = useQuery({
    queryKey: ["resources", enterpriseId],
    queryFn: async () => {
      const res = await listResources(enterpriseId!, { page_size: 200 });
      return res.data.items;
    },
    enabled: !!enterpriseId,
  });

  const filtered = activeCategory === "全部"
    ? resources
    : resources.filter(r => r.category === activeCategory);

  const addMutation = useMutation({
    mutationFn: () =>
      createResource(enterpriseId!, {
        name: newName,
        category: newCategory,
        quantity: parseInt(newQty, 10) || 0,
        unit: newUnit,
        location: newLocation || undefined,
        responsible_person: newPerson || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] });
      showToast?.("资源已添加", "success");
      setAddOpen(false);
      setNewName("");
      setNewQty("1");
      setNewLocation("");
      setNewPerson("");
    },
    onError: () => showToast?.("添加失败", "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: (rid: string) => deleteResource(enterpriseId!, rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] });
      showToast?.("已删除", "success");
    },
    onError: () => showToast?.("删除失败", "danger"),
  });

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh pb-20">
      <NavBar
        title="应急资源管理"
        showBack
        onBack={() => navigate(-1)}
        rightActions={[{
          icon: <Sparkles size={22} />,
          label: "AI生成",
          onPress: () => showToast?.("AI 生成功能需对接后端 API", "info"),
        }]}
      />

      {/* 分类筛选 */}
      <div className="px-md py-sm flex gap-2 overflow-x-auto hide-scrollbar">
        {RESOURCE_CATEGORIES.map(cat => (
          <Chip
            key={cat}
            selected={activeCategory === cat}
            onClick={() => setActiveCategory(cat)}
          >
            {cat}
          </Chip>
        ))}
      </div>

      {/* 列表 */}
      <div className="px-md space-y-2">
        {filtered.map((res) => (
          <motion.div key={res.id} whileTap={{ scale: 0.99 }}>
            <Card pressable className="flex items-start gap-md">
              <div className="w-2 h-2 rounded-full mt-1.5 shrink-0 bg-blue-500" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-sm">
                  <p className="text-h3 font-semibold text-neutral-900">{res.name}</p>
                  <span className="text-caption text-neutral-400">
                    {res.quantity}{res.unit}
                  </span>
                </div>
                <p className="text-body-sm text-neutral-600 mt-0.5">
                  {[res.location, res.responsible_person ? `责任人: ${res.responsible_person}` : ""]
                    .filter(Boolean).join(" · ")}
                </p>
              </div>
              <button
                className="text-red-400 text-caption shrink-0"
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm("确定删除此资源？")) {
                    deleteMutation.mutate(res.id);
                  }
                }}
              >
                删除
              </button>
            </Card>
          </motion.div>
        ))}

        {filtered.length === 0 && (
          <EmptyState
            icon={<Package size={40} className="text-neutral-300" />}
            title="暂无应急资源"
            description="点击右下角 + 添加应急资源"
            action="添加资源"
            onAction={() => setAddOpen(true)}
          />
        )}
      </div>

      {/* 新增 BottomSheet */}
      <BottomSheet open={addOpen} onClose={() => setAddOpen(false)} height="70%">
        <div className="p-md space-y-md">
          <p className="text-h2">新增应急资源</p>
          <Input label="资源名称" required value={newName} onChange={setNewName} placeholder="如：干粉灭火器" />
          <div className="flex gap-sm">
            <div className="flex-1">
              <label className="text-caption text-neutral-400 mb-1 block">分类</label>
              <select
                className="w-full h-11 px-3 rounded-md border border-neutral-200 bg-white text-body"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
              >
                {RESOURCE_CATEGORIES.filter(c => c !== "全部").map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-sm">
            <Input label="数量" type="number" value={newQty} onChange={setNewQty} className="flex-1" />
            <Input label="单位" value={newUnit} onChange={setNewUnit} className="flex-1" />
          </div>
          <Input label="存放位置" value={newLocation} onChange={setNewLocation} placeholder="如：一楼消防柜" />
          <Input label="责任人" value={newPerson} onChange={setNewPerson} placeholder="如：张三" />
          <button
            className="w-full h-11 bg-primary-600 text-white rounded-md font-semibold disabled:opacity-50"
            disabled={!newName.trim() || addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            {addMutation.isPending ? "添加中…" : "确认添加"}
          </button>
        </div>
      </BottomSheet>

      <FAB icon={<Plus size={24} />} onClick={() => setAddOpen(true)} />
    </SafeArea>
  );
}
