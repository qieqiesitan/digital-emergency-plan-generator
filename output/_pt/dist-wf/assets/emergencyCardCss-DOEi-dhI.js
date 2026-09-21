import{f as o}from"./react-BfvYI6Yh.js";async function d(e){return(await o.get(`/plans/${e}/export/preview`)).data.data}async function s(e){const r=await o.post(`/plans/${e}/export/docx`,{},{responseType:"blob",timeout:12e4,skipGlobalError:!0}),t=String(r.headers["content-type"]||"");if(t.includes("application/vnd.openxmlformats")||t.includes("application/octet-stream"))return r.data;const c=await r.data.text();try{const a=JSON.parse(c);throw new Error(a.detail||a.message||"Server error: "+c.slice(0,200))}catch(a){throw a instanceof Error&&!a.message.startsWith("Server error:")?a:new Error("Server error: "+c.slice(0,200),{cause:a})}}async function i(e){return(await o.post(`/plans/${e}/export/validate`)).data.data}async function f(e){return(await o.get(`/export/tasks/${e}`)).data.data}function p(e){const r=typeof localStorage<"u"&&localStorage.getItem("access_token")||"",t=r?`?token=${encodeURIComponent(r)}`:"";return`/api/v1/export/download/${e}${t}`}const l=`
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
`;export{l as E,f as a,p as b,s as e,d as g,i as v};
