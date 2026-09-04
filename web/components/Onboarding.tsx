"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TOUR_STEPS } from "@/lib/tour";
import { LogoMark } from "@/components/Brand";

/**
 * First-time walkthrough.
 *
 * Shown automatically when the account's `onboarding.completed` flag is false —
 * i.e. exactly once per account, not once per browser. Progress (step) and
 * completion are persisted server-side so a user who closes the tab resumes
 * where they were, and "Replay tutorial" in Settings simply resets the flag.
 */
export function OnboardingTour() {
  const { account, setAccount } = useAuth();
  const ob = account?.onboarding;
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const total = TOUR_STEPS.length;

  useEffect(() => {
    if (!account || !ob) return;
    if (!ob.completed) {
      setStep(Math.min(ob.step || 0, total - 1));
      setOpen(true);
    } else {
      setOpen(false);
    }
  }, [account, ob, total]);

  const persistStep = useCallback((n: number) => {
    api.updateOnboarding({ step: n }).catch(() => {});
  }, []);

  async function finish(reason: "finish" | "skip") {
    setSaving(true);
    try {
      const res = await api.updateOnboarding({ completed: true, step: reason === "finish" ? total : step });
      if (account) setAccount({ ...account, onboarding: res });
    } catch {
      /* the tour will simply offer itself again next time */
    } finally {
      setSaving(false);
      setOpen(false);
    }
  }
  function go(n: number) {
    const next = Math.max(0, Math.min(total - 1, n));
    setStep(next);
    persistStep(next);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" && step < total - 1) go(step + 1);
      else if (e.key === "ArrowLeft" && step > 0) go(step - 1);
      else if (e.key === "Escape") finish("skip");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step]);

  if (!open || !account) return null;
  const s = TOUR_STEPS[step];
  const last = step === total - 1;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/45" role="dialog" aria-modal aria-labelledby="tour-title">
      <div className="w-full max-w-lg bg-surface border border-border shadow-none">
        <div className="panel-head">
          <LogoMark size={18} />
          <span>getting started</span>
          <span className="meta tabular-nums">step {step + 1} of {total}</span>
        </div>

        {/* progress */}
        <div className="flex gap-px px-3 pt-3" aria-hidden>
          {TOUR_STEPS.map((_, i) => (
            <span key={i} className={`flex-1 h-[3px] ${i <= step ? "bg-brand" : "bg-track"}`} />
          ))}
        </div>

        <div className="p-4 min-h-[190px]">
          <h2 id="tour-title" className="text-[16px] font-medium text-title tracking-tightest">{s.title}</h2>
          <p className="text-[12.5px] leading-relaxed text-cell mt-2 font-prose">{s.body}</p>
          {s.caveat && <div className="caveat mt-3 border border-warn/30">{s.caveat}</div>}
          {s.link && (
            <Link href={s.link.href} onClick={() => persistStep(step)} className="inline-block mt-3 text-[11.5px] text-brand hover:underline">
              {s.link.label} →
            </Link>
          )}
        </div>

        <div className="flex items-center gap-2 px-4 py-3 border-t border-border">
          <button onClick={() => finish("skip")} disabled={saving} className="text-[11px] text-faint hover:text-ink">
            Skip tutorial
          </button>
          <span className="flex-1" />
          <button onClick={() => go(step - 1)} disabled={step === 0 || saving} className="btn-ghost text-[12px]">
            Back
          </button>
          {last ? (
            <button onClick={() => finish("finish")} disabled={saving} className="btn-primary text-[12px]">
              {saving ? "Saving…" : "Finish"}
            </button>
          ) : (
            <button onClick={() => go(step + 1)} disabled={saving} className="btn-primary text-[12px]">
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** "Replay tutorial" control for Settings / Help. */
export function ReplayTourButton({ className = "" }: { className?: string }) {
  const { account, setAccount } = useAuth();
  const [busy, setBusy] = useState(false);
  async function replay() {
    setBusy(true);
    try {
      const res = await api.updateOnboarding({ completed: false, step: 0 });
      if (account) setAccount({ ...account, onboarding: res });
    } finally { setBusy(false); }
  }
  return (
    <button onClick={replay} disabled={busy} className={`btn-ghost text-[12px] ${className}`}>
      {busy ? "Starting…" : "Replay tutorial"}
    </button>
  );
}
