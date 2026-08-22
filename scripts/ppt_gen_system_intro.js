/**
 * 生成「数字化应急预案自动生成系统-系统介绍.pptx」（客户/企业演示版，10 页）
 *
 * 运行方式（依赖安装在临时目录，通过 NODE_PATH 引用）：
 *   $env:NODE_PATH = "$env:TEMP\ppt-build-pptgen\node_modules"
 *   node scripts/ppt_gen_system_intro.js
 *
 * 设计依据：docs/superpowers/specs/2026-08-21-system-intro-ppt-design.md
 * QA：脚本内置文本宽度预算断言（CJK≈1em/字），配合 markitdown / validate.py 校验。
 */
"use strict";

const path = require("path");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const PptxGenJS = require("pptxgenjs");
const {
  FiClock, FiDollarSign, FiFileText, FiAlertTriangle,
  FiDatabase, FiBookOpen, FiCpu,
  FiEdit3, FiZap, FiCheckCircle, FiDownload,
  FiGlobe, FiTarget, FiClipboard,
  FiGrid, FiLink, FiPenTool,
  FiBarChart2, FiLayers, FiSearch, FiMap, FiBell, FiCheckSquare,
  FiActivity, FiSmartphone, FiMapPin,
  FiShield, FiLock, FiServer,
  FiThumbsUp, FiAward, FiUsers,
} = require("react-icons/fi");

// ---------------------------------------------------------------- 常量
const OUT = path.resolve(__dirname, "..", "数字化应急预案自动生成系统-系统介绍.pptx");

const NAVY = "1F3A5F";
const NAVY_DEEP = "16283F";
const NAVY_SOFT = "2A4A75";
const BG = "F5F7FA";
const WHITE = "FFFFFF";
const GREEN = "2E8B57";
const GREEN_LIGHT = "E9F3ED";
const BLUE_LIGHT = "E7EDF5";
const MUTED = "6B7A90";
const ICE = "CADCFC";
const LINE = "E3EAF2";
const DARK_TEXT = "22324A";

const M = 0.55;                       // 页边距
const SW = 13.333;                    // 版式宽
const SH = 7.5;                       // 版式高
const CJK_FONT = "Microsoft YaHei";
const LATIN_FONT = "Calibri";

// ---------------------------------------------------------------- 图标流水线
const ICON_COMPONENTS = {
  clock: FiClock,
  dollar: FiDollarSign,
  "file-text": FiFileText,
  alert: FiAlertTriangle,
  database: FiDatabase,
  "book-open": FiBookOpen,
  cpu: FiCpu,
  "edit-3": FiEdit3,
  zap: FiZap,
  "check-circle": FiCheckCircle,
  download: FiDownload,
  globe: FiGlobe,
  target: FiTarget,
  clipboard: FiClipboard,
  grid: FiGrid,
  link: FiLink,
  "pen-tool": FiPenTool,
  "bar-chart-2": FiBarChart2,
  layers: FiLayers,
  search: FiSearch,
  map: FiMap,
  bell: FiBell,
  "check-square": FiCheckSquare,
  activity: FiActivity,
  smartphone: FiSmartphone,
  "map-pin": FiMapPin,
  shield: FiShield,
  lock: FiLock,
  server: FiServer,
  "thumbs-up": FiThumbsUp,
  award: FiAward,
  users: FiUsers,
};

let pptx; // 模块级引用，供布局 helper 使用（在 main 中初始化）

const iconCache = new Map();
async function preloadIcons(names) {
  const jobs = [...new Set(names)].map(async (name) => {
    const Comp = ICON_COMPONENTS[name];
    if (!Comp) throw new Error(`未知图标: ${name}`);
    const svg = ReactDOMServer.renderToStaticMarkup(
      React.createElement(Comp, { size: 32, color: "#FFFFFF", "aria-hidden": true })
    );
    const buf = await sharp(Buffer.from(svg))
      .resize(256, 256, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png()
      .toBuffer();
    iconCache.set(name, "image/png;base64," + buf.toString("base64"));
  });
  await Promise.all(jobs);
}
function iconData(name) {
  if (!iconCache.has(name)) throw new Error(`图标未预载: ${name}`);
  return iconCache.get(name);
}

// ---------------------------------------------------------------- 文本宽度预算
function charWidthInch(ch, pt) {
  const c = ch.codePointAt(0);
  if (c >= 0x2e80) return pt / 72;                       // CJK/全角 ≈ 1em
  if (ch === " ") return (pt * 0.3) / 72;
  if (/[0-9A-Za-z]/.test(ch)) return (pt * 0.56) / 72;
  if (".,;:!?()'".includes(ch)) return (pt * 0.33) / 72;
  if ("··-—".includes(ch)) return (pt * 0.5) / 72;
  return (pt * 0.62) / 72;
}
function estLines(text, pt, wIn) {
  let total = 0;
  for (const seg of String(text).split("\n")) {
    if (seg === "") { total += 1; continue; }
    let curW = 0;
    let lines = 1;
    for (const ch of seg) {
      const cw = charWidthInch(ch, pt);
      if (curW + cw > wIn) { lines += 1; curW = cw; } else curW += cw;
    }
    total += lines;
  }
  return total;
}
function fitSize(text, pt, wIn, hIn, label, lineScale = 1.32, minPt = 8.5) {
  let size = pt;
  while (size > minPt) {
    const lines = estLines(text, size, wIn);
    if (lines * ((size * lineScale) / 72) <= hIn + 0.02) break;
    size -= 0.5;
  }
  const lines = estLines(text, size, wIn);
  const needH = lines * ((size * lineScale) / 72);
  if (needH > hIn + 0.02) {
    console.warn(`⚠ FIT FAIL ${label}: 需要 ${needH.toFixed(2)}in > 盒子 ${hIn}in @${size}pt`);
  } else if (size < pt - 0.01) {
    console.warn(`⚠ FIT SHRUNK ${label}: ${pt}→${size}pt（${lines} 行）`);
  }
  return size;
}

// ---------------------------------------------------------------- 工具
function freshShadow() {
  return { type: "outer", color: "D5DEE9", blur: 10, angle: 45, offset: 3, opacity: 0.45 };
}
function card(slide, x, y, w, h, fill = WHITE, radius = 0.1) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    fill: { color: fill },
    line: { color: LINE, width: 1 },
    rectRadius: radius,
    shadow: freshShadow(),
  });
}
function solidRect(slide, x, y, w, h, color, radius = 0) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    fill: { color },
    line: { type: "none" },
    rectRadius: radius,
  });
}
function fillOpt(fill) {
  if (fill === "transparent") return { color: WHITE, transparency: 100 };
  return { color: fill };
}
function iconCircle(slide, x, y, d, name, fill = NAVY) {
  slide.addShape(pptx.ShapeType.ellipse, {
    x, y, w: d, h: d,
    fill: { color: fill },
    line: { type: "none" },
    shadow: freshShadow(),
  });
  const pad = d * 0.27;
  slide.addImage({ data: iconData(name), x: x + pad, y: y + pad, w: d - pad * 2, h: d - pad * 2 });
}
function addText(slide, text, opts) {
  const { label, boxW, boxH, pt, minPt = 8.5, lineScale = 1.32, ...rest } = opts;
  let size = pt;
  if (boxW && boxH) size = fitSize(text, pt, boxW, boxH, label || text.slice(0, 12), lineScale, minPt);
  slide.addText(text, {
    fontSize: size,
    fontFace: CJK_FONT,
    lineSpacing: Math.round(size * lineScale),
    margin: 0,
    ...rest,
  });
  return size;
}
function kicker(slide, num, text) {
  addText(slide, `${num} · ${text}`, {
    x: M, y: 0.42, w: 9, h: 0.34,
    pt: 12.5, bold: true, color: GREEN, charSpacing: 1,
    label: `kicker-${num}`,
  });
}
function slideTitle(slide, text) {
  addText(slide, text, {
    x: M, y: 0.72, w: 12.2, h: 0.72,
    pt: 33, bold: true, color: NAVY, charSpacing: 0,
    label: `title-${text.slice(0, 8)}`,
  });
}
function lightSlide(pptx, index, total) {
  const slide = pptx.addSlide();
  slide.background = { color: BG };
  // 页脚：左下系统名 + 右下页码（小字，非色条）
  addText(slide, "数字化应急预案自动生成系统", {
    x: M, y: 7.08, w: 4.5, h: 0.3, pt: 9.5, color: MUTED, label: "footer",
  });
  addText(slide, `${String(index).padStart(2, "0")} / ${String(total).padStart(2, "0")}`, {
    x: 11.9, y: 7.08, w: 0.9, h: 0.3, pt: 9.5, color: MUTED, align: "right", label: "page",
  });
  return slide;
}

// ---------------------------------------------------------------- 幻灯片
function slideCover(pptx, total) {
  const s = pptx.addSlide();
  s.background = { color: NAVY_DEEP };

  // 背景层次：两个柔和大圆
  solidRect(s, -2.2, -2.2, 6.5, 6.5, NAVY, 0.5);
  solidRect(s, 11.2, 4.6, 5.0, 5.0, "1D334F", 0.5);
  solidRect(s, -1.6, 5.4, 3.2, 3.2, "1D334F", 0.5);

  addText(s, "面向企业安全管理人员的智能预案编制平台", {
    x: 0.9, y: 1.45, w: 11.5, h: 0.4, pt: 14, color: ICE, charSpacing: 2,
    label: "cover-kicker",
  });
  addText(s, "数字化应急预案自动生成系统", {
    x: 0.9, y: 2.0, w: 11.6, h: 1.1, pt: 44, bold: true, color: WHITE,
    label: "cover-title",
  });

  // 价值主张
  addText(s, "企业数据 · 国标模板 · AI 引擎", {
    x: 0.9, y: 3.35, w: 11.5, h: 0.45, pt: 17, bold: true, color: GREEN,
    label: "cover-slogan",
  });
  addText(s, "以 GB/T 29639-2020 为合规基础，自动生成综合应急预案、专项应急预案、现场处置方案，一键导出标准 Word 文档。", {
    x: 0.9, y: 3.95, w: 11.5, h: 0.75, pt: 15, color: "DDE7F3", lineScale: 1.4,
    label: "cover-desc",
  });

  // 三类预案 chips
  const chips = ["综合应急预案", "专项应急预案", "现场处置方案"];
  const cw = 2.45;
  const gap = 0.32;
  let cx = 0.9;
  chips.forEach((label, i) => {
    s.addShape(pptx.ShapeType.roundRect, {
      x: cx, y: 5.0, w: cw, h: 0.62,
      fill: fillOpt(i === 0 ? GREEN : "transparent"),
      line: { color: i === 0 ? GREEN : "7E93AD", width: 1.2 },
      rectRadius: 0.5,
    });
    addText(s, label, {
      x: cx, y: 5.02, w: cw, h: 0.58, pt: 13.5, bold: true,
      color: i === 0 ? WHITE : ICE, align: "center", valign: "middle",
      label: "cover-chip",
    });
    cx += cw + gap;
  });

  addText(s, "数据驱动 · 合规约束 · 智能生成", {
    x: 0.9, y: 6.25, w: 11.5, h: 0.35, pt: 12, color: "8FA6C0", charSpacing: 1,
    label: "cover-foot",
  });
  s.addNotes(
    "开场：这是一套面向企业安全管理人员的智能预案编制平台。核心思路是：企业数据 + 国标模板 + AI 引擎，把过去需要数周的专业预案编制，压缩到填数据、点生成两步。系统覆盖综合、专项、现场处置三类预案，并支持一键导出标准 Word 文档。"
  );
}

function slidePain(pptx, total) {
  const s = lightSlide(pptx, 2, total);
  kicker(s, "01", "行业现状");
  slideTitle(s, "传统预案编制，为什么又难又慢？");

  const items = [
    { icon: "clock", t: "编制周期长", d: "资料收集、专家撰写、多轮评审，一份预案动辄数周，年检修订更是反复投入" },
    { icon: "dollar", t: "专业门槛高", d: "依赖注册安全工程师的经验与法规积累，中小企业难以长期负担" },
    { icon: "file-text", t: "内容易脱节", d: "套用通用模板，与企业实际风险、资源、组织脱节，关键时刻难落地" },
    { icon: "alert", t: "合规有风险", d: "章节结构与风险辨识跟不上 GB/T 29639-2020、GB 6441-2025 最新要求" },
  ];
  const gap = 0.25;
  const w = (SW - 2 * M - 3 * gap) / 4;
  const y = 1.85;
  const h = 3.35;
  items.forEach((it, i) => {
    const x = M + i * (w + gap);
    card(s, x, y, w, h);
    iconCircle(s, x + 0.28, y + 0.28, 0.62, it.icon, i === 3 ? GREEN : NAVY);
    addText(s, it.t, {
      x: x + 0.28, y: y + 1.08, w: w - 0.56, h: 0.42, pt: 16.5, bold: true, color: NAVY,
      label: `pain-${i}-title`,
    });
    addText(s, it.d, {
      x: x + 0.28, y: y + 1.58, w: w - 0.56, h: 1.55, pt: 12, color: MUTED, lineScale: 1.42,
      label: `pain-${i}-desc`,
    });
  });

  addText(s, "一份可用、合规的应急预案，是安全管理的基本盘，也是事故应对的第一道防线。", {
    x: M, y: 5.65, w: 12.23, h: 0.4, pt: 13, italic: true, color: NAVY, align: "center",
    label: "pain-closing",
  });
  s.addNotes(
    "先讲痛点：传统预案编制周期长、依赖专家、内容容易和企业实际脱节，而且法规更新快，容易踩合规红线。对中小企业尤其明显——养不起专职安全专家，又必须满足监管要求。"
  );
}

function slidePosition(pptx, total) {
  const s = lightSlide(pptx, 3, total);
  kicker(s, "02", "解决方案");
  slideTitle(s, "把「编制预案」变成「填数据 + 点生成」");

  const left = [
    { icon: "database", t: "结构化企业数据", d: "企业信息、组织架构、风险源、应急资源一次录入，多份预案持续复用" },
    { icon: "book-open", t: "国标模板框架", d: "按 GB/T 29639-2020 预置三类预案章节结构，AI 生成与人工编辑双模式" },
    { icon: "cpu", t: "AI 生成引擎", d: "多模型适配、流式输出，生成时智能注入企业真实数据，内容不编造" },
  ];
  let ly = 1.8;
  left.forEach((it, i) => {
    const w = 7.35;
    const h = 1.55;
    card(s, M, ly, w, h);
    iconCircle(s, M + 0.28, ly + 0.45, 0.62, it.icon);
    addText(s, it.t, {
      x: M + 1.1, y: ly + 0.22, w: w - 1.4, h: 0.4, pt: 16, bold: true, color: NAVY,
      label: `pos-${i}-title`,
    });
    addText(s, it.d, {
      x: M + 1.1, y: ly + 0.68, w: w - 1.4, h: 0.7, pt: 11.5, color: MUTED, lineScale: 1.35,
      label: `pos-${i}-desc`,
    });
    ly += h + 0.25;
  });

  // 右侧统计面板
  const px = 8.25;
  const py = 1.8;
  const pw = 4.53;
  const ph = 5.05;
  solidRect(s, px, py, pw, ph, NAVY, 0.12);
  const stats = [
    ["3", "类预案自动生成"],
    ["27", "类事故风险辨识（GB 6441-2025）"],
    ["4", "种主流模型可配"],
    ["1", "键导出标准 Word"],
  ];
  let sy = py + 0.42;
  stats.forEach(([num, label], i) => {
    addText(s, num, {
      x: px + 0.42, y: sy, w: 1.7, h: 0.75, pt: 38, bold: true, color: GREEN, fontFace: LATIN_FONT,
      label: `stat-${i}-num`,
    });
    addText(s, label, {
      x: px + 0.42, y: sy + 0.7, w: pw - 0.84, h: 0.5, pt: 11.5, color: ICE,
      label: `stat-${i}-label`,
    });
    sy += 1.13;
  });

  s.addNotes(
    "方案一句话：把编制预案变成填数据加一键生成。左边三大支柱——结构化的企业数据、国标模板框架、AI 生成引擎。右边是硬指标：三类预案、GB 6441-2025 的 27 类事故风险辨识、四种主流大模型可选、一键导出标准 Word。"
  );
}

function slideFlow(pptx, total) {
  const s = lightSlide(pptx, 4, total);
  kicker(s, "03", "使用流程");
  slideTitle(s, "四步闭环，让预案真正用起来");

  const steps = [
    { icon: "edit-3", t: "数据录入", d: "企业基本信息、组织架构、风险源、应急资源，表单化采集" },
    { icon: "zap", t: "AI 生成", d: "按章节自动撰写与润色，支持单章生成与一键批量，流式呈现" },
    { icon: "check-circle", t: "人工精修", d: "富文本编辑器逐章核对，版本快照随时回滚" },
    { icon: "download", t: "标准导出", d: "按公文格式生成 .docx：封面、批准页、目录、正文、表格" },
  ];
  const w = 2.62;
  const gap = 0.14;
  const arrowW = 0.28;
  const y = 1.95;
  const h = 3.05;
  let x = M;
  steps.forEach((st, i) => {
    card(s, x, y, w, h);
    // 序号圆
    s.addShape(pptx.ShapeType.ellipse, {
      x: x + w / 2 - 0.36, y: y + 0.28, w: 0.72, h: 0.72,
      fill: { color: i === 1 ? GREEN : NAVY },
      line: { type: "none" },
    });
    addText(s, String(i + 1), {
      x: x + w / 2 - 0.36, y: y + 0.3, w: 0.72, h: 0.68, pt: 20, bold: true,
      color: WHITE, align: "center", valign: "middle", fontFace: LATIN_FONT,
      label: `flow-${i}-num`,
    });
    addText(s, st.t, {
      x: x + 0.2, y: y + 1.15, w: w - 0.4, h: 0.4, pt: 16, bold: true, color: NAVY, align: "center",
      label: `flow-${i}-title`,
    });
    addText(s, st.d, {
      x: x + 0.24, y: y + 1.62, w: w - 0.48, h: 1.3, pt: 11.5, color: MUTED, lineScale: 1.4,
      label: `flow-${i}-desc`,
    });
    if (i < 3) {
      const ax = x + w + gap;
      s.addShape(pptx.ShapeType.rightArrow, {
        x: ax, y: y + h / 2 - 0.2, w: arrowW, h: 0.4,
        fill: { color: "B9C8DA" },
        line: { type: "none" },
      });
    }
    x += w + gap + arrowW;
  });

  addText(s, "3 秒自动保存　·　必填章节校验　·　版本快照回滚　·　导出前预览", {
    x: M, y: 5.55, w: 12.23, h: 0.45, pt: 13, bold: true, color: GREEN, align: "center",
    label: "flow-chips",
  });
  s.addNotes(
    "使用流程是四步闭环：第一步录入企业数据，第二步 AI 按章节自动生成、可以流式查看，第三步在富文本编辑器里人工精修，第四步一键导出符合公文格式的 Word。全程有自动保存、必填校验和版本回滚兜底。"
  );
}

function slidePlans(pptx, total) {
  const s = lightSlide(pptx, 5, total);
  kicker(s, "04", "核心能力一");
  slideTitle(s, "一份系统，三类预案自动生成");

  const items = [
    {
      icon: "globe", t: "综合应急预案", d: "企业整体应急框架：总则、应急组织机构及职责、预警与响应、后期处置、应急保障",
      tag: "面向企业整体",
    },
    {
      icon: "target", t: "专项应急预案", d: "针对特定事故类型：适用范围、响应启动、处置措施、应急保障，与风险源自动联动",
      tag: "面向特定事故",
    },
    {
      icon: "clipboard", t: "现场处置方案", d: "一线操作卡片：事故风险描述、应急工作职责、应急处置步骤、注意事项",
      tag: "面向一线班组",
    },
  ];
  const gap = 0.28;
  const w = (SW - 2 * M - 2 * gap) / 3;
  const y = 1.9;
  const h = 3.45;
  items.forEach((it, i) => {
    const x = M + i * (w + gap);
    card(s, x, y, w, h);
    iconCircle(s, x + w / 2 - 0.35, y + 0.34, 0.7, it.icon, i === 1 ? GREEN : NAVY);
    addText(s, it.t, {
      x: x + 0.28, y: y + 1.22, w: w - 0.56, h: 0.45, pt: 18, bold: true, color: NAVY, align: "center",
      label: `plan-${i}-title`,
    });
    addText(s, it.tag, {
      x: x + 0.28, y: y + 1.66, w: w - 0.56, h: 0.3, pt: 10.5, bold: true, color: GREEN, align: "center",
      label: `plan-${i}-tag`,
    });
    addText(s, it.d, {
      x: x + 0.32, y: y + 2.05, w: w - 0.64, h: 1.25, pt: 12, color: MUTED, lineScale: 1.42,
      label: `plan-${i}-desc`,
    });
  });
  addText(s, "章节结构覆盖 GB/T 29639-2020 · 事故风险辨识对接 GB 6441-2025（27 类）", {
    x: M, y: 5.7, w: 12.23, h: 0.4, pt: 12.5, color: MUTED, align: "center",
    label: "plan-note",
  });
  s.addNotes(
    "三类预案：综合应急预案管企业整体框架，专项应急预案针对火灾、触电等特定事故类型，现场处置方案是一线班组能直接照做的操作卡片。三者章节结构都覆盖 GB/T 29639-2020，风险辨识对接 GB 6441-2025 的 27 类事故。"
  );
}

function slideAi(pptx, total) {
  const s = lightSlide(pptx, 6, total);
  kicker(s, "05", "核心能力二");
  slideTitle(s, "AI 生成引擎：专业、可控、可追溯");

  const items = [
    { icon: "grid", t: "多模型适配", d: "OpenAI、通义千问、文心一言、DeepSeek 统一接口，用户自配 Key，自由切换" },
    { icon: "zap", t: "流式输出", d: "章节内容边生成边呈现，支持单章生成与一键批量，可随时停止重新生成" },
    { icon: "link", t: "智能上下文注入", d: "自动带入企业数据与风险源信息，避免内容编造，保证预案与企业实际一致" },
    { icon: "pen-tool", t: "提示词可配置", d: "系统级与章节级两级提示词模板，GB/T 合规要点自动约束" },
  ];
  const gap = 0.28;
  const w = (SW - 2 * M - gap) / 2;
  const h = 2.15;
  const y0 = 1.9;
  items.forEach((it, i) => {
    const x = M + (i % 2) * (w + gap);
    const y = y0 + Math.floor(i / 2) * (h + gap);
    card(s, x, y, w, h);
    iconCircle(s, x + 0.3, y + 0.32, 0.62, it.icon, i % 2 === 0 ? NAVY : GREEN);
    addText(s, it.t, {
      x: x + 1.1, y: y + 0.34, w: w - 1.4, h: 0.45, pt: 17, bold: true, color: NAVY,
      label: `ai-${i}-title`,
    });
    addText(s, it.d, {
      x: x + 0.32, y: y + 1.08, w: w - 0.64, h: 0.85, pt: 12.5, color: MUTED, lineScale: 1.4,
      label: `ai-${i}-desc`,
    });
  });
  s.addNotes(
    "AI 引擎的四个关键词：一是多模型，OpenAI、通义千问、文心一言、DeepSeek 都能接，用户自己配 Key；二是流式输出，生成过程实时可见；三是智能注入企业数据，保证不编造；四是提示词两级可配置，把国标合规要点写进生成约束里。"
  );
}

function slideRisk(pptx, total) {
  const s = lightSlide(pptx, 7, total);
  kicker(s, "06", "核心能力三");
  slideTitle(s, "从预案编制，到风险管理完整闭环");

  const items = [
    { icon: "bar-chart-2", t: "风险评估报告", d: "AI 生成风险评估报告，风险等级矩阵可视化" },
    { icon: "layers", t: "应急资源调查", d: "应急资源需求-能力差距分析" },
    { icon: "search", t: "法规库智能引用", d: "法规条文精准匹配，编制依据可溯源" },
    { icon: "map", t: "风险分级管控", d: "风险树、四色图、管控清单闭环管理" },
    { icon: "bell", t: "风险告知卡", d: "岗位风险告知卡自动生成，AI 标志审查" },
    { icon: "check-square", t: "隐患管理", d: "隐患登记-整改-复查全流程闭环" },
  ];
  const gapX = 0.28;
  const gapY = 0.28;
  const w = (SW - 2 * M - 2 * gapX) / 3;
  const h = 2.05;
  const y0 = 1.9;
  items.forEach((it, i) => {
    const x = M + (i % 3) * (w + gapX);
    const y = y0 + Math.floor(i / 3) * (h + gapY);
    card(s, x, y, w, h);
    iconCircle(s, x + 0.28, y + 0.28, 0.56, it.icon, i % 3 === 1 ? GREEN : NAVY);
    addText(s, it.t, {
      x: x + 0.98, y: y + 0.3, w: w - 1.26, h: 0.4, pt: 14.5, bold: true, color: NAVY,
      label: `risk-${i}-title`,
    });
    addText(s, it.d, {
      x: x + 0.28, y: y + 1.02, w: w - 0.56, h: 0.85, pt: 11.5, color: MUTED, lineScale: 1.4,
      label: `risk-${i}-desc`,
    });
  });
  s.addNotes(
    "不止是预案生成，系统已经延伸到风险管理全链条：风险评估报告、应急资源调查、法规库智能引用、风险分级管控、风险告知卡加 AI 标志审查、隐患登记到复查的闭环。客户已有的数据都能在系统里持续沉淀和复用。"
  );
}

function slideExtend(pptx, total) {
  const s = lightSlide(pptx, 8, total);
  kicker(s, "07", "更多能力");
  slideTitle(s, "面向全员与全场景的能力延伸");

  const items = [
    { icon: "activity", t: "企业驾驶舱", d: "风险指数、待办事项、风险排行一屏总览，管理决策有据可依" },
    { icon: "smartphone", t: "移动端 PWA", d: "手机随时查看预案、风险与任务，支持离线访问" },
    { icon: "map-pin", t: "四色图 AI", d: "四色安全风险图智能生成，厂区风险一目了然" },
  ];
  const gap = 0.28;
  const w = (SW - 2 * M - 2 * gap) / 3;
  const y = 1.9;
  const h = 3.2;
  items.forEach((it, i) => {
    const x = M + i * (w + gap);
    card(s, x, y, w, h);
    iconCircle(s, x + w / 2 - 0.33, y + 0.38, 0.66, it.icon, i === 1 ? GREEN : NAVY);
    addText(s, it.t, {
      x: x + 0.28, y: y + 1.25, w: w - 0.56, h: 0.45, pt: 17.5, bold: true, color: NAVY, align: "center",
      label: `ext-${i}-title`,
    });
    addText(s, it.d, {
      x: x + 0.34, y: y + 1.82, w: w - 0.68, h: 1.1, pt: 12, color: MUTED, lineScale: 1.45, align: "center",
      label: `ext-${i}-desc`,
    });
  });
  addText(s, "Web 端 + 移动端，覆盖预案编制、评审与现场巡检全场景", {
    x: M, y: 5.55, w: 12.23, h: 0.4, pt: 12.5, color: MUTED, align: "center",
    label: "ext-note",
  });
  s.addNotes(
    "延伸能力：企业驾驶舱让管理层一屏看风险；移动端 PWA 不用装 App，现场巡检时手机就能看预案、报隐患，还支持离线；四色图 AI 把厂区风险分布自动画出来。"
  );
}

function slideCompliance(pptx, total) {
  const s = lightSlide(pptx, 9, total);
  kicker(s, "08", "信任保障");
  slideTitle(s, "合规有据，安全可控");

  const items = [
    { icon: "shield", t: "国标合规", d: "预案框架遵循 GB/T 29639-2020，事故风险辨识对接 GB 6441-2025 二十七类" },
    { icon: "file-text", t: "公文导出", d: "黑体标题、仿宋正文、28 磅行距，封面/批准页/目录/编号/表格齐备" },
    { icon: "lock", t: "数据安全", d: "行级数据隔离、JWT 双 Token、API Key AES-256 加密存储" },
    { icon: "server", t: "部署灵活", d: "Docker Compose 一键部署，支持企业私有化" },
  ];
  const gap = 0.25;
  const w = (SW - 2 * M - 3 * gap) / 4;
  const y = 1.9;
  const h = 3.3;
  items.forEach((it, i) => {
    const x = M + i * (w + gap);
    card(s, x, y, w, h, i === 0 ? GREEN_LIGHT : WHITE);
    iconCircle(s, x + 0.28, y + 0.3, 0.62, it.icon, i === 0 ? GREEN : NAVY);
    addText(s, it.t, {
      x: x + 0.28, y: y + 1.1, w: w - 0.56, h: 0.42, pt: 16, bold: true, color: NAVY,
      label: `comp-${i}-title`,
    });
    addText(s, it.d, {
      x: x + 0.28, y: y + 1.6, w: w - 0.56, h: 1.5, pt: 12, color: MUTED, lineScale: 1.42,
      label: `comp-${i}-desc`,
    });
  });
  s.addNotes(
    "信任保障四件事：第一，预案结构严格按 GB/T 29639-2020，风险辨识按 GB 6441-2025 的 27 类事故口径；第二，导出是标准公文格式；第三，数据按用户行级隔离，API Key 加密存储；第四，支持 Docker 一键部署和私有化。"
  );
}

function slideSummary(pptx, total) {
  const s = pptx.addSlide();
  s.background = { color: NAVY_DEEP };
  solidRect(s, 10.9, -1.8, 5.2, 5.2, NAVY, 0.5);
  solidRect(s, -2.0, 5.2, 4.0, 4.0, "1D334F", 0.5);

  addText(s, "09 · 总结", {
    x: 0.9, y: 0.95, w: 6, h: 0.35, pt: 12.5, bold: true, color: GREEN, charSpacing: 1,
    label: "sum-kicker",
  });
  addText(s, "让应急预案编制，快一步、稳一步", {
    x: 0.9, y: 1.35, w: 11.6, h: 0.95, pt: 38, bold: true, color: WHITE,
    label: "sum-title",
  });

  const values = [
    { icon: "shield", t: "合规有据", d: "国标框架 + 法规库引用，出处可溯源" },
    { icon: "zap", t: "生成高效", d: "数据一次录入，三类预案一键生成" },
    { icon: "check-circle", t: "落地可用", d: "专家精修 + 版本回滚，成果真正可执行" },
  ];
  const gap = 0.32;
  const w = (11.53 - 2 * gap) / 3;
  const y = 2.75;
  const h = 2.0;
  values.forEach((v, i) => {
    const x = 0.9 + i * (w + gap);
    s.addShape(pptx.ShapeType.roundRect, {
      x, y, w, h,
      fill: fillOpt("transparent"),
      line: { color: "7E93AD", width: 1.2 },
      rectRadius: 0.1,
    });
    iconCircle(s, x + w / 2 - 0.32, y + 0.32, 0.64, v.icon, i === 1 ? GREEN : "33507A");
    addText(s, v.t, {
      x, y: y + 1.08, w, h: 0.42, pt: 17, bold: true, color: WHITE, align: "center",
      label: `sum-${i}-title`,
    });
    addText(s, v.d, {
      x: x + 0.2, y: y + 1.52, w: w - 0.4, h: 0.4, pt: 10.5, color: ICE, align: "center",
      label: `sum-${i}-desc`,
    });
  });

  // CTA 按钮
  const ctas = [
    { t: "立即试用", fill: GREEN, line: GREEN, fg: WHITE },
    { t: "预约演示", fill: "transparent", line: "7E93AD", fg: ICE },
    { t: "咨询部署", fill: "transparent", line: "7E93AD", fg: ICE },
  ];
  const bw = 2.35;
  const bgap = 0.35;
  let bx = (SW - (3 * bw + 2 * bgap)) / 2;
  ctas.forEach((b, i) => {
    s.addShape(pptx.ShapeType.roundRect, {
      x: bx, y: 5.35, w: bw, h: 0.7,
      fill: fillOpt(b.fill),
      line: { color: b.line, width: 1.4 },
      rectRadius: 0.5,
    });
    addText(s, b.t, {
      x: bx, y: 5.38, w: bw, h: 0.64, pt: 15, bold: true, color: b.fg,
      align: "center", valign: "middle",
      label: `cta-${i}`,
    });
    bx += bw + bgap;
  });

  addText(s, "数字化应急预案自动生成系统", {
    x: 0.9, y: 6.5, w: 11.5, h: 0.35, pt: 11.5, color: "8FA6C0", align: "center",
    label: "sum-footer",
  });
  s.addNotes(
    "收尾：一句话总结——让预案编制快一步、稳一步。合规有据、生成高效、落地可用，三个价值对应客户最关心的三件事。欢迎现场试用或预约演示，也支持私有化部署咨询。谢谢。"
  );
}

// ---------------------------------------------------------------- 主流程
async function main() {
  const usedIcons = [
    "clock", "dollar", "file-text", "alert",
    "database", "book-open", "cpu",
    "edit-3", "zap", "check-circle", "download",
    "globe", "target", "clipboard",
    "grid", "link", "pen-tool",
    "bar-chart-2", "layers", "search", "map", "bell", "check-square",
    "activity", "smartphone", "map-pin",
    "shield", "lock", "server",
  ];
  await preloadIcons(usedIcons);

  pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "数字化应急预案自动生成系统";
  pptx.title = "数字化应急预案自动生成系统 - 系统介绍";

  const TOTAL = 10;
  slideCover(pptx, TOTAL);
  slidePain(pptx, TOTAL);
  slidePosition(pptx, TOTAL);
  slideFlow(pptx, TOTAL);
  slidePlans(pptx, TOTAL);
  slideAi(pptx, TOTAL);
  slideRisk(pptx, TOTAL);
  slideExtend(pptx, TOTAL);
  slideCompliance(pptx, TOTAL);
  slideSummary(pptx, TOTAL);

  await pptx.writeFile({ fileName: OUT });
  console.log(`已生成: ${OUT}`);
  console.log(`幻灯片数: ${TOTAL}`);
}

main().catch((err) => {
  console.error("生成失败:", err);
  process.exit(1);
});
