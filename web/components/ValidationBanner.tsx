"use client";
/**
 * Site-wide scientific-honesty notice (Task E/J).
 *
 * Deliberately not a dismissible banner and not decorative: scoring components
 * are interpretable heuristics, off-target is a motif scan with no genome
 * alignment, and nothing here has been validated at the bench. It reads as a
 * terminal warning line so it belongs to the interface rather than interrupting it.
 */
export function ValidationBanner() {
  return (
    <div className="flex-none flex items-start gap-2 border-b border-border bg-warn/[0.06] px-3 py-1.5 text-[10.5px] leading-relaxed text-warn">
      <span aria-hidden className="font-semibold">!</span>
      <span>
        research use — computational predictions only. scores are interpretable heuristics
        (named models where available); off-target is a motif scan with no genome alignment.
        results are <b className="font-semibold">not clinical</b> and{" "}
        <b className="font-semibold">require experimental validation</b>.
      </span>
    </div>
  );
}
