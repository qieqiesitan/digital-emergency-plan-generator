import { useState } from "react";
import { Descriptions, Tag, Timeline, Table, Button, Modal, Space, message } from "antd";
import { useQuery } from "@tanstack/react-query";
import {
  fetchRegulation, fetchRegulationHistory, fetchRegulationLineage,
  fetchSourceFile, updateTopics,
} from "@/services/regulationService";

interface Props {
  id: string;
  onClose: () => void;
}

/** 文号特征：国务院令第708号 / 主席令第88号 / 〔2020〕1号 / 公告 …（用于区分"文号"与"误填成法规名"的 code） */
const CODE_LIKE = /令|号|公告|〔|\[|决议|通知/;

export function RegulationDetail({ id, onClose }: Props) {
  const [sourcePreview, setSourcePreview] = useState<{ filename: string; url: string; type: string; text?: string } | null>(null);
  const { data: reg } = useQuery({
    queryKey: ["regulation", id],
    queryFn: () => fetchRegulation(id),
  });

  const { data: history } = useQuery({
    queryKey: ["regulationHistory", id],
    queryFn: () => fetchRegulationHistory(id),
  });

  // 法规体系链（只读图谱）：上位法链 + 直接下级
  const { data: lineage } = useQuery({
    queryKey: ["regulationLineage", id],
    queryFn: () => fetchRegulationLineage(id),
    enabled: !!id,
  });

  const statusColors: Record<string, string> = { effective: "green", abolished: "red" };
  const typeLabels: Record<string, string> = { law: "法律", standard: "标准", policy: "政策" };
  const actionLabels: Record<string, string> = { created: "新增入库", updated: "编辑更新", abolished: "标记废止", deleted: "删除", reindexed: "重建索引" };

  const closeSourcePreview = () => {
    if (sourcePreview) URL.revokeObjectURL(sourcePreview.url);
    setSourcePreview(null);
  };

  const handleViewSource = async (filename: string) => {
    try {
      const blob = await fetchSourceFile(id, filename);
      const url = URL.createObjectURL(blob);
      const text = blob.type.startsWith("text/") ? await blob.text() : undefined;
      setSourcePreview({ filename, url, type: blob.type, text });
    } catch {
      message.error("源文件加载失败，请重试");
    }
  };

  const articleCols = [
    { title: "条号", dataIndex: "number", key: "number", width: 120 },
    { title: "内容", dataIndex: "text", key: "text", ellipsis: true },
  ];

  return (
    <>
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
                {(reg.ai_topics?.filter((t: string) => !reg.topics?.includes(t)).length ?? 0) > 0 && (
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

          {lineage && (lineage.up.length > 0 || lineage.down.length > 0) && (
            <>
              <h4 style={{ marginTop: 16 }}>法规体系链</h4>
              <div style={{ marginBottom: 8 }}>
                <span style={{ color: "#999", marginRight: 8 }}>上位法链：</span>
                {lineage.up.length === 0 ? (
                  <Tag>本法规为顶层</Tag>
                ) : (
                  <Space wrap size={[4, 4]}>
                    {lineage.up.map((item, i) => (
                      <span key={item.id}>
                        {i > 0 && <span style={{ color: "#bbb", margin: "0 4px" }}>←</span>}
                        <Tag color={item.status === "abolished" ? "red" : "blue"}>
                          {/* 数据里部分节点的 code 存的是法规名而不是文号（同名会显示成「XX XX」），
                              因此只有看起来像文号（含 令/号/公告/〔〕）时才前缀展示 */}
                          {CODE_LIKE.test(item.code) ? `${item.code} ` : ""}{item.title}
                        </Tag>
                      </span>
                    ))}
                  </Space>
                )}
              </div>
              <div>
                <span style={{ color: "#999", marginRight: 8 }}>直接下级：</span>
                {lineage.down.length === 0 ? (
                  <Tag>暂无下级法规</Tag>
                ) : (
                  <Space wrap size={[4, 4]}>
                    {lineage.down.map((item) => (
                      <Tag key={item.id} color={item.status === "abolished" ? "red" : "green"}>
                        {CODE_LIKE.test(item.code) ? `${item.code} ` : ""}{item.title}
                      </Tag>
                    ))}
                  </Space>
                )}
              </div>
            </>
          )}

          {reg.articles && reg.articles.length > 0 && (
            <>
              <h4 style={{ marginTop: 16 }}>法规条文（{reg.articles.length} 条）</h4>
              <Table columns={articleCols} dataSource={reg.articles} rowKey="number" size="small"
                pagination={{ defaultPageSize: 10 }} />
            </>
          )}

          {reg.source_files && reg.source_files.length > 0 && (
            <>
              <h4 style={{ marginTop: 16 }}>源文件</h4>
              {reg.source_files.map(f => (
                <div key={f.filename} style={{ marginBottom: 4 }}>
                  <Button type="link" size="small" style={{ paddingLeft: 0 }} onClick={() => handleViewSource(f.filename)}>
                    {f.filename}
                  </Button>
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
                    {Boolean(e.detail?.filename) && <div style={{ fontSize: 12 }}>文件: {String(e.detail?.filename)}</div>}
                    {Boolean(e.detail?.replaced_by) && <div style={{ fontSize: 12 }}>替代为: {String(e.detail?.replaced_by)}</div>}
                  </div>
                ),
              }))} />
            </>
          )}
        </div>
      )}
    </Modal>
    {sourcePreview && (
      <Modal
        title={`源文件：${sourcePreview.filename}`}
        open={!!sourcePreview}
        onCancel={closeSourcePreview}
        width={860}
        styles={{ body: { height: "70vh" } }}
        footer={[
          <Button key="download" onClick={() => {
            const a = document.createElement("a");
            a.href = sourcePreview.url;
            a.download = sourcePreview.filename;
            a.click();
          }}>
            下载
          </Button>,
          <Button key="close" type="primary" onClick={closeSourcePreview}>关闭</Button>,
        ]}
      >
        {sourcePreview.type === "application/pdf" || sourcePreview.type.startsWith("image/") ? (
          <iframe
            title={sourcePreview.filename}
            src={sourcePreview.url}
            style={{ width: "100%", height: "100%", border: "none" }}
          />
        ) : sourcePreview.text != null ? (
          <pre style={{ maxHeight: "100%", overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
            {sourcePreview.text}
          </pre>
        ) : (
          <div style={{ textAlign: "center", paddingTop: 80, color: "#999" }}>
            该格式暂不支持在线预览，请点击「下载」查看原文
          </div>
        )}
      </Modal>
    )}
    </>
  );
}
