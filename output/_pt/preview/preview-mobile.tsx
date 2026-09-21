/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * 临时预演页（截图后即删）：渲染 3 个"无引用移动端文件"的真实样子。
 *  - RiskSourceListScreen（旧风险源页，接口还活着）
 *  - PlanCard（已被 PlanCardsScreen 的内联卡片取代）
 *  - useStreamGeneration（已被"后台任务 + 轮询"取代；这里用假 SSE 驱动真实 hook）
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/mobile/components/ui/Toast";
import RiskSourceListScreen from "@/mobile/screens/RiskSourceListScreen";
import PlanCard from "@/mobile/components/plan/PlanCard";
import { useStreamGeneration } from "@/mobile/hooks/useStreamGeneration";
import "@/mobile/styles/tokens.css";
import "@/mobile/styles/base.css";

const ENT = "10e11995-e682-405a-9035-fbde13cca213";

/* ── 假的 SSE：让 useStreamGeneration 真的跑起来（内容是"排查计划"这种真实感文本）── */
function installFakeSSE() {
  const chunks = [
    "罐区每周综合安全排查计划\n\n",
    "一、排查范围：储罐区（4 座常压罐）、装卸区（3 个鹤管位）\n",
    "二、排查频次：每周 2 次（周一、周五 09:00 前完成）\n",
    "三、责任人：罐区班组长（复核：安全总监）\n",
    "四、排查要点：\n",
    "  1. 储罐液位计、温度计读数是否正常，无卡涩；\n",
    "  2. 围堰、排水阀完好，无积水积油；\n",
    "  3. 可燃气体报警器在检定有效期内；\n",
    "  4. 装卸鹤管静电接地可靠，作业票齐全；\n",
    "  5. 消防器材压力在绿区、铅封完好。\n",
    "五、异常处置：发现重大隐患立即停止作业并报安全总监。",
  ];
  const enc = new TextEncoder();
  window.fetch = (async () => {
    const stream = new ReadableStream({
      async start(controller) {
        for (const c of chunks) {
          controller.enqueue(enc.encode(`data: ${JSON.stringify({ type: "chunk", content: c })}\n\n`));
          await new Promise((r) => setTimeout(r, 600));
        }
        controller.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  }) as any;
}
installFakeSSE();

function Frame({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ font: "600 14px/1.4 -apple-system, 'Segoe UI', 'PingFang SC', sans-serif", marginBottom: 2 }}>
        {title}
      </div>
      {note && <div style={{ font: "12px/1.5 -apple-system, 'Segoe UI', 'PingFang SC', sans-serif", color: "#8c8c8c", marginBottom: 8 }}>{note}</div>}
      <div
        style={{
          width: 390, height: 844, overflow: "hidden", border: "10px solid #111",
          borderRadius: 36, background: "#fff", position: "relative",
        }}
      >
        {children}
      </div>
    </div>
  );
}

function StreamPreview() {
  const [started, setStarted] = React.useState(false);
  const { state, generateSingle } = useStreamGeneration({});

  React.useEffect(() => {
    if (!started) {
      setStarted(true);
      void generateSingle("plan-1", "sec_3", "事故风险描述");
    }
  }, [started, generateSingle]);

  return (
    <div className="bg-neutral-50 min-h-dvh p-md">
      <div className="bg-white rounded-md shadow-card p-md">
        <div className="flex items-center justify-between mb-sm">
          <span className="text-h3 font-semibold text-neutral-900">生成章节：事故风险描述</span>
          <span className={`text-caption ${state.isGenerating ? "text-primary-600" : "text-neutral-400"}`}>
            {state.isGenerating ? "生成中…" : state.error ? "失败" : "已完成"}
          </span>
        </div>
        <div className="h-1 bg-neutral-100 rounded-full overflow-hidden mb-md">
          <div
            className="h-full bg-primary-500 transition-all"
            style={{ width: state.isGenerating ? "62%" : "100%" }}
          />
        </div>
        <pre
          style={{
            whiteSpace: "pre-wrap", font: "12px/1.7 -apple-system, 'PingFang SC', sans-serif",
            color: "#262626", margin: 0, maxHeight: 520, overflow: "auto",
          }}
        >
          {state.content || "（等待第一个分片…）"}
          {state.isGenerating && <span style={{ color: "#1A56DB" }}>▌</span>}
        </pre>
        <div className="flex gap-sm mt-md">
          <button className="flex-1 h-10 rounded-md border border-neutral-200 text-neutral-600 text-caption">停止</button>
          <button className="flex-1 h-10 rounded-md bg-primary-600 text-white text-caption">保存到章节</button>
        </div>
      </div>
      <div className="text-caption text-neutral-400 mt-sm">
        hook 状态：isGenerating={String(state.isGenerating)} · 已收 {state.content.length} 字
      </div>
    </div>
  );
}

function App() {
  const queryClient = React.useMemo(() => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchOnMount: false, refetchOnWindowFocus: false, networkMode: "offlineFirst" } },
    });
    qc.setQueryData(["risk-sources", ENT], [
      { id: "r1", enterprise_id: ENT, categories: ["火灾", "爆炸"], name: "甲醇储罐", location: "罐区 1# 罐", description: "5000m³ 常压储罐", risk_level: "重大", likelihood: "中", severity: "高", control_measures: "液位联锁", sort_order: 1, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
      { id: "r2", enterprise_id: ENT, categories: ["泄漏"], name: "装卸鹤管", location: "装卸区 3# 位", description: "汽车装卸鹤管", risk_level: "较大", likelihood: "中", severity: "中", control_measures: "静电接地", sort_order: 2, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
      { id: "r3", enterprise_id: ENT, categories: ["火灾"], name: "危废暂存间", location: "厂区西侧", description: "暂存废机油", risk_level: "一般", likelihood: "低", severity: "中", control_measures: "分类堆放", sort_order: 3, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
      { id: "r4", enterprise_id: ENT, categories: ["触电"], name: "配电室", location: "生产车间东侧", description: "10kV 配电", risk_level: "低", likelihood: "低", severity: "中", control_measures: "门禁 + 定期巡检", sort_order: 4, created_at: "2026-09-01T00:00:00Z", location_x: null, location_y: null },
    ]);
    return qc;
  }, []);

  return (
    <div style={{ display: "flex", gap: 28, padding: 24, background: "#fff", alignItems: "flex-start" }}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <Frame
            title="② 移动端 RiskSourceListScreen（旧「风险源」页）"
            note="mobile/screens/RiskSourceListScreen.tsx（221 行）· 接口仍可用，只是没有路由挂它"
          >
            <MemoryRouter initialEntries={[`/m/enterprises/${ENT}/risk-sources`]}>
              <Routes>
                <Route path="/m/enterprises/:id/risk-sources" element={<RiskSourceListScreen />} />
              </Routes>
            </MemoryRouter>
          </Frame>
        </ToastProvider>
      </QueryClientProvider>

      <div>
        <div style={{ font: "600 14px/1.4 -apple-system, 'Segoe UI', 'PingFang SC', sans-serif", marginBottom: 2 }}>
          ③ 移动端 PlanCard（预案卡片）
        </div>
        <div style={{ font: "12px/1.5 -apple-system, 'Segoe UI', 'PingFang SC', sans-serif", color: "#8c8c8c", marginBottom: 8 }}>
          mobile/components/plan/PlanCard.tsx（88 行）· 已被 PlanCardsScreen 的内联卡片取代
        </div>
        <div style={{ width: 390, border: "10px solid #111", borderRadius: 36, background: "#fafafa", padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          <PlanCard id="p1" title="西安宝岳综合应急预案" planType="comprehensive" status="completed" enterpriseName="西安宝岳空间科技" updatedAt="2 小时前" onPress={() => undefined} />
          <PlanCard id="p2" title="罐区专项应急预案" planType="special" status="generating" enterpriseName="西安宝岳空间科技" accidentType="泄漏 / 火灾" updatedAt="刚刚" onPress={() => undefined} />
          <PlanCard id="p3" title="装卸区现场处置方案" planType="onsite" status="draft" enterpriseName="西安宝岳空间科技" accidentType="泄漏" updatedAt="昨天" onPress={() => undefined} />
        </div>
      </div>

      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <Frame
            title="④ 移动端 useStreamGeneration（流式生成 hook）"
            note="mobile/hooks/useStreamGeneration.ts（190 行）· 用假 SSE 实时驱动，展示「生成中」界面"
          >
            <StreamPreview />
          </Frame>
        </ToastProvider>
      </QueryClientProvider>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
