const PARTICLES = [
  { left: "6%", bottom: 150, duration: 8, delay: 0 },
  { left: "18%", bottom: 90, duration: 10, delay: 1.2 },
  { left: "31%", bottom: 170, duration: 7, delay: 2 },
  { left: "47%", bottom: 110, duration: 9, delay: 0.6 },
  { left: "63%", bottom: 160, duration: 8.4, delay: 1.8 },
  { left: "78%", bottom: 100, duration: 7.6, delay: 0.9 },
  { left: "92%", bottom: 180, duration: 9.6, delay: 2.6 },
];

export default function CockpitBackground() {
  return (
    <div className="cp-bg" aria-hidden>
      <div className="grid" />
      <div className="aurora" />
      <div className="aurora2" />
      <div className="floor" />
      <div className="scan" />
      <div className="stream" style={{ left: 10 }} />
      <div className="stream" style={{ right: 10, animationDelay: "0.7s" }} />
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          className="part"
          style={{ left: p.left, bottom: p.bottom, animationDuration: `${p.duration}s`, animationDelay: `${p.delay}s` }}
        />
      ))}
    </div>
  );
}
