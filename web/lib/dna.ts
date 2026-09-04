// DNA/RNA constants + helpers for the visualizers.

// RNA (guide) base colors — spec: A green, U yellow, C blue, G red
export const RNA_COLORS: Record<string, string> = {
  A: "#22c55e", U: "#eab308", C: "#3b82f6", G: "#ef4444", N: "#9ca3af",
};
// DNA base colors — spec: A green, T orange, C blue, G red
export const DNA_COLORS: Record<string, string> = {
  A: "#22c55e", T: "#f59e0b", C: "#3b82f6", G: "#ef4444", N: "#9ca3af",
};

export const BASE_NAME: Record<string, string> = {
  A: "Adenine", U: "Uracil", T: "Thymine", C: "Cytosine", G: "Guanine", N: "Unknown",
};

export const DNA_COMPLEMENT: Record<string, string> = {
  A: "T", T: "A", C: "G", G: "C", N: "N",
};

export function cleanSeq(s: string): string {
  return (s || "").replace(/[^ACGTNacgtn]/g, "").toUpperCase();
}

export function complementStrand(s: string): string {
  return s.split("").map((b) => DNA_COMPLEMENT[b] || "N").join("");
}

// A windowed view of the full DNA around a guide, with highlight indices.
export interface DnaWindow {
  seq: string;          // windowed DNA (top strand, 5'->3')
  windowStart: number;  // index in the full sequence where the window begins
  guideStart: number;   // index within `seq` where the protospacer starts
  guideEnd: number;     // exclusive
  pamStart: number;     // index within `seq` (or -1)
  pamEnd: number;
}

export function buildDnaWindow(
  fullSeq: string,
  guide: any,
  flank = 14,
  maxLen = 54,
): DnaWindow {
  const seqLen = fullSeq.length;
  const pos = guide.position;
  const end = guide.end ?? guide.position + guide.sequence.length;
  const pamLen = (guide.pam || "NGG").length;
  const strand =
    typeof guide.strand === "string" ? guide.strand : guide.strand?.value || "+";

  let winStart = Math.max(0, pos - flank);
  let winEnd = Math.min(seqLen, end + flank);
  if (winEnd - winStart > maxLen) winEnd = winStart + maxLen;

  const seq = fullSeq.slice(winStart, winEnd);
  const guideStart = pos - winStart;
  const guideEnd = end - winStart;

  // PAM: 3' of protospacer for Cas9 (+ strand -> after end; - strand -> before pos)
  let pamStart = -1;
  let pamEnd = -1;
  if (strand === "+") {
    pamStart = guideEnd;
    pamEnd = guideEnd + pamLen;
  } else {
    pamStart = guideStart - pamLen;
    pamEnd = guideStart;
  }
  return { seq, windowStart: winStart, guideStart, guideEnd, pamStart, pamEnd };
}
