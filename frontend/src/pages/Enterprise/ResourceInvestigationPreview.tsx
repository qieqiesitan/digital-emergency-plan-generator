import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spin, Button, message, Modal, Table, Tag, Input, Space } from "antd";
import { ArrowLeftOutlined, DownloadOutlined, EditOutlined, HistoryOutlined, SaveOutlined } from "@ant-design/icons";
import {
  createResourceInvestigationVersion,
  downloadResourceInvestigation,
  getResourceInvestigation,
  getResourceInvestigationPreview,
  listResourceInvestigationVersions,
  rollbackResourceInvestigationVersion,
  saveResourceInvestigationContent,
} from "@/services/resourceInvestigationService";
import type { ReportVersionItem } from "@/types/riskAssessment";
import type { ResourceInvestigationPreview as RIPreview } from "@/types/resourceInvestigation";

export default function ResourceInvestigationPreview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<RIPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [versions, setVersions] = useState<ReportVersionItem[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [currentVersion, setCurrentVersion] = useState(0);

  const reloadPreview = () => {
    if (!id) return;
    getResourceInvestigationPreview(id).then(setData).catch(() => {});
    getResourceInvestigation(id).then(r => setCurrentVersion(r.current_version ?? 0)).catch(() => {});
  };

  useEffect(() => {
    if (!id) return;
    getResourceInvestigationPreview(id)
      .then(setData)
      .finally(() => setLoading(false));
    getResourceInvestigation(id)
      .then(r => setCurrentVersion(r.current_version ?? 0))
      .catch(() => {});
  }, [id]);

  const handleExport = async () => {
    if (id) {
      try {
        await downloadResourceInvestigation(id);
      } catch (err: any) {
        message.error(err.message || "download failed");
      }
    }
  };

  const startEdit = async () => {
    if (!id) return;
    try {
      const report = await getResourceInvestigation(id);
      setDraft(report.content || "");
      setEditing(true);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "加载报告正文失败");
    }
  };

  const handleSaveContent = async () => {
    if (!id) return;
    setSaving(true);
    try {
      await saveResourceInvestigationContent(id, draft);
      message.success("报告正文已保存");
      setEditing(false);
      reloadPreview();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveVersion = async () => {
    if (!id) return;
    try {
      const v = await createResourceInvestigationVersion(id);
      setCurrentVersion(v.version_number);
      message.success(`已保存版本 V${v.version_number}`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存版本失败");
    }
  };

  const openVersions = async () => {
    if (!id) return;
    setVersionOpen(true);
    setVersionsLoading(true);
    try {
      setVersions(await listResourceInvestigationVersions(id));
    } catch {
      message.error("加载版本列表失败");
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleRollback = (v: ReportVersionItem) => {
    if (!id) return;
    Modal.confirm({
      title: `确定回滚到 V${v.version_number}？`,
      content: "回滚将恢复该版本的报告正文与摘要，当前内容将被覆盖。",
      okText: "回滚",
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await rollbackResourceInvestigationVersion(id, v.id);
          message.success(`已回滚到 V${v.version_number}`);
          setCurrentVersion(v.version_number);
          reloadPreview();
          setVersions(await listResourceInvestigationVersions(id));
        } catch (err) {
          message.error(err instanceof Error ? err.message : "回滚失败");
        }
      },
    });
  };

  if (loading) return <Spin size="large" />;
  if (!data) return <div>报告不存在</div>;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/enterprises/${id}`)}>
          返回企业详情
        </Button>
        <Space>
          {!editing ? (
            <>
              <Button icon={<HistoryOutlined />} onClick={openVersions}>版本历史</Button>
              <Button icon={<SaveOutlined />} onClick={handleSaveVersion}>保存版本</Button>
              <Button icon={<EditOutlined />} onClick={startEdit}>编辑</Button>
            </>
          ) : (
            <>
              <Button onClick={() => setEditing(false)}>取消</Button>
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSaveContent}>
                保存正文
              </Button>
            </>
          )}
          <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport}>
            下载 Word
          </Button>
        </Space>
      </div>
      {editing ? (
        <Input.TextArea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={30}
          style={{ fontFamily: "monospace", fontSize: 13 }}
          placeholder="报告正文（Markdown 格式）"
        />
      ) : (
        <div
          style={{
            background: "#fff",
            padding: "60px 80px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            maxWidth: 794,
            margin: "0 auto",
          }}
          dangerouslySetInnerHTML={{ __html: data.html }}
        />
      )}

      <Modal
        title="版本历史"
        open={versionOpen}
        onCancel={() => setVersionOpen(false)}
        footer={null}
        width={560}
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={versions}
          loading={versionsLoading}
          pagination={false}
          locale={{ emptyText: "暂无版本，点击「保存版本」创建快照" }}
          columns={[
            {
              title: "版本",
              dataIndex: "version_number",
              width: 110,
              render: (v: number) => (
                <span>
                  V{v}
                  {v === currentVersion && <Tag color="blue" style={{ marginLeft: 8 }}>当前</Tag>}
                </span>
              ),
            },
            { title: "类型", dataIndex: "created_by", width: 80, render: (v: string) => (v === "auto" ? "自动" : "手动") },
            { title: "时间", dataIndex: "created_at" },
            {
              title: "",
              render: (_: unknown, r: ReportVersionItem) => (
                <Button size="small" disabled={r.version_number === currentVersion} onClick={() => handleRollback(r)}>
                  回滚
                </Button>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
