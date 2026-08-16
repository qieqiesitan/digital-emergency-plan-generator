import type { CockpitCompletion } from "@/types/cockpit";

export default function CockpitCompletionPanel({ completion }: { completion: CockpitCompletion }) {
  const percent = completion.percent ?? 0;
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">数据完成度</div>
      <div className="cp-ringwrap">
        <div className="cp-ring" style={{ background: `conic-gradient(#00d4ff 0 ${percent}%, rgba(255,255,255,.07) ${percent}% 100%)` }}>
          <b>{percent > 0 ? `${percent}%` : "--"}</b>
        </div>
        <div className="cp-modules">
          {completion.modules.length === 0 ? (
            <div className="cp-empty">暂无数据</div>
          ) : (
            completion.modules.map((m) => (
              <div className="cp-mod" key={m.key}>
                {m.label}
                {m.done ? <b>✓</b> : <b className="warn">…</b>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
