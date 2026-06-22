import { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <div className="font-display font-extrabold text-base mb-2">{children}</div>;
}

export function Metric({ label, value, sub, color = "ink" }: {
  label: string; value: ReactNode; sub?: string; color?: "ink" | "brand" | "good" | "warn" | "bad";
}) {
  const colorMap: Record<string, string> = {
    ink: "text-ink", brand: "text-brand", good: "text-good", warn: "text-warn", bad: "text-bad",
  };
  return (
    <div className="card !p-4 h-full">
      <div className="label">{label}</div>
      <div className={`font-display font-extrabold text-2xl leading-tight mt-0.5 ${colorMap[color]}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export function Pill({ value, kind }: { value: ReactNode; kind: "good" | "warn" | "bad" }) {
  const map = {
    good: "bg-brand/10 text-brand",
    warn: "bg-warn/15 text-[#9A6818]",
    bad: "bg-bad/15 text-bad",
  };
  return <span className={`pill ${map[kind]}`}>{value}</span>;
}

export function scoreKind(v: number): "good" | "warn" | "bad" {
  return v >= 0.7 ? "good" : v >= 0.5 ? "warn" : "bad";
}
export function riskKind(v: number): "good" | "warn" | "bad" {
  return v < 0.2 ? "good" : v < 0.4 ? "warn" : "bad";
}

export function BarRow({ label, value, color = "#7A33A6" }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2 my-1">
      <span className="w-28 text-xs text-muted font-semibold">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-bg overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, value * 100))}%`, background: color }} />
      </div>
      <span className="w-9 text-right text-xs font-bold">{value.toFixed(2)}</span>
    </div>
  );
}

export function Button({ children, onClick, type = "button", variant = "primary", disabled, full }: {
  children: ReactNode; onClick?: () => void; type?: "button" | "submit";
  variant?: "primary" | "ghost"; disabled?: boolean; full?: boolean;
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`${variant === "primary" ? "btn-primary" : "btn-ghost"} ${full ? "w-full" : ""}`}>
      {children}
    </button>
  );
}
