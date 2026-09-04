import { ReactNode } from "react";

/**
 * Shared primitives for the terminal design system.
 *
 * Colour carries exactly four meanings here — accent (healthy / selected /
 * headline), series (neutral quantity), warn (provisional or medium risk),
 * bad (high risk or failure). Anything else is neutral by construction.
 */

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <div className="label mb-2">{children}</div>;
}

/** Titled panel — header strip plus body. The dominant container in this system. */
export function Panel({
  title, meta, children, className = "", bodyClass = "",
}: {
  title: ReactNode; meta?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <div className={`panel ${className}`}>
      <div className="panel-head">
        <span>{title}</span>
        {meta && <span className="meta">{meta}</span>}
      </div>
      <div className={bodyClass || "panel-body"}>{children}</div>
    </div>
  );
}

/** A ten-segment meter. Reads at a glance without needing to parse the number. */
export function Meter({ value, tone = "accent" }: { value: number; tone?: Tone }) {
  const filled = Math.max(0, Math.min(10, Math.round(value * 10)));
  return (
    <div className="flex gap-0.5 mt-2" aria-hidden>
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} className={`flex-1 h-[9px] ${i < filled ? toneBg[tone] : "bg-track"}`} />
      ))}
    </div>
  );
}

export type Tone = "ink" | "accent" | "series" | "warn" | "bad" | "brand" | "good";

const toneText: Record<Tone, string> = {
  ink: "text-ink", accent: "text-brand", brand: "text-brand", good: "text-brand",
  series: "text-series", warn: "text-warn", bad: "text-bad",
};
const toneBg: Record<Tone, string> = {
  ink: "bg-ink", accent: "bg-brand", brand: "bg-brand", good: "bg-brand",
  series: "bg-series", warn: "bg-warn", bad: "bg-bad",
};

/** Headline figure with a label, an optional caption and an optional meter. */
export function Metric({
  label, value, sub, color = "ink", meter,
}: {
  label: string; value: ReactNode; sub?: string; color?: Tone; meter?: number;
}) {
  return (
    <div className="panel px-3 py-2.5 h-full">
      <div className="label">{label}</div>
      <div className={`text-[24px] leading-none mt-1.5 tracking-tightest tabular-nums ${toneText[color]}`}>
        {value}
      </div>
      {sub && <div className="text-[10.5px] text-muted mt-1.5">{sub}</div>}
      {typeof meter === "number" && <Meter value={meter} tone={color} />}
    </div>
  );
}

/** Square tag — these sit inside dense numeric tables, so no lozenges. */
export function Pill({ value, kind }: { value: ReactNode; kind: "good" | "warn" | "bad" }) {
  const map = { good: "tag-good", warn: "tag-warn", bad: "tag-bad" } as const;
  return <span className={`${map[kind]} tabular-nums`}>{value}</span>;
}

/**
 * Model provenance badge. Never hidden: a score from an untrained prior must
 * not look like a measured one.
 */
export function KindTag({ kind }: { kind: string }) {
  const k = kind.toLowerCase();
  const cls = k === "real" ? "kind-real" : k.startsWith("prov") ? "kind-prov" : "kind-na";
  return <span className={cls}>{kind}</span>;
}

export function scoreKind(v: number): "good" | "warn" | "bad" {
  return v >= 0.7 ? "good" : v >= 0.5 ? "warn" : "bad";
}
export function riskKind(v: number): "good" | "warn" | "bad" {
  return v < 0.2 ? "good" : v < 0.4 ? "warn" : "bad";
}

/** Labelled horizontal bar. `tone` defaults to the neutral quantitative series. */
export function BarRow({
  label, value, tone = "series",
}: {
  label: string; value: number; tone?: Tone;
}) {
  return (
    <div className="flex items-center gap-2.5 py-1">
      <span className="w-28 text-[11px] text-muted truncate">{label}</span>
      <span className="flex-1 h-[6px] bg-track overflow-hidden">
        <span
          className={`block h-full ${toneBg[tone]}`}
          style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}
        />
      </span>
      <span className="w-9 text-right text-[11px] tabular-nums text-cell">{value.toFixed(2)}</span>
    </div>
  );
}

export function Button({
  children, onClick, type = "button", variant = "primary", disabled, full,
}: {
  children: ReactNode; onClick?: () => void; type?: "button" | "submit";
  variant?: "primary" | "ghost"; disabled?: boolean; full?: boolean;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${variant === "primary" ? "btn-primary" : "btn-ghost"} ${full ? "w-full" : ""}`}
    >
      {children}
    </button>
  );
}
