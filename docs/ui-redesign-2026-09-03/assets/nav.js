/* 页面导航 + antd 风格线性图标库（禁止 emoji 的替代方案） */
(function(){
  /* ---------- 图标 sprite ---------- */
  var P = {
    'home':'<path d="M3 11.2 12 3.5l9 7.7V21h-6.5v-5.5h-5V21H3z"/>',
    'build':'<path d="M4 21h16M6.5 21V7.5L12 3.5l5.5 4V21M10 21v-4.5h4V21"/>',
    'file':'<path d="M7 2.5h7l4.5 4.5v14H7z M14 2.5V7h4.5 M10 12h5 M10 16h5"/>',
    'filedone':'<path d="M7 2.5h7l4.5 4.5v14H7z M14 2.5V7h4.5 M9.8 13.8l2 2 3.4-3.6"/>',
    'set':'<path d="M4 7.5h9 M17.5 7.5H20 M4 16.5h3 M11.5 16.5H20"/><circle cx="15" cy="7.5" r="2.3"/><circle cx="9" cy="16.5" r="2.3"/>',
    'user':'<circle cx="12" cy="8" r="4"/><path d="M4.5 21c.5-4 3.5-6.2 7.5-6.2s7 2.2 7.5 6.2"/>',
    'search':'<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    'plus':'<path d="M12 5v14M5 12h14"/>',
    'down':'<path d="M6 9.5l6 6 6-6"/>',
    'up':'<path d="M6 14.5l6-6 6 6"/>',
    'left':'<path d="M15 5.5 8.5 12l6.5 6.5"/>',
    'right':'<path d="M9 5.5 15.5 12 9 18.5"/>',
    'edit':'<path d="M4 20h4.5L20 8.5 15.5 4 4 15.5z M13.5 6l4.5 4.5"/>',
    'del':'<path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l1 13.5h9l1-13.5M10 11v6M14 11v6"/>',
    'download':'<path d="M12 3.5v11M6.5 9.5 12 15l5.5-5.5M4 20.5h16"/>',
    'upload':'<path d="M12 15V4M6.5 9 12 3.5 17.5 9M4 20.5h16"/>',
    'save':'<path d="M5 4h11l4 4v12H5z M8 4v6h8V4 M8 20v-6h8v6"/>',
    'export':'<path d="M4 13.5V20h16v-6.5 M12 3.5V14 M7.5 10 12 14.5 16.5 10"/>',
    'ai':'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
    'alert':'<path d="M12 3.5 21.5 20.5h-19z M12 10v4.5 M12 17.2v.6"/>',
    'check':'<path d="M4.5 12.5l5 5L19.5 7"/>',
    'close':'<path d="M6 6l12 12M18 6 6 18"/>',
    'refresh':'<path d="M20 12a8 8 0 1 1-2.3-5.6M20.5 3.5v5h-5"/>',
    'eye':'<path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"/><circle cx="12" cy="12" r="2.8"/>',
    'link':'<path d="M9.5 14.5 14.5 9.5 M8 16l-1.5 1.5a3.5 3.5 0 0 1-5-5L5 9 M16 8l1.5-1.5a3.5 3.5 0 0 1 5 5L19 15"/>',
    'copy':'<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4V3h12v1"/>',
    'pin':'<path d="M12 21.5s7-6.2 7-11.5a7 7 0 1 0-14 0c0 5.3 7 11.5 7 11.5z"/><circle cx="12" cy="10" r="2.6"/>',
    'clock':'<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.3l3.2 3"/>',
    'chart':'<path d="M4 20h16 M7.5 20v-6 M12 20V6.5 M16.5 20v-9"/>',
    'pie':'<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5V12l8 2.6"/>',
    'grid':'<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    'list':'<path d="M8.5 6H21M8.5 12H21M8.5 18H21"/><circle cx="4.3" cy="6" r="1" fill="currentColor"/><circle cx="4.3" cy="12" r="1" fill="currentColor"/><circle cx="4.3" cy="18" r="1" fill="currentColor"/>',
    'stop':'<rect x="6" y="6" width="12" height="12" rx="2"/>',
    'shield':'<path d="M12 3l8 3v6c0 4.8-3.4 7.9-8 9-4.6-1.1-8-4.2-8-9V6z"/><path d="M8.8 12l2.2 2.2 4.2-4.4"/>',
    'fire':'<path d="M12 3c1.2 3.2-2.5 4.4-2.5 7.4a2.5 2.5 0 0 0 5 0C14.5 8 17 7 17 4.5c1.6 1.9 2.5 4.3 2.5 6.8a7.5 7.5 0 1 1-15 0C4.5 7 8.5 5.5 12 3z"/>',
    'drop':'<path d="M12 3s6.2 7 6.2 11.2a6.2 6.2 0 0 1-12.4 0C5.8 10 12 3 12 3z"/>',
    'box':'<path d="M3.5 8 12 3.5 20.5 8v8L12 20.5 3.5 16z M3.5 8 12 12.5 20.5 8 M12 12.5v8"/>',
    'org':'<rect x="9" y="3" width="6" height="4.5" rx="1"/><rect x="2.5" y="16.5" width="6" height="4.5" rx="1"/><rect x="15.5" y="16.5" width="6" height="4.5" rx="1"/><path d="M12 7.5v4.5M5.5 16.5v-3h13v3"/>',
    'book':'<path d="M4.5 4h11a3 3 0 0 1 3 3v13h-14z M4.5 17h14"/>',
    'send':'<path d="M21.5 2.5 11 13M21.5 2.5l-7 19-3.5-9-9-3.5z"/>',
    'thunder':'<path d="M13 2 4.5 14h6l-1 8 9-12h-6z"/>',
    'image':'<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.6"/><path d="M21 15.5 16 10.5l-8 8.5"/>',
    'calendar':'<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    'lock':'<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    'expand':'<path d="M15 3.5h5.5V9M21.5 3.5 14.5 10.5M9 20.5H3.5V15M3.5 20.5l7-7"/>',
    'filter':'<path d="M3.5 5h17l-7 8v6l-3-1.8v-4.2z"/>',
    'bell':'<path d="M6 9.5a6 6 0 0 1 12 0c0 5 2 6.5 2 6.5H4s2-1.5 2-6.5z M10 19a2 2 0 0 0 4 0"/>',
    'rollback':'<path d="M9 14 4 9l5-5 M4 9h10a6 6 0 0 1 0 12h-3"/>',
    'print':'<path d="M7 8V3.5h10V8 M7 17H4.5V9a1.5 1.5 0 0 1 1.5-1.5h12A1.5 1.5 0 0 1 19.5 9v8H17 M7 13.5h10v7H7z"/>',
    'scan':'<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M4 12h16"/>'
  };
  var svg = '<svg style="display:none" xmlns="http://www.w3.org/2000/svg">'
    + Object.keys(P).map(function(k){return '<symbol id="i-'+k+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+P[k]+'</symbol>';}).join('')
    + '</svg>';
  document.write(svg);

  /* ---------- 底部页导航 ---------- */
  var pages = [
    ['01-login.html','01 登录'],
    ['02-dashboard.html','02 工作台'],
    ['03-enterprise-list.html','03 企业列表'],
    ['04-enterprise-form.html','04 新建企业'],
    ['05-cockpit.html','05 驾驶舱'],
    ['06-plans.html','06 预案总览'],
    ['07-plan-editor.html','07 预案编辑器'],
    ['08-export-preview.html','08 导出预览'],
    ['index.html','总览']
  ];
  var cur = location.pathname.split('/').pop() || 'index.html';
  window.addEventListener('DOMContentLoaded', function(){
    var nav = document.createElement('div');
    nav.style.cssText = 'position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:999;'
      +'background:rgba(17,24,39,.92);backdrop-filter:blur(6px);border-radius:12px;padding:8px 10px;'
      +'display:flex;gap:4px;box-shadow:0 12px 28px rgba(16,24,40,.25);max-width:96vw;flex-wrap:wrap;justify-content:center';
    pages.forEach(function(p){
      var a = document.createElement('a');
      a.href = p[0]; a.textContent = p[1];
      a.style.cssText = 'color:'+(p[0]===cur?'#fff':'#C7D0DD')+';font-size:12px;text-decoration:none;'
        +'padding:5px 10px;border-radius:7px;white-space:nowrap;font-family:Inter,PingFang SC,sans-serif';
      if(p[0]===cur) a.style.background = '#1D4ED8';
      else a.onmouseenter=function(){a.style.color='#fff'}; a.onmouseleave=function(){a.style.color='#C7D0DD'};
      nav.appendChild(a);
    });
    document.body.appendChild(nav);
  });
})();
