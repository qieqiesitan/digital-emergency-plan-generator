/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * 临时预演页（截图后即删）：把"AI 智能引导界面如果真的建起来长什么样"和
 * "4 个无引用文件中的桌面那个长什么样"渲染出来给业务方看。
 * 数据是示例（mock），接口契约来自 POST /enterprises/{id}/hazard-inspection/ai/setup-wizard。
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Alert, Button, Card, Checkbox, ConfigProvider, Divider, Input, Radio, Select,
  Space, Steps, Table, Tag, Typography,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import { CheckCircleFilled, RobotOutlined } from "@ant-design/icons";
import RiskSourceForm from "@/components/enterprise/RiskSourceForm";
import "@/styles/global.css";

const { Title, Text, Paragraph } = Typography;

const ENT = "10e11995-e682-405a-9035-fbde13cca213";

/* ── 智能引导：三块建议的示例数据（形状与后端契约一致）───────────────── */
const ORG_NODES = [
  { id: "n1", type: "dept", name: "安全管理部", parent: null },
  { id: "n2", type: "team", name: "安全管理组", parent: "安全管理部" },
  { id: "n3", type: "position", name: "安全总监", parent: "安全管理部" },
  { id: "n4", type: "dept", name: "生产运行部", parent: null },
  { id: "n5", type: "team", name: "罐区班组", parent: "生产运行部" },
  { id: "n6", type: "team", name: "装卸班组", parent: "生产运行部" },
  { id: "n7", type: "position", name: "班组长", parent: "罐区班组" },
];

const PLANS = [
  { name: "罐区每周综合安全排查", category: "综合排查", frequency: "每周", weekdays: [1, 5], who: "罐区班组长", zones: ["储罐区", "装卸区"] },
  { name: "装卸作业专项排查", category: "专项排查", frequency: "每月", weekdays: [10], who: "生产运行部负责人", zones: ["装卸区"] },
  { name: "消防设施季节性排查", category: "季节性排查", frequency: "每季度", weekdays: [1], who: "安全管理部", zones: ["全厂"] },
  { name: "节假日专项排查", category: "节假日排查", frequency: "每次节假日前", weekdays: [], who: "安全总监", zones: ["全厂"] },
];

const CHECKLIST = [
  { content: "储罐液位计、温度计是否完好且读数正常", expected_note: "现场查看仪表" },
  { content: "罐区围堰、排水阀是否完好、无积水积油", expected_note: "拍照留证" },
  { content: "可燃气体报警器是否在检定有效期内", expected_note: "核对检定证书" },
  { content: "装卸鹤管、静电接地是否可靠连接", expected_note: "作业前检查" },
  { content: "消防器材压力是否在绿区、铅封完好", expected_note: "随机抽查 3 处" },
];

function WizardPreview() {
  return (
    <Card
      style={{ width: 1180, margin: "0 auto" }}
      styles={{ body: { padding: 24 } }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <RobotOutlined style={{ color: "#1A56DB", fontSize: 18 }} />
        <Title level={4} style={{ margin: 0 }}>智能引导：一次把「组织 / 排查计划 / 检查表」建好</Title>
      </div>
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        输入行业与主要区域 → AI 一次返回三块建议 → <Text strong>逐块确认后</Text>才写入（接口本身不落库，误点不会脏数据）。
      </Paragraph>

      <Steps
        size="small"
        current={1}
        items={[
          { title: "填写基础信息" },
          { title: "审阅三块建议" },
          { title: "分块确认写入" },
          { title: "完成" },
        ]}
        style={{ marginBottom: 20 }}
      />

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 20 }}>
        {/* 第 1 步：输入 */}
        <div>
          <Card size="small" title="① 填写基础信息" style={{ background: "#fafafa" }}>
            <Space direction="vertical" style={{ width: "100%" }} size={10}>
              <div>
                <Text type="secondary">所属行业</Text>
                <Input defaultValue="化工 / 危险化学品经营" style={{ marginTop: 4 }} />
              </div>
              <div>
                <Text type="secondary">主要区域（逗号分隔）</Text>
                <Input.TextArea defaultValue="储罐区、装卸区、生产车间、危废暂存间" rows={3} style={{ marginTop: 4 }} />
              </div>
              <div>
                <Text type="secondary">员工数量</Text>
                <Input defaultValue="120" style={{ marginTop: 4 }} />
              </div>
              <div>
                <Text type="secondary">排查频次偏好</Text>
                <Radio.Group defaultValue="standard" style={{ marginTop: 4 }}>
                  <Radio.Button value="light">精简</Radio.Button>
                  <Radio.Button value="standard">标准</Radio.Button>
                  <Radio.Button value="strict">严格</Radio.Button>
                </Radio.Group>
              </div>
              <Button type="primary" block icon={<RobotOutlined />}>生成建议</Button>
              <Text type="secondary" style={{ fontSize: 12 }}>
                未配置 AI 时返回 available:false，界面自动降级为"手动维护"提示，不报错。
              </Text>
            </Space>
          </Card>
        </div>

        {/* 第 2 步：三块建议 */}
        <div>
          <Card
            size="small"
            title={<span>② 审阅建议 <Tag color="blue">AI 生成</Tag><Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>全部可改，未确认不写库</Text></span>}
          >
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
              {/* 组织架构 */}
              <div>
                <Text strong>组织架构建议（{ORG_NODES.length} 个节点）</Text>
                <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, marginTop: 8, height: 232, overflow: "auto" }}>
                  {ORG_NODES.map((n) => (
                    <div key={n.id} style={{ paddingLeft: n.parent ? 16 : 0, marginBottom: 6 }}>
                      <Checkbox defaultChecked>
                        <Text style={{ fontSize: 13 }}>{n.name}</Text>
                        <Tag style={{ marginLeft: 6 }} color={n.type === "dept" ? "blue" : n.type === "team" ? "green" : "purple"}>
                          {n.type === "dept" ? "部门" : n.type === "team" ? "班组" : "岗位"}
                        </Tag>
                      </Checkbox>
                    </div>
                  ))}
                </div>
                <Button size="small" type="primary" block style={{ marginTop: 8 }}>确认并写入组织架构</Button>
              </div>

              {/* 排查计划 */}
              <div>
                <Text strong>排查计划建议（{PLANS.length} 个计划）</Text>
                <Table
                  size="small"
                  pagination={false}
                  style={{ marginTop: 8 }}
                  dataSource={PLANS}
                  rowKey="name"
                  columns={[
                    { title: "计划", dataIndex: "name", ellipsis: true,
                      render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text> },
                    { title: "频次", dataIndex: "frequency", width: 74,
                      render: (v: string) => <Tag color="orange">{v}</Tag> },
                    { title: "负责", dataIndex: "who", width: 96, ellipsis: true,
                      render: (v: string) => <Text style={{ fontSize: 12 }} type="secondary">{v}</Text> },
                  ]}
                />
                <Button size="small" type="primary" block style={{ marginTop: 8 }}>确认并生成计划</Button>
              </div>

              {/* 检查表 */}
              <div>
                <Text strong>检查表模板建议（{CHECKLIST.length} 条，可继续加）</Text>
                <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, marginTop: 8, height: 232, overflow: "auto" }}>
                  {CHECKLIST.map((c, i) => (
                    <div key={i} style={{ marginBottom: 8 }}>
                      <Checkbox defaultChecked>
                        <Text style={{ fontSize: 13 }}>{c.content}</Text>
                      </Checkbox>
                      <div style={{ marginLeft: 24 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>要求：{c.expected_note}</Text>
                      </div>
                    </div>
                  ))}
                </div>
                <Button size="small" type="primary" block style={{ marginTop: 8 }}>确认并生成检查表</Button>
              </div>
            </div>

            <Divider style={{ margin: "14px 0" }} />
            <Space>
              <Button type="primary">全部确认写入</Button>
              <Button>重新生成</Button>
              <Text type="secondary" style={{ fontSize: 12 }}>
                写入走各自的既有端点（组织架构 / 排查计划 / 检查表模板），失败只影响对应那一块。
              </Text>
            </Space>
          </Card>

          <Alert
            style={{ marginTop: 14 }}
            type="info"
            showIcon
            message="③ 完成后：跳转到「排查计划」列表，显示 4 个计划 + 首次排查任务已按频次排期"
            description={<Text type="secondary" style={{ fontSize: 12 }}>
              组织架构写入后，公司组织页会出现 安全管理部 / 生产运行部 两个部门与 3 个班组；检查表模板出现在「检查表模板」页，可直接用于新建排查任务。
            </Text>}
          />
        </div>
      </div>
    </Card>
  );
}

function App() {
  const queryClient = React.useMemo(() => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchOnMount: false, refetchOnWindowFocus: false } },
    });
    // 旧"风险源"表单要的数据：直接喂缓存，避免真发请求
    qc.setQueryData(["riskSources", ENT], {
      data: {
        items: [
          { id: "r1", enterprise_id: ENT, categories: ["火灾", "爆炸"], name: "甲醇储罐", location: "罐区 1# 罐", description: "5000m³ 常压储罐", risk_level: "重大", likelihood: "中", severity: "高", control_measures: "液位联锁 + 每周巡检", sort_order: 1, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
          { id: "r2", enterprise_id: ENT, categories: ["泄漏"], name: "装卸鹤管", location: "装卸区 3# 位", description: "汽车装卸鹤管", risk_level: "较大", likelihood: "中", severity: "中", control_measures: "静电接地 + 作业票", sort_order: 2, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
          { id: "r3", enterprise_id: ENT, categories: ["火灾"], name: "危废暂存间", location: "厂区西侧", description: "暂存废机油、废溶剂", risk_level: "一般", likelihood: "低", severity: "中", control_measures: "分类堆放 + 每周检查", sort_order: 3, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
        ],
        total: 3,
      },
    });
    return qc;
  }, []);

  return (
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#1A56DB", borderRadius: 6 } }}>
      <QueryClientProvider client={queryClient}>
        <div style={{ padding: 24, background: "#fff" }}>
          <WizardPreview />

          <Divider style={{ margin: "32px 0 20px" }}>以下为「4 个无引用文件」中的桌面那个（实渲染）</Divider>
          <Card
            style={{ width: 1180, margin: "0 auto" }}
            title={<span>旧「风险源」表单 <Tag color="red">当前全站无路由挂载</Tag><Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>components/enterprise/RiskSourceForm.tsx（230 行）</Text></span>}
          >
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 14 }}
              message={<span><CheckCircleFilled /> 它的接口仍然活着：/enterprises/&#123;id&#125;/risk-sources 既能读也能写，只是没有页面挂它</span>}
              description="所以它是「可用但没入口」的旧模型界面，而不是坏代码。"
            />
            <RiskSourceForm enterpriseId={ENT} floorPlanUrl={null} />
          </Card>
        </div>
      </QueryClientProvider>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
