import { Button } from "antd";

interface Props {
  name: string;
  industry?: string;
  majorCount?: number;
  onBack: () => void;
  onEdit: () => void;
}

export default function CockpitHeader({ name, industry, majorCount, onBack, onEdit }: Props) {
  return (
    <div className="cp-top">
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <Button type="text" size="small" onClick={onBack} style={{ color: "#00d4ff", paddingLeft: 0 }}>
          ← 返回
        </Button>
        <span className="cp-name">
          {name} <small className="cp-sub">Enterprise Cockpit · 企业驾驶舱</small>
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
        <span className="cp-live"><i />系统运行正常</span>
        {industry && <span className="cp-tag">{industry}</span>}
        {typeof majorCount === "number" && majorCount > 0 && (
          <span className="cp-tag red">重大风险 {majorCount}</span>
        )}
        <button type="button" className="cp-btn" onClick={onEdit}>编辑企业</button>
      </div>
    </div>
  );
}
