/**
 * 现场处置方案「应急处置卡」系列章节的卡片化预览样式。
 * 与后端 export.py PREVIEW_CSS 中的 .emergency-card* 规则保持一致；
 * 预览页需在本地注入（后端 preview.html 内的 <style> 在 React 容器中不可靠）。
 */
export const EMERGENCY_CARD_CSS = `
.emergency-card-section { margin: 16px 0; display: grid; gap: 14px; }
.emergency-card {
  border: 1px solid #e8e8e8; border-radius: 10px; padding: 14px 18px;
  background: #fff; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  break-inside: avoid; page-break-inside: avoid;
}
.emergency-card h3 {
  margin: 0 0 8px; font-size: 15px; font-weight: 700;
  padding-left: 10px; border-left: 4px solid #d9d9d9;
}
.emergency-card ol, .emergency-card ul { margin-bottom: 0; }
.emergency-card li { margin-bottom: 6px; }
.emergency-card[data-theme="danger"] { background: #fff7f7; border-color: #ffccc7; }
.emergency-card[data-theme="danger"] h3 { border-left-color: #ff4d4f; }
.emergency-card[data-theme="action"] { background: #fffdf6; border-color: #ffe7ba; }
.emergency-card[data-theme="action"] h3 { border-left-color: #fa8c16; }
.emergency-card[data-theme="info"] { background: #f6faff; border-color: #bae0ff; }
.emergency-card[data-theme="info"] h3 { border-left-color: #1677ff; }
.emergency-card[data-theme="contact"] { background: #f9fff6; border-color: #d9f7be; }
.emergency-card[data-theme="contact"] h3 { border-left-color: #52c41a; }
.emergency-card[data-theme="default"] h3 { border-left-color: #8c8c8c; }
`;
