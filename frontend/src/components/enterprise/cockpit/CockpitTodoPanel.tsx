import type { CockpitTodo } from "@/types/cockpit";

const PRIORITY_COLORS: Record<string, string> = { high: "#ff4d4f", medium: "#ff9f43", low: "#2f81f7" };

export default function CockpitTodoPanel({ todos }: { todos: CockpitTodo[] }) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">待办提醒 <b style={{ color: "#ff9f43" }}>{todos.length}</b></div>
      {todos.length === 0 ? (
        <div className="cp-empty">暂无待办事项</div>
      ) : (
        todos.map((t) => (
          <div className="cp-todo" key={t.title}>
            <span className="lv" style={{ background: PRIORITY_COLORS[t.priority] || "#2f81f7" }} />
            <div><b>{t.title}</b><span>{t.note}</span></div>
          </div>
        ))
      )}
    </div>
  );
}
