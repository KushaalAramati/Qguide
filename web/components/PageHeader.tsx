import { ReactNode } from "react";

/**
 * Page header — answers "what page am I on, what does it do, what should I do
 * next" in one strip. `primary` is the single most important action on the
 * page; everything else goes in `actions` as ghost buttons.
 */
export function PageHeader({
  title, description, eyebrow, primary, actions, children,
}: {
  title: ReactNode; description?: ReactNode; eyebrow?: ReactNode;
  primary?: ReactNode; actions?: ReactNode; children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 pb-3 mb-1 border-b border-border">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          {eyebrow && <div className="label mb-1">{eyebrow}</div>}
          <h1 className="text-[20px] leading-tight font-medium text-title tracking-tightest">{title}</h1>
          {description && <p className="text-[12px] text-muted mt-1 max-w-2xl">{description}</p>}
        </div>
        {(primary || actions) && (
          <div className="flex items-center gap-2 flex-wrap">
            {actions}
            {primary}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

/** Horizontal tab strip used for in-page sections. */
export function Tabs<T extends string>({
  items, value, onChange,
}: { items: readonly T[] | T[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex border-b border-border overflow-x-auto" role="tablist">
      {items.map((t) => (
        <button
          key={t}
          role="tab"
          aria-selected={value === t}
          onClick={() => onChange(t)}
          className={`px-3 py-2 text-[11.5px] whitespace-nowrap border-b-2 -mb-px transition-colors ${
            value === t ? "text-brand border-brand bg-brand/[0.05]" : "text-faint border-transparent hover:text-ink"
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

/** Empty state — never leave a blank panel. */
export function EmptyState({
  title, body, action,
}: { title: ReactNode; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="py-8 px-4 text-center">
      <div className="text-[12.5px] text-ink">{title}</div>
      {body && <div className="text-[11.5px] text-muted mt-1 max-w-md mx-auto">{body}</div>}
      {action && <div className="mt-3 flex justify-center">{action}</div>}
    </div>
  );
}

export function LoadingRows({ n = 4 }: { n?: number }) {
  return (
    <div className="flex flex-col gap-2 p-3" aria-busy>
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="h-3 bg-track animate-pulse" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div role="alert" className="border border-bad/40 bg-bad/[0.06] text-bad text-[11.5px] px-3 py-2 flex items-center gap-3">
      <span className="flex-1">{message}</span>
      {retry && <button onClick={retry} className="btn-ghost !py-0.5 !px-2 !text-[11px]">retry</button>}
    </div>
  );
}
