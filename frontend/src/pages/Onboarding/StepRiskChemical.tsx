import { Button } from "antd";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
}

export default function StepRiskChemical(props: Props) {
  return (
    <div style={{ maxWidth: 760 }}>
      <h3>风险与危化品</h3>
      <p style={{ color: "#666" }}>开发中</p>
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={props.onPrev}>上一步</Button>
        <Button type="primary" onClick={props.onDone}>
          标记完成，下一步 →
        </Button>
      </div>
    </div>
  );
}
