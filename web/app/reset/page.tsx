"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";

function ResetInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { setAccount } = useAuth();
  const [token, setTok] = useState("");
  const [pw, setPw] = useState(""); const [cf, setCf] = useState("");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  useEffect(() => { const t = params.get("token"); if (t) setTok(t); }, [params]);
  async function submit() {
    setErr("");
    if (pw.length < 6) return setErr("Password must be at least 6 characters.");
    if (pw !== cf) return setErr("Passwords do not match.");
    setBusy(true);
    try {
      const r = await api.resetPassword(token, pw);
      setToken(r.token); setAccount(r.account); router.replace("/dashboard");
    } catch (e: any) { setErr(e.message || "Failed."); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen grid place-items-center bg-bg p-6">
      <div className="card w-full max-w-md">
        <div className="font-display font-extrabold text-2xl">Set a new password</div>
        <div className="mt-4 flex flex-col gap-3">
          <div><div className="label mb-1">Reset token</div><input className="input" value={token} onChange={(e) => setTok(e.target.value)} placeholder="paste token" /></div>
          <div><div className="label mb-1">New password</div><input type="password" className="input" value={pw} onChange={(e) => setPw(e.target.value)} /></div>
          <div><div className="label mb-1">Confirm password</div><input type="password" className="input" value={cf} onChange={(e) => setCf(e.target.value)} /></div>
          <Button onClick={submit} disabled={busy || !token || !pw} full>Reset password</Button>
          {err && <div className="text-sm text-bad">{err}</div>}
          <Link href="/login" className="text-brand text-sm font-semibold">← Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}

export default function ResetPage() {
  return <Suspense fallback={<div className="min-h-screen grid place-items-center text-muted">Loading…</div>}><ResetInner /></Suspense>;
}
