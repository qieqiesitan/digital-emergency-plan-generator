import { useState } from "react";
import { Tabs, Button, message, Space, Spin, Timeline, Modal } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RegulationList } from "@/components/regulation/RegulationList";
import { RegulationForm } from "@/components/regulation/RegulationForm";
import { RegulationDetail } from "@/components/regulation/RegulationDetail";
import { RegulationGraph } from "@/components/regulation/RegulationGraph";
import { AbolishDialog } from "@/components/regulation/AbolishDialog";
import { fetchStats, rebuildIndex, fetchGlobalHistory } from "@/services/regulationService";
import { PageHeader } from "@/components/common/PageHeader";
import type { RegulationNode } from "@/types/regulation";

export default function RegulationManagePage() {
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [viewId, setViewId] = useState<string | null>(null);
  const [abolishTarget, setAbolishTarget] = useState<RegulationNode | null>(null);
  const [activeTab, setActiveTab] = useState("list");

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["regulationStats"],
    queryFn: fetchStats,
    refetchInterval: 30000,
  });

  const { data: historyData } = useQuery({
    queryKey: ["globalHistory"],
    queryFn: () => fetchGlobalHistory(undefined, 50),
  });

  const rebuildMut = useMutation({
    mutationFn: rebuildIndex,
    onSuccess: (d) => {
      message.success(`索引重建完成：${d.total_articles} 条条文，耗时 ${d.duration_seconds}s`);
      queryClient.invalidateQueries({ queryKey: ["regulationStats"] });
    },
    onError: () => message.error("索引重建失败"),
  });

  function handleRebuild() {
    Modal.confirm({
      title: "确认重建向量索引",
      content: "将调用 AI Embedding API 对所有法规条文重新向量化，约需 10-30 秒。确定继续？",
      onOk: () => rebuildMut.mutate(),
    });
  }

  if (statsLoading) return <Spin style={{ display: "block", textAlign: "center", padding: 80 }} />;

  const actionLabels: Record<string, string> = { created: "新增入库", updated: "编辑更新", abolished: "标记废止", deleted: "删除", reindexed: "重建索引" };

  const subtitle = stats
    ?     `共 ${stats.total} 条 | 有效 ${stats.effective} 条 | 已废止 ${stats.abolished} 条 | 已索引 ${stats.indexed_articles} 条条文`
    : "";

  return (
    <div>
      <PageHeader title="法规库管理" subtitle={subtitle}>
        <Space>
          <Button icon={<ReloadOutlined />} loading={rebuildMut.isPending} onClick={handleRebuild}>一键重建索引</Button>
        </Space>
      </PageHeader>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        {
          key: "list",
          label: "法规列表",
          children: <RegulationList onAdd={() => setAddOpen(true)} onView={id => setViewId(id)} onAbolish={r => setAbolishTarget(r)} />,
        },
        {
          key: "graph",
          label: "关系图谱",
          children: <RegulationGraph />,
        },
        {
          key: "history",
          label: "变更记录",
          children: (
            <div style={{ maxWidth: 700 }}>
              {historyData?.items && historyData.items.length > 0 ? (
                <Timeline items={historyData.items.map(e => ({content: (
                    <div>
                      <div><strong>{actionLabels[e.action] || e.action}</strong> — {e.operator}</div>
                      <div style={{ color: "#999", fontSize: 12 }}>{e.timestamp} | {e.regulation_id}</div>
                      {e.detail && (e.detail as Record<string,any>).filename && <div style={{ fontSize: 12 }}>文件: {String((e.detail as Record<string,any>).filename)}</div>}
                      {e.detail && (e.detail as Record<string,any>).replaced_by && <div style={{ fontSize: 12 }}>替代: {String((e.detail as Record<string,any>).replaced_by)}</div>}
                    </div>
                  ),
                }))} />
              ) : (
                <p style={{ color: "#999", textAlign: "center", padding: 40 }}>暂无变更记录</p>
              )}
            </div>
          ),
        },
      ]} />

      <RegulationForm open={addOpen} onClose={() => setAddOpen(false)} />
      {viewId && <RegulationDetail id={viewId} onClose={() => setViewId(null)} />}
      <AbolishDialog record={abolishTarget} open={!!abolishTarget} onClose={() => setAbolishTarget(null)} />
    </div>
  );
}
