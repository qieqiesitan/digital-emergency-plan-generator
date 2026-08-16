import type { ActivityItem } from "@/types/cockpit";

function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function CockpitActivityPanel({ activities }: { activities: ActivityItem[] }) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">最近动态</div>
      <div className="cp-feed">
        {activities.length === 0 ? (
          <div className="cp-empty">暂无动态</div>
        ) : (
          activities.slice(0, 3).map((a, i) => (
            <div className="it" key={i}>
              <span className="dot" />
              <span><b>{a.actor}</b> {a.action}</span>
              <span className="tm">{formatTime(a.time)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
