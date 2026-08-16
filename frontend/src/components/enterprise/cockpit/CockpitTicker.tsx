interface Props {
  items: string[];
}

export default function CockpitTicker({ items }: Props) {
  const inner = (
    <>
      {items.map((it, i) => (
        <span key={i}>{it}</span>
      ))}
    </>
  );
  return (
    <div className="cp-ticker">
      <div>
        {inner}
        {inner}
      </div>
    </div>
  );
}
