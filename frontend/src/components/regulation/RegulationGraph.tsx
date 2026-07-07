import { useEffect, useRef, useState } from "react";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchRegulationGraph } from "@/services/regulationService";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: true, theme: "default" });

export function RegulationGraph() {
  const [svg, setSvg] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["regulationGraph"],
    queryFn: fetchRegulationGraph,
  });

  useEffect(() => {
    if (!data) return;
    const lines: string[] = ["graph TD"];

    for (const n of data.nodes) {
      const color = n.status === "abolished" ? "#ff4d4f" : "#52c41a";
      const label = `${n.label}`.replace(/"/g, "'");
      lines.push(`  ${n.id}["${label} ${n.status === "abolished" ? "\u274c" : "\u2705"}"]`);
      if (n.status === "abolished") lines.push(`  style ${n.id} fill:#fff1f0,stroke:#ff4d4f`);
      else if (n.node_type === "topic") lines.push(`  style ${n.id} fill:#e6f7ff,stroke:#1890ff`);
    }

    for (const e of data.edges) {
      lines.push(`  ${e.source} -->|${e.relation}| ${e.target}`);
    }

    const mcode = lines.join("\n");
    mermaid.render("regulation-graph-svg", mcode).then(({ svg: s }) => {
      setSvg(s);
    }).catch(() => {
      setSvg('<p style="color:#999;text-align:center;padding:40px">图谱数据不足，暂无法渲染</p>');
    });
  }, [data]);

  if (isLoading) return <Spin tip="加载图谱..." style={{ display: "block", textAlign: "center", padding: 60 }} />;

  return (
    <div style={{ overflow: "auto", padding: 16, background: "#fafafa", borderRadius: 8, minHeight: 300 }}
      dangerouslySetInnerHTML={{ __html: svg }} />
  );
}