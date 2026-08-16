import { useNavigate, useParams, Outlet } from "react-router-dom";
import { Button } from "antd";
import ModuleSideNav, { type SideNavGroup } from "./ModuleSideNav";

interface Props {
  title: string;
  en?: string;
  groups?: (id: string) => SideNavGroup[];
}

export default function ModulePageShell({ title, en, groups }: Props) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const navGroups = groups?.(id ?? "");
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Button type="link" onClick={() => navigate(`/enterprises/${id}`)}>← 返回企业驾驶舱</Button>
          <span style={{ fontSize: 16, fontWeight: 700 }}>{title}</span>
          {en && <span style={{ fontSize: 9, color: "#8a94a6", letterSpacing: 2 }}>{en}</span>}
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        {navGroups && <ModuleSideNav groups={navGroups} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
