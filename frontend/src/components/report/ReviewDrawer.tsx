import { useMemo, useState } from "react";
import { Alert, Button, Checkbox, Drawer, Empty, Space, Tag } from "antd";
import type { ReportIssue } from "@/types/reportWorkspace";

const SEVERITY_COLOR: Record<ReportIssue["severity"], string> = {
  error: "red",
  warning: "orange",
  info: "blue",
};

const SEVERITY_LABEL: Record<ReportIssue["severity"], string> = {
  error: "问题",
  warning: "警告",
  info: "提示",
};

interface ReviewDrawerProps {
  open: boolean;
  issues: ReportIssue[];
  onClose: () => void;
  onApply: (sectionKeys: string[]) => void;
  applying: boolean;
  /** section_key → 章节标题（侧栏同名键对应） */
  chapterTitleMap?: Record<string, string>;
}

/**
 * AI 审查抽屉：左侧展示按章节分组的 issue 列表（severity 标色），
 * 勾选章节后触发「生成修订」（adapter.applyReview），修订结果
 * 由工作台逐条 DiffPreviewModal 确认。
 */
export default function ReviewDrawer({
  open,
  issues,
  onClose,
  onApply,
  applying,
  chapterTitleMap,
}: ReviewDrawerProps) {
  const [checkedKeys, setCheckedKeys] = useState<string[]>([]);

  const groups = useMemo(() => {
    const map = new Map<string, ReportIssue[]>();
    issues.forEach((issue) => {
      const list = map.get(issue.section_key) || [];
      list.push(issue);
      map.set(issue.section_key, list);
    });
    return Array.from(map.entries()).map(([sectionKey, list]) => ({
      sectionKey,
      list,
      title: chapterTitleMap?.[sectionKey] || sectionKey,
      errorCount: list.filter((i) => i.severity === "error").length,
      warningCount: list.filter((i) => i.severity === "warning").length,
    }));
  }, [issues, chapterTitleMap]);

  const allKeys = groups.map((g) => g.sectionKey);
  const allChecked = allKeys.length > 0 && allKeys.every((k) => checkedKeys.includes(k));

  const toggleAll = () => {
    if (allChecked) setCheckedKeys([]);
    else setCheckedKeys(allKeys);
  };

  return (
    <Drawer
      title="AI 审查结果"
      width={560}
      open={open}
      onClose={() => {
        setCheckedKeys([]);
        onClose();
      }}
      extra={
        <Space>
          <Checkbox checked={allChecked} indeterminate={!allChecked && checkedKeys.length > 0} onChange={toggleAll}>
            全选章节
          </Checkbox>
          <Button
            type="primary"
            disabled={checkedKeys.length === 0 || groups.length === 0}
            loading={applying}
            onClick={() => onApply(checkedKeys)}
          >
            生成修订（已选 {checkedKeys.length} 章）
          </Button>
        </Space>
      }
      footer={
        <div style={{ textAlign: "right" }}>
          <Space>
            <Button onClick={() => { setCheckedKeys([]); onClose(); }}>关闭</Button>
            <Button
              type="primary"
              disabled={checkedKeys.length === 0 || groups.length === 0}
              loading={applying}
              onClick={() => onApply(checkedKeys)}
            >
              生成修订
            </Button>
          </Space>
        </div>
      }
    >
      {groups.length === 0 ? (
        <Empty description="未发现问题，报告质量良好" />
      ) : (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="勾选章节后点击「生成修订」，系统将逐条给出原文/修订对比，确认后写入草稿。"
          />
          {groups.map((g) => {
            const checked = checkedKeys.includes(g.sectionKey);
            return (
              <div
                key={g.sectionKey}
                style={{
                  border: "1px solid #f0f0f0",
                  borderRadius: 8,
                  marginBottom: 12,
                  padding: "10px 12px",
                }}
              >
                <label style={{ display: "flex", gap: 8, cursor: "pointer", alignItems: "flex-start" }}>
                  <Checkbox
                    checked={checked}
                    onChange={(e) => {
                      setCheckedKeys((prev) =>
                        e.target.checked
                          ? [...prev, g.sectionKey]
                          : prev.filter((k) => k !== g.sectionKey),
                      );
                    }}
                  />
                  <span style={{ flex: 1 }}>
                    <span style={{ fontWeight: 600 }}>{g.title}</span>
                    <span style={{ marginLeft: 8, fontSize: 12, color: "#bbb" }}>{g.sectionKey}</span>
                    <span style={{ marginLeft: 8 }}>
                      {g.errorCount > 0 && <Tag color="red">{g.errorCount} 问题</Tag>}
                      {g.warningCount > 0 && <Tag color="orange">{g.warningCount} 警告</Tag>}
                    </span>
                    {g.list.map((issue, idx) => (
                      <div
                        key={`${issue.kind}-${idx}`}
                        style={{
                          marginTop: 6,
                          fontSize: 13,
                          color: issue.severity === "info" ? "#666" : "#333",
                        }}
                      >
                        <Tag color={SEVERITY_COLOR[issue.severity]} style={{ marginRight: 6 }}>
                          {SEVERITY_LABEL[issue.severity]}
                        </Tag>
                        {issue.issue}
                        {issue.suggestion && (
                          <div style={{ color: "#999", marginTop: 2, fontSize: 12 }}>
                            建议：{issue.suggestion}
                          </div>
                        )}
                      </div>
                    ))}
                  </span>
                </label>
              </div>
            );
          })}
        </>
      )}
    </Drawer>
  );
}
