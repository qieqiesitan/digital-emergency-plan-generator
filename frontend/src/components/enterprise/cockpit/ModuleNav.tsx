import { useNavigate } from "react-router-dom";
import AppIcon from "@/components/common/AppIcon";

interface ModuleItem {
  key: string;
  label: string;
  en: string;
  to: (id: string) => string;
  hot?: boolean;
  icon: React.ReactNode;
}

const MODULES: ModuleItem[] = [
  {
    key: "info", label: "基本信息", en: "ARCHIVE", to: (id) => `/enterprises/${id}/modules/info`,
    icon: <AppIcon name="archive" size={24} />,
  },
  {
    key: "org", label: "组织架构", en: "ORG", to: (id) => `/enterprises/${id}/org`,
    icon: <AppIcon name="org" size={24} />,
  },
  {
    key: "geo", label: "周边环境", en: "GEO", to: (id) => `/enterprises/${id}/modules/surrounding`,
    icon: <AppIcon name="geo" size={24} />,
  },
  {
    key: "chem", label: "危险化学品", en: "CHEM", to: (id) => `/enterprises/${id}/modules/chemicals`,
    icon: <AppIcon name="chem" size={24} />,
  },
  {
    key: "risk", label: "风险管控", en: "RISK", hot: true, to: (id) => `/enterprises/${id}/risk-management`,
    icon: <AppIcon name="risk" size={24} />,
  },
  {
    key: "hazard", label: "隐患治理", en: "HAZARD", hot: true, to: (id) => `/enterprises/${id}/hazard`,
    icon: <AppIcon name="hazard" size={24} />,
  },
  {
    key: "rescue", label: "应急资源", en: "RESCUE", to: (id) => `/enterprises/${id}/modules/resources`,
    icon: <AppIcon name="rescue" size={24} />,
  },
  {
    key: "assessment", label: "风险评估报告", en: "REPORT", to: (id) => `/enterprises/${id}/modules/assessment`,
    icon: <AppIcon name="assessment" size={24} />,
  },
  {
    key: "investigation", label: "资源调查报告", en: "SURVEY", to: (id) => `/enterprises/${id}/modules/investigation`,
    icon: <AppIcon name="investigation" size={24} />,
  },
  {
    key: "plan", label: "预案管理", en: "PLAN", to: (id) => `/enterprises/${id}/plans`,
    icon: <AppIcon name="plan-manage" size={24} />,
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
