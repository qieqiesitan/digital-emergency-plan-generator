import { Modal, Button, Typography } from "antd";

const { Text } = Typography;

interface DiffPreviewModalProps {
  open: boolean;
  oldText: string;
  newText: string;
  onAccept: () => void;
  onReject: () => void;
  onClose: () => void;
}

function diffLines(oldText: string, newText: string) {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const maxLen = Math.max(oldLines.length, newLines.length);
  const rows = [];
  for (let i = 0; i < maxLen; i++) {
    const o = oldLines[i] ?? "";
    const n = newLines[i] ?? "";
    rows.push({ old: o, new: n, changed: o !== n });
  }
  return rows;
}

export default function DiffPreviewModal({
  open, oldText, newText, onAccept, onReject, onClose,
}: DiffPreviewModalProps) {
  const rows = diffLines(oldText, newText);
  return (
    <Modal
      title="生成结果对比"
      open={open}
      width={860}
      onCancel={onClose}
      footer={[
        <Button key="reject" danger onClick={onReject}>拒绝，恢复原文</Button>,
        <Button key="accept" type="primary" onClick={onAccept}>接受新内容</Button>,
      ]}
    >
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ flex: 1, border: "1px solid #f0f0f0", padding: 8, maxHeight: 420, overflow: "auto" }}>
          <Text strong>原文</Text>
          {rows.map((r, i) => (
            <div key={i} style={{ background: r.changed ? "#fff1f0" : "transparent", whiteSpace: "pre-wrap" }}>
              {r.old}
            </div>
          ))}
        </div>
        <div style={{ flex: 1, border: "1px solid #f0f0f0", padding: 8, maxHeight: 420, overflow: "auto" }}>
          <Text strong>新内容</Text>
          {rows.map((r, i) => (
            <div key={i} style={{ background: r.changed ? "#f6ffed" : "transparent", whiteSpace: "pre-wrap" }}>
              {r.new}
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
}
