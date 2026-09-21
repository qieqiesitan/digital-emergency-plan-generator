/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * 临时对照页（仅用于 antd `List` → `SimpleList` 的度量回归，验证完即删）。
 *
 * 渲染 13 组「同一份 props/markup，一边用 antd List、一边用 SimpleList」的列表，
 * 由 `_list_parity_probe.py` 在真浏览器里逐元素比对盒子与字体。
 */
import React from "react";
import ReactDOM from "react-dom/client";
import {
  Button,
  ConfigProvider,
  Empty,
  Input,
  Popconfirm,
  Space,
  Tag,
  Typography,
  List as AntList,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import { BankOutlined, DeleteOutlined, RightOutlined } from "@ant-design/icons";
import SimpleList from "@/components/common/SimpleList";
import "@/styles/global.css";

const { Text } = Typography;

const plans = [
  { id: "p1", title: "某某化工企业综合应急预案", plan_type: "综合预案", enterprise_name: "某某化工有限公司", completed_sections: 12, total_sections: 25, status: "草稿" },
  { id: "p2", title: "某某化工企业专项应急预案", plan_type: "专项预案", enterprise_name: "某某化工有限公司", completed_sections: 25, total_sections: 25, status: "已完成" },
];

const floors = [
  { id: "f1", name: "一号厂房", is_default: true, zone_count: 3, risk_point_count: 12 },
  { id: "f2", name: "二号厂房", is_default: false, zone_count: 5, risk_point_count: 21 },
];

const signs = [
  { svg_name: "warn", name: "当心爆炸", reason: "存在易燃气体" },
  { svg_name: "ban", name: "禁止吸烟", reason: "易燃易爆区域" },
];

const evidences = [
  { article_anchor: "第 12 条", relation: "依据", note: "与重大危险源辨识一致" },
  { article_anchor: "第 18 条", relation: "冲突", note: "安全距离要求更严格" },
];

const aiResults = [
  { accident_type: "火灾", method_type: "LEC", description: "可燃物泄漏遇火源", trigger_conditions: "明火作业", consequences: "人员烧伤", reasoning: "历史事故高频" },
  { accident_type: "爆炸", method_type: "LS", description: "容器超压", trigger_conditions: "安全阀失效", consequences: "厂房损毁", reasoning: "设备老化" },
];

const migrationItems = [
  { _key: "m1", source_name: "储罐区", status: "adopted", suggested_zone: "罐区", suggested_object: "储罐", suggested_event: "泄漏" },
  { _key: "m2", source_name: "装卸台", status: "modified", suggested_zone: "装卸区", suggested_object: "鹤管", suggested_event: "泄漏" },
];

const zones = [
  { client_id: "z1", name: "罐区", risk_level: "红色", suspected: false },
  { client_id: "z2", name: "装卸区", risk_level: "橙色", suspected: true },
];

const excluded = [
  { reason: "too_small", polygons: [{ points: [1, 2, 3] }] },
  { reason: "text_like", polygons: [{ points: [1, 2] }] },
];

const sections = [
  { key: "sec_1", title: "总则" },
  { key: "sec_2", title: "事故风险描述" },
];

type Case = { id: number; title: string; render: (L: any) => React.ReactNode };

const cases: Case[] = [
  {
    id: 1,
    title: "看板·最近编辑（默认尺寸 + extra + Meta）",
    render: (L) => (
      <L
        dataSource={plans}
        renderItem={(item: any) => (
          <L.Item
            style={{ cursor: "pointer" }}
            onClick={() => undefined}
            extra={<Tag color="blue">{item.status}</Tag>}
          >
            <L.Item.Meta
              title={
                <span>
                  <Tag color="purple">{item.plan_type}</Tag>
                  {" "}
                  {item.title}
                </span>
              }
              description={`${item.enterprise_name} · ${item.completed_sections}/${item.total_sections} 章节 · 3 小时前`}
            />
          </L.Item>
        )}
        locale={{ emptyText: <Empty description="暂无预案" /> }}
      />
    ),
  },
  {
    id: 2,
    title: "看板·企业切换弹窗（Meta + 行尾图标 + locale 空态）",
    render: (L) => (
      <L
        dataSource={[{ name: "某某化工有限公司", industry: "化学原料制造" }, { name: "某某物流有限公司", industry: "" }]}
        locale={{ emptyText: <Empty description="无匹配企业" /> }}
        renderItem={(e: any) => (
          <L.Item style={{ cursor: "pointer", padding: "12px 8px" }} onClick={() => undefined}>
            <L.Item.Meta
              title={
                <span>
                  <BankOutlined style={{ marginRight: 8 }} />
                  {e.name}
                </span>
              }
              description={e.industry || "未设置行业"}
            />
            <RightOutlined style={{ color: "#bbb" }} />
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 3,
    title: "楼层管理抽屉（actions 含 null 占位）",
    render: (L) => (
      <L
        dataSource={floors}
        renderItem={(f: any) => (
          <L.Item
            actions={[
              !f.is_default ? (
                <Button key="default" type="link" size="small">
                  设为默认
                </Button>
              ) : null,
              <Button key="rename" type="link" size="small">
                重命名
              </Button>,
              <Popconfirm key="delete" title={`删除楼层「${f.name}」？`}>
                <Button type="link" size="small" danger>
                  删除
                </Button>
              </Popconfirm>,
            ]}
          >
            <L.Item.Meta
              title={
                <Space>
                  <span>{f.name}</span>
                  {f.is_default && <Tag color="blue">默认</Tag>}
                </Space>
              }
              description={`${f.zone_count ?? 0} 分区 · ${f.risk_point_count ?? 0} 风险点`}
            />
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 4,
    title: "风险告知卡预览（size=small + header + locale=无）",
    render: (L) => (
      <L
        header={<span style={{ color: "#cf1322", fontWeight: 600 }}>建议删除（{signs.length}）</span>}
        size="small"
        dataSource={signs}
        locale={{ emptyText: "无" }}
        renderItem={(s: any) => (
          <L.Item key={s.svg_name}>
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ width: 16, height: 16, background: "#eee" }} />
              <div>
                <div>{s.name}</div>
                <div>理由：{s.reason}</div>
              </div>
            </div>
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 5,
    title: "AI 风险事件建议弹窗（actions + Meta 多段描述）",
    render: (L) => (
      <L
        dataSource={aiResults}
        renderItem={(item: any, idx: number) => (
          <L.Item
            key={idx}
            actions={[
              <Button key="accept" type="primary" size="small">
                采纳
              </Button>,
            ]}
          >
            <L.Item.Meta
              title={
                <Space>
                  {item.accident_type}
                  {item.method_type && <Tag>{item.method_type}</Tag>}
                </Space>
              }
              description={
                <div>
                  {item.description && <p style={{ margin: "4px 0" }}>描述：{item.description}</p>}
                  {item.trigger_conditions && <p style={{ margin: "4px 0" }}>触发条件：{item.trigger_conditions}</p>}
                  {item.consequences && <p style={{ margin: "4px 0" }}>后果：{item.consequences}</p>}
                  {item.reasoning && <p style={{ margin: "4px 0", color: "#1677ff" }}>理由：{item.reasoning}</p>}
                </div>
              }
            />
          </L.Item>
        )}
        locale={{ emptyText: "暂无建议" }}
      />
    ),
  },
  {
    id: 6,
    title: "重大危险源·依据面板（size=small + 垂直 Space）",
    render: (L) => (
      <L
        size="small"
        loading={false}
        dataSource={evidences}
        renderItem={(e: any) => (
          <L.Item>
            <Space orientation="vertical" size={0}>
              <Space>
                <Text strong>{e.article_anchor}</Text>
                <Tag color={e.relation === "冲突" ? "red" : "blue"}>{e.relation}</Tag>
              </Space>
              {e.note ? <Text type="secondary">{e.note}</Text> : null}
            </Space>
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 7,
    title: "迁移向导·步骤二（renderItem 直接返回 div，非 List.Item）",
    render: (L) => (
      <L
        dataSource={migrationItems}
        renderItem={(item: any) => (
          <div
            style={{
              padding: "12px 0",
              borderBottom: "1px solid #f0f0f0",
              opacity: item.status === "skipped" ? 0.5 : 1,
            }}
          >
            <span style={{ fontWeight: 500 }}>{item.source_name}</span>
            <Tag color="blue">{item.suggested_zone}</Tag>
          </div>
        )}
      />
    ),
  },
  {
    id: 8,
    title: "迁移向导·步骤三（size=small + 多个内联标签）",
    render: (L) => (
      <L
        size="small"
        dataSource={migrationItems}
        renderItem={(item: any) => (
          <L.Item>
            <span style={{ fontWeight: 500 }}>{item.source_name}</span>
            <span style={{ color: "#8c8c8c", margin: "0 8px" }}>→</span>
            <Tag color="blue">{item.suggested_zone}</Tag>
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 9,
    title: "四色图导入·分区清单（size=small + 选中态 style + actions）",
    render: (L) => (
      <L
        size="small"
        dataSource={zones}
        renderItem={(z: any, i: number) => (
          <L.Item
            style={i === 0 ? { background: "#e6f4ff", borderRadius: 6 } : undefined}
            onClick={() => undefined}
            actions={[
              <Button key="del" type="text" danger size="small">
                删除
              </Button>,
            ]}
          >
            <div style={{ width: "100%" }}>
              <Input value={z.name} size="small" style={{ marginBottom: 4 }} readOnly />
              <Tag color="red">{z.risk_level}</Tag>
            </div>
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 10,
    title: "四色图导入·已排除清单（size=small + actions 恢复）",
    render: (L) => (
      <L
        size="small"
        dataSource={excluded}
        renderItem={(item: any, i: number) => (
          <L.Item
            actions={[
              <Button key="restore" type="link">
                恢复
              </Button>,
            ]}
          >
            <span style={{ color: "#999", fontSize: 12 }}>
              {i + 1}. {item.reason} · {item.polygons[0]?.points.length ?? 0} 个顶点
            </span>
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 11,
    title: "章节个性化指令面板（size=small + Item 覆盖 padding）",
    render: (L) => (
      <L
        size="small"
        dataSource={sections}
        renderItem={(sec: any) => (
          <L.Item style={{ padding: "4px 0" }}>
            <Space style={{ width: "100%", justifyContent: "space-between" }}>
              <Text style={{ fontSize: 12, maxWidth: 160 }} ellipsis>
                {sec.title}
              </Text>
              <Space.Compact style={{ width: "60%" }}>
                <Input size="small" defaultValue="额外指令" style={{ fontSize: 12 }} />
                <Button size="small" icon={<DeleteOutlined />} />
              </Space.Compact>
            </Space>
          </L.Item>
        )}
      />
    ),
  },
  {
    id: 12,
    title: "空态（size=small + locale=无）",
    render: (L) => <L size="small" dataSource={[]} locale={{ emptyText: "无" }} renderItem={(x: any) => <L.Item>{x}</L.Item>} />,
  },
  {
    id: 13,
    title: "加载态（loading + 空数据）",
    render: (L) => <L loading dataSource={[]} locale={{ emptyText: "无" }} renderItem={(x: any) => <L.Item>{x}</L.Item>} />,
  },
];

function Root() {
  return (
    <ConfigProvider
      locale={zhCN}
      /* 与 App.tsx 的 theme.token 完全一致，避免字体栈差异污染度量对比 */
      theme={{
        token: {
          colorPrimary: "#1A56DB",
          borderRadius: 6,
          fontFamily: '-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <div style={{ padding: 24, background: "#fff" }}>
        {cases.map((c) => (
          <section key={c.id} data-case={c.id} style={{ marginBottom: 40 }}>
            <h3 style={{ marginBottom: 12 }}>
              {c.id}. {c.title}
            </h3>
            <div style={{ display: "flex", gap: 32, alignItems: "flex-start" }}>
              {(["antd", "simple"] as const).map((impl) => (
                <div key={impl} data-impl={impl} style={{ width: 520 }}>
                  {c.render(impl === "antd" ? AntList : SimpleList)}
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<Root />);
