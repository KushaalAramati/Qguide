// Clean vector DNA double helix (two sine strands + base-pair rungs).
export function Dna({ width = 1000, height = 64, turns = 6, s1 = "#7A33A6", s2 = "#C49AE0", opacity = 0.9 }:
  { width?: number; height?: number; turns?: number; s1?: string; s2?: string; opacity?: number }) {
  const n = 160;
  const amp = height * 0.3;
  const mid = height / 2;
  const A: [number, number][] = [];
  const B: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const x = (width * i) / n;
    const ph = (turns * 2 * Math.PI * i) / n;
    A.push([x, mid + amp * Math.sin(ph)]);
    B.push([x, mid + amp * Math.sin(ph + Math.PI)]);
  }
  const pa = A.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const pb = B.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const rungs = [];
  for (let i = 0; i <= n; i += 7) {
    const [xa, ya] = A[i];
    const [xb, yb] = B[i];
    const c = (Math.floor(i / 7) % 2 === 0) ? s1 : s2;
    rungs.push(<line key={i} x1={xa} y1={ya} x2={xb} y2={yb} stroke={c} strokeWidth={2} opacity={0.4} />);
    rungs.push(<circle key={`a${i}`} cx={xa} cy={ya} r={2.6} fill={s1} />);
    rungs.push(<circle key={`b${i}`} cx={xb} cy={yb} r={2.6} fill={s2} />);
  }
  return (
    <div style={{ opacity, lineHeight: 0 }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} xmlns="http://www.w3.org/2000/svg">
        <polyline points={pa} fill="none" stroke={s1} strokeWidth={3} strokeLinecap="round" />
        <polyline points={pb} fill="none" stroke={s2} strokeWidth={3} strokeLinecap="round" />
        {rungs}
      </svg>
    </div>
  );
}
