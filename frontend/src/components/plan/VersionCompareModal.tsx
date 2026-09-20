/**
 * 版本对比弹窗：选两个版本 → 逐章节看「新增 / 删除 / 修改」以及新旧正文。
 *
 * 数据来自既有接口 `GET /plans/{id}/versions/compare`（N-25 修好路由后一直可用），
 * 之前只是**没有 UI 入口**（版本页只有"回滚"）。这里只做展示，不新增后端。
 * 正文为 HTML，一律经 `sanitizeHtml`（与章节预览/报告预览同一实现）后再渲染。
 */
import { useMemo, useState } from "react";
import { Alert, Collapse, Empty, Modal, Select, Space, Spin, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { compareVersions, listVersions } from "@/services/planService";
import { groupDiffs, plainTextLength, summarizeDiffs, type DiffKind } from "@/utils/versionDiff";
import { sanitizeHtml } from "@/utils/sanitize";

const { Text } = Typography;

const KIND_COLOR: Record<DiffKind, string> = {
  added: "green", removed: "red", modified: "orange", unchanged: "default",
};

interface Props {
  open: boolean;
  onClose: () => void;
  planId: string;
  /** 打开时的默认 A 侧（通常是用户点的那一行） */
  initialA?: number;
}

export default function VersionCompareModal({ open, onClose, planId, initialA }: Props) {
  const [a, setA] = useState<number | undefined>(initialA);
  const [b, setB] = useState<number | undefined>(undefined);

  const { data: versions = [] } = useQuery({
    queryKey: ["versions", planId],
    queryFn: () => listVersions(planId),
    enabled: open && !!planId,
  });

  // 打开时给一组合理默认：A=点选的那版，B=当前最新版（与 A 不同）
  const numbers = useMemo(
    () => [...new Set((versions || []).map((v) => v.version_number))].sort((x, y) => y - x),
    [versions],
  );
  const effA = a ?? initialA ?? numbers[1] ?? numbers[0];
  const effB = b ?? numbers.find((n) => n !== effA) ?? effA;

  const { data, isFetching, error } = useQuery({
    queryKey: ["versionCompare", planId, effA, effB],
    queryFn: () => compareVersions(planId, effA!, effB!),
    enabled: open && effA !== undefined && effB !== undefined && effA !== effB,
  });

  const groups = useMemo(() => groupDiffs(data?.diffs), [data]);
  const summary = useMemo(() => summarizeDiffs(data?.diffs), [data]);

  const options = numbers.map((n) => ({ value: n, label: `V${n}` }));

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={1000}
      title="版本对比"
      destroyOnHidden
    >
      <Space style={{ marginBottom: 12 }} wrap>
        <Text type="secondary">对比</Text>
        <Select style={{ width: 110 }} value={effA} options={options} onChange={setA} placeholder="版本 A" />
        <Text type="secondary">→</Text>
        <Select style={{ width: 110 }} value={effB} options={options} onChange={setB} placeholder="版本 B" />
        {data && (
          <Space size={4}>
            <Tag color="green">新增 {summary.added}</Tag>
            <Tag color="red">删除 {summary.removed}</Tag>
            <Tag color="orange">修改 {summary.modified}</Tag>
            <Tag>未变 {summary.unchanged}</Tag>
          </Space>
        )}
      </Space>

      {effA === effB && <Alert type="info" showIcon title="请选择两个不同的版本" />}
      {error != null && <Alert type="error" showIcon title="版本对比失败" description={String((error as Error).message || "")} />}
      {isFetching && <div style={{ textAlign: "center", padding: 24 }}><Spin /></div>}

      {!isFetching && data && summary.changed === 0 && (
        <Empty description={`V${effA} 与 V${effB} 内容完全一致`} />
      )}

      {!isFetching && data && summary.changed > 0 && (
        <Collapse
          defaultActiveKey={groups.filter((g) => g.kind !== "unchanged").map((g) => g.kind)}
          items={groups.map((g) => ({
            key: g.kind,
            label: (
              <Space>
                <Tag color={KIND_COLOR[g.kind]}>{g.label}</Tag>
                <Text type="secondary">{g.items.length} 个章节</Text>
              </Space>
            ),
            children: (
              <Space orientation="vertical" style={{ width: "100%" }} size={14}>
                {g.items.map((item) => (
                  <div key={item.section_key} style={{ borderBottom: "1px solid #f0f0f0", paddingBottom: 10 }}>
                    <div style={{ marginBottom: 6 }}>
                      <Text strong>{item.title}</Text>
                      <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                        {item.section_key} · 旧 {plainTextLength(item.old_content)} 字 → 新 {plainTextLength(item.new_content)} 字
                      </Text>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: item.old_content && item.new_content ? "1fr 1fr" : "1fr", gap: 12 }}>
                      {item.old_content ? (
                        <div>
                          <Tag color="red">改前（V{effA}）</Tag>
                          <div
                            className="version-diff-pane"
                            dangerouslySetInnerHTML={{ __html: sanitizeHtml(item.old_content) }}
                          />
                        </div>
                      ) : null}
                      {item.new_content ? (
                        <div>
                          <Tag color="green">改后（V{effB}）</Tag>
                          <div
                            className="version-diff-pane"
                            dangerouslySetInnerHTML={{ __html: sanitizeHtml(item.new_content) }}
                          />
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </Space>
            ),
          }))}
        />
      )}
    </Modal>
  );
}
