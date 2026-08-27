interface Props {
  items: string[];
}

export default function CockpitTicker({ items }: Props) {
  const inner = (
    <>
      {items.map((it, i) => (
        <span key={i}>{renderItem(it)}</span>
      ))}
    </>
  );
  return (
    <div className="cp-ticker">
      <div>
        {inner}
        <span aria-hidden="true">{inner}</span>
      </div>
    </div>
  );
}

/** 把「标签 数字」拆成 标签(<b>数字</b>)，突出关键数值，提升扫读性。 */
function renderItem(it: string) {
  const m = it.match(/^(.*?)\s*([0-9.]+%?)$/);
  if (m) {
    return (
      <>
        {m[1]}
        <b>{m[2]}</b>
      </>
    );
  }
  return it;
}
