"use client";
// Site-wide scientific-honesty banner (Task E/J). Predictions are computational and
// must be validated at the bench; several components are heuristic/provisional.
export function ValidationBanner() {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-[12px] text-ink">
      <span className="text-warn font-bold leading-none mt-0.5">⚠</span>
      <span>
        <b>Research use — computational predictions only.</b> Scores are interpretable heuristics
        (with named models where available); off-target is heuristic (no genome alignment yet).
        Results are <b>not clinical</b> and <b>require experimental validation</b>.
      </span>
    </div>
  );
}
