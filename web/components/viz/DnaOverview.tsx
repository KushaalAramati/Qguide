"use client";
// Linear scale representation of the full sequence with guide + PAM markers.
export function DnaOverview({ seqLength, guides, selectedId, onSelect }: {
  seqLength: number; guides: any[]; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const W = 1000, H = 86, pad = 24;
  const x = (p: number) => pad + (p / Math.max(1, seqLength)) * (W - 2 * pad);
  const axisY = 54;

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="select-none">
        {/* axis */}
        <line x1={pad} y1={axisY} x2={W - pad} y2={axisY} stroke="#D3C2E6" strokeWidth={2} />
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line x1={x(seqLength * f)} y1={axisY - 4} x2={x(seqLength * f)} y2={axisY + 4} stroke="#B9A4D1" />
            <text x={x(seqLength * f)} y={axisY + 18} fontSize="10" fill="#6E5B7B" textAnchor="middle">{Math.round(seqLength * f)}</text>
          </g>
        ))}
        {/* guide markers */}
        {guides.map((g) => {
          const sel = g.guide_id === selectedId;
          const strand = typeof g.strand === "string" ? g.strand : g.strand?.value || "+";
          const cx = x((g.position + (g.end ?? g.position + g.sequence.length)) / 2);
          const y = strand === "+" ? axisY - 16 : axisY + 16;
          return (
            <g key={g.guide_id} onClick={() => onSelect(g.guide_id)} style={{ cursor: "pointer" }}>
              {/* protospacer span */}
              <line x1={x(g.position)} x2={x(g.end ?? g.position + g.sequence.length)} y1={axisY} y2={axisY}
                stroke={sel ? "#7A33A6" : "#C49AE0"} strokeWidth={sel ? 6 : 3} opacity={sel ? 1 : 0.7} />
              <circle cx={cx} cy={y} r={sel ? 6 : 4} fill={sel ? "#7A33A6" : "#A569BD"} stroke="#fff" strokeWidth={1} />
              {sel && <text x={cx} y={y < axisY ? y - 8 : y + 14} fontSize="10" fontWeight="700" fill="#7A33A6" textAnchor="middle">{g.guide_id}</text>}
            </g>
          );
        })}
        <text x={pad} y={16} fontSize="11" fontWeight="700" fill="#2C1A3D">Sequence map · {seqLength} bp · {guides.length} guides</text>
      </svg>
    </div>
  );
}
