"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  async function submit() {
    setBusy(true); setErr("");
    try { setRes(await api.forgotPassword(email)); }
    catch (e: any) { setErr(e.message || "Failed."); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen grid place-items-center bg-bg p-6">
      <div className="card w-full max-w-md">
        <div className="font-display font-extrabold text-2xl">Reset your password</div>
        <div className="text-muted text-sm mt-1">Enter your account email and we'll generate a reset link.</div>
        {!res ? (
          <div className="mt-4 flex flex-col gap-3">
            <input className="input" placeholder="you@lab.org" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Button onClick={submit} disabled={busy || !email} full>Generate reset link</Button>
            {err && <div className="text-sm text-bad">{err}</div>}
          </div>
        ) : (
          <div className="mt-4">
            <div className="text-sm text-good font-semibold">{res.message}</div>
            {res.reset_token ? (
              <div className="mt-3">
                <div className="text-[11px] text-warn mb-1">⚠ Dev mode — normally this token is emailed, not shown. Use it on the reset page:</div>
                <Link href={`/reset?token=${encodeURIComponent(res.reset_token)}`} className="btn-primary block text-center">Continue to reset →</Link>
              </div>
            ) : (
              <div className="text-sm text-muted mt-2">If an account exists for that email, a reset link has been generated.</div>
            )}
          </div>
        )}
        <div className="mt-4 text-sm"><Link href="/login" className="text-brand font-semibold">← Back to sign in</Link></div>
      </div>
    </div>
  );
}
