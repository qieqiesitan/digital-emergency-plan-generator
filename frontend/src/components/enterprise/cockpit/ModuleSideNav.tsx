import { useLocation, useNavigate } from "react-router-dom";

export interface SideNavItem {
  key: string;
  label: string;
  to: string;
  matchSearch?: string;
  inactiveWhenSearch?: string;
}

export interface SideNavGroup {
  label: string;
  items: SideNavItem[];
}

export default function ModuleSideNav({ groups }: { groups: SideNavGroup[] }) {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <div
      style={{
        width: 170, flexShrink: 0, background: "#fff", border: "1px solid #e5e9f0",
        borderRadius: 8, padding: "8px 0", alignSelf: "flex-start",
      }}
    >
      {groups.map((g) => (
        <div key={g.label}>
          <div style={{ fontSize: 10, color: "#9aa4b4", padding: "8px 12px 3px", letterSpacing: 1 }}>{g.label}</div>
          {g.items.map((it) => {
            const active = it.matchSearch
              ? location.pathname === it.to.split("?")[0] && location.search.includes(it.matchSearch)
              : location.pathname === it.to && !(it.inactiveWhenSearch && location.search.includes(it.inactiveWhenSearch));
            return (
              <div
                key={it.key}
                role="button"
                tabIndex={0}
                onClick={() => navigate(it.to)}
                onKeyDown={(e) => e.key === "Enter" && navigate(it.to)}
                style={{
                  fontSize: 12, padding: "7px 12px", cursor: "pointer",
                  color: active ? "#1677ff" : "#5a6a80",
                  background: active ? "#e6f0ff" : "transparent",
                  borderRight: active ? "2px solid #1677ff" : "2px solid transparent",
                  fontWeight: active ? 600 : 400,
                }}
              >
                {it.label}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
