"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";
import { Dna } from "@/components/Dna";

export default function LoginPage() {
  const router = useRouter();
  const { setAccount } = useAuth();
  const [tab, setTab] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setErr(""); setBusy(true);
    try {
      const res = tab === "in" ? await api.login(email, pw) : await api.signup(name, email, pw);
      setToken(res.token);
      setAccount(res.account);
      router.replace("/new");
    } catch (e: any) {
      setErr(e.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-3">
          <div className="text-4xl">🧬</div>
          <div className="font-display font-extrabold text-3xl bg-gradient-to-r from-brand to-brand-light bg-clip-text text-transparent">Q-Guide</div>
          <div className="text-muted text-sm">Quantum-assisted gRNA design</div>
        </div>
        <Dna width={460} height={56} turns={5} />
        <div className="card mt-3">
          <div className="flex gap-1 mb-4 border-b border-border">
            {(["in", "up"] as const).map((t) => (
              <button key={t} onClick={() => { setTab(t); setErr(""); }}
                className={`px-3 py-2 font-bold text-sm ${tab === t ? "text-brand border-b-2 border-brand" : "text-muted"}`}>
                {t === "in" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-3">
            {tab === "up" && (
              <div><div className="label mb-1">Full name</div>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
            )}
            <div><div className="label mb-1">Email</div>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div><div className="label mb-1">Password</div>
              <input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()} /></div>
            {err && <div className="text-bad text-sm font-semibold">{err}</div>}
            <Button onClick={submit} disabled={busy} full>
              {busy ? "Please wait…" : tab === "in" ? "Sign in" : "Create account (+25 credits)"}
            </Button>
            {tab === "in" && <div className="text-xs text-muted">New here? Switch to <b>Create account</b> for 25 free credits.</div>}
          </div>
        </div>
        <div className="text-center text-xs text-muted mt-3">
          Prototype — credits & accounts are for testing. The Buy Credits checkout is simulated.
        </div>
      </div>
    </div>
  );
}
