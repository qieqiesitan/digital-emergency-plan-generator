// @ts-nocheck
import { useState } from "react";
import { Descriptions, Tag, Timeline, Table, Button, Modal, Space } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchRegulation, fetchRegulationHistory, getSourceDownloadUrl, updateTopics } from "@/services/regulationService";
import type { RegulationNode } from "@/types/regulation";

interface Props {
  id: string;
  onClose: () => void;
}

export function RegulationDetail({ id, onClose }: Props) {
  const { data: reg, isLoading } = useQuery({
    queryKey: ["regulation", id],
    queryFn: () => fetchRegulation(id),
  });

  const { data: history } = useQuery({
    queryKey: ["regulationHistory", id],
    queryFn: () => fetchRegulationHistory(id),
  });

  const statusColors: Record<string, string> = { effective: "green", abolished: "red" };
  const typeLabels: Record<string, string> = { law: "法律", standard: "标准", policy: "政策" };
  const actionLabels: Record<string, string> = { created: "新增入库", updated: "编辑更新", abolished: "标记废止", deleted: "删除", reindexed: "重建索引" };

  const articleCols = [
    { title: "条号", dataIndex: "number", key: "number", width: 120 },
    { title: "内容", dataIndex: "text", key: "text", ellipsis: true },
  ];

  return (
    <Modal title="法规详情" open={!!id} onCancel={onClose} width={800} footer={<Button onClick={onClose}>关闭</Button>}>
      {reg && (
        <div>
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="编号">{reg.code}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={statusColors[reg.status]}>{reg.status === "effective" ? "有效" : "废止"}</Tag></Descriptions.Item>
            <Descriptions.Item label="全称" span={2}>{reg.full_name}</Descriptions.Item>
            <Descriptions.Item label="类型">{typeLabels[reg.node_type] || reg.node_type}</Descriptions.Item>
            <Descriptions.Item label="版本">{reg.version || "-"}</Descriptions.Item>
            <Descriptions.Item label="发布机关">{reg.issuing_body || "-"}</Descriptions.Item>
            <Descriptions.Item label="施行日期">{reg.effective_date || "-"}</Descriptions.Item>
            <Descriptions.Item label="主题标签" span={2}>
              <Space wrap size={[4, 4]}>
                {reg.topics?.map((t: string) => (
                  <Tag
                    key={t}
                    color="blue"
                    closable
                    onClose={() => {
                      const newTopics = (reg.topics || []).filter(x => x !== t);
                      updateTopics(id, newTopics).then(() => {
                        reg.topics = newTopics;
                      }).catch(() => {});
                    }}
                  >{t}</Tag>
                ))}
                {reg.ai_topics?.filter((t: string) => !reg.topics?.includes(t)).length > 0 && (
                  <span style={{ fontSize: 12, color: '#8c8c8c', marginLeft: 8 }}>| AI建议:</span>
                )}
                {reg.ai_topics?.filter((t: string) => !reg.topics?.includes(t)).map((t: string) => (
                  <Tag
                    key={'ai_'+t}
                    color="geekblue"
                    style={{ cursor: 'pointer' }}
                    onClick={() => {
                      const newTopics = [...(reg.topics || []), t];
                      updateTopics(id, newTopics).then(() => {
                        reg.topics = newTopics;
                      }).catch(() => {});
                    }}
                  >{t} 采纳</Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>

          {reg.articles && reg.articles.length > 0 && (
            <>
              <h4 style={{ marginTop: 16 }}>法规条文（{reg.articles.length} 条）</h4>
              <Table columns={articleCols} dataSource={reg.articles} rowKey="number" size="small"
                pagination={{ pageSize: 10 }} />
            </>
          )}

          {reg.source_files && reg.source_files.length > 0 && (
            <>
              <h4 style={{ marginTop: 16 }}>源文件</h4>
              {reg.source_files.map(f => (
                <div key={f.filename} style={{ marginBottom: 4 }}>
                  <a href={getSourceDownloadUrl(id, f.filename)} target="_blank" rel="noopener noreferrer">
                    {f.filename}
                  </a>
                  <span style={{ color: "#999", marginLeft: 8 }}>{(f.size / 1024).toFixed(1)}KB</span>
                </div>
              ))}
            </>
          )}

          {history && history.items.length > 0 && (
            <>
              <h4 style={{ marginTop: 16 }}>变更历史</h4>
              <Timeline items={history.items.slice(0, 20).map(e => ({
                children: (
                  <div>
                    <div>{actionLabels[e.action] || e.action} — {e.operator}</div>
                    <div style={{ color: "#999", fontSize: 12 }}>{e.timestamp}</div>
                    {e.detail?.filename && <div style={{ fontSize: 12 }}>文件: {String(e.detail.filename)}</div>}
                    {e.detail?.replaced_by && <div style={{ fontSize: 12 }}>替代为: {String(e.detail.replaced_by)}</div>}
                  </div>
                ),
              }))} />
            </>
          )}
        </div>
      )}
    </Modal>
  );
}