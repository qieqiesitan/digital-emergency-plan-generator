import { useNavigate } from "react-router-dom";

interface ModuleItem {
  key: string;
  label: string;
  en: string;
  to: (id: string) => string;
  hot?: boolean;
  icon: React.ReactNode;
}

const stroke = { fill: "none", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const MODULES: ModuleItem[] = [
  {
    key: "info", label: "基本信息", en: "ARCHIVE", to: (id) => `/enterprises/${id}/modules/info`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><rect x="3" y="4" width="14" height="17" rx="1.5" /><path d="M3 9l7-4 7 4M8 21v-4.5h4V21M7 13h.01M10 13h.01M13 13h.01M7 16.5h.01M10 16.5h.01" /></svg>,
  },
  {
    key: "org", label: "组织架构", en: "ORG", to: (id) => `/enterprises/${id}/org`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><circle cx="5.5" cy="6.5" r="2" /><circle cx="18.5" cy="6.5" r="2" /><circle cx="12" cy="17.5" r="2" /><path d="M7 8l4.2 7.4M17 8l-4.2 7.4M7.5 6.5h9" /></svg>,
  },
  {
    key: "geo", label: "周边环境", en: "GEO", to: (id) => `/enterprises/${id}/modules/surrounding`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="12" r="8" /><path d="M12 4.5c3.8 2.6 3.8 12.4 0 15M12 4.5c-3.8 2.6-3.8 12.4 0 15M4.5 12h15" /></svg>,
  },
  {
    key: "chem", label: "危险化学品", en: "CHEM", to: (id) => `/enterprises/${id}/modules/chemicals`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M10 2.5v5.1a2 2 0 0 1-.21.9L4.72 18.6a1 1 0 0 0 .9 1.4h12.76a1 1 0 0 0 .9-1.4l-5.07-10.1a2 2 0 0 1-.21-.9V2.5" /><path d="M8.5 2.5h7M7 15.5h10" /></svg>,
  },
  {
    key: "risk", label: "风险管控", en: "RISK", hot: true, to: (id) => `/enterprises/${id}/risk-management`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M12 2.8 19 5.6v4.9c0 4.5-3 8-7 10-4-2-7-5.5-7-10V5.6z" /><path d="M12 8.5v3.5M12 15.2h.01" /></svg>,
  },
  {
    key: "hazard", label: "隐患治理", en: "HAZARD", hot: true, to: (id) => `/enterprises/${id}/hazard`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><circle cx="11" cy="11" r="6.5" /><path d="M20.5 20.5 16 16M11 7.5v3.5M8 11h6" /></svg>,
  },
  {
    key: "rescue", label: "应急资源", en: "RESCUE", to: (id) => `/enterprises/${id}/modules/resources`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M3 6.5h12v8H3zM15 10h3.2L21 12.7V14.5h-6z" /><circle cx="7" cy="17.5" r="1.7" /><circle cx="17" cy="17.5" r="1.7" /></svg>,
  },
  {
    key: "assessment", label: "风险评估", en: "REPORT", to: (id) => `/enterprises/${id}/modules/assessment`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 19.5v-6M9.5 19.5V9.5M15 19.5v-8M20.5 19.5V5" /><path d="M3 19.5h18.5" /></svg>,
  },
  {
    key: "investigation", label: "资源调查", en: "SURVEY", to: (id) => `/enterprises/${id}/modules/investigation`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><rect x="5" y="3.5" width="14" height="17.5" rx="2" /><path d="M9 8.5h6M9 12.5h6M9 16.5h4M12 3.5v-1" /></svg>,
  },
  {
    key: "plan", label: "预案管理", en: "PLAN", to: (id) => `/enterprises/${id}/plans`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9.5 12h5M9.5 16h5" /></svg>,
  },
];

export default function ModuleNav({ enterpriseId }: { enterpriseId: string }) {
  const navigate = useNavigate();
  return (
    <div className="cp-nav">
      {MODULES.map((m) => (
        <div
          key={m.key}
          className={`it${m.hot ? " hot" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => navigate(m.to(enterpriseId))}
          onKeyDown={(e) => e.key === "Enter" && navigate(m.to(enterpriseId))}
        >
          {m.hot && <span className="badge" />}
          {m.icon}
          <span className="lb">{m.label}</span>
          <span className="sb">{m.en}</span>
        </div>
      ))}
    </div>
  );
}
