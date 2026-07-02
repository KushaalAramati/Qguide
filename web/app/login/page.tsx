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
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [pwErr, setPwErr] = useState(false);   // red-border the password field
  const [busy, setBusy] = useState(false);

  function switchTab(t: "in" | "up") {
    setTab(t); setErr(""); setPwErr(false);
  }

  async function submit() {
    setErr(""); setPwErr(false); setBusy(true);
    try {
      let res;
      if (tab === "in") {
        res = await api.login(email, pw);
      } else {
        const fullName = `${first} ${last}`.trim();
        res = await api.signup(fullName, email, pw);
      }
      setToken(res.token);
      setAccount(res.account);
      router.replace("/new");
    } catch (e: any) {
      // 401 on sign-in => wrong password: precise message + red border.
      if (tab === "in" && e.status === 401) {
        setErr("Incorrect password. Please try again.");
        setPwErr(true);
      } else if (tab === "in" && e.status === 404) {
        setErr("No account found for that email.");
      } else {
        setErr(e.message || "Something went wrong.");
      }
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
              <button key={t} onClick={() => switchTab(t)}
                className={`px-3 py-2 font-bold text-sm ${tab === t ? "text-brand border-b-2 border-brand" : "text-muted"}`}>
                {t === "in" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-3">
            {tab === "up" && (
              <div className="grid grid-cols-2 gap-3">
                <div><div className="label mb-1">First name</div>
                  <input className="input" value={first} onChange={(e) => setFirst(e.target.value)} /></div>
                <div><div className="label mb-1">Last name</div>
                  <input className="input" value={last} onChange={(e) => setLast(e.target.value)} /></div>
              </div>
            )}
            <div><div className="label mb-1">Email</div>
              <input className="input" type="email" value={email}
                onChange={(e) => { setEmail(e.target.value); setPwErr(false); setErr(""); }} /></div>
            <div>
              <div className="label mb-1">Password</div>
              <input
                className={`input ${pwErr ? "!border-bad border-2 focus:!border-bad" : ""}`}
                type="password" value={pw}
                onChange={(e) => { setPw(e.target.value); setPwErr(false); }}
                onKeyDown={(e) => e.key === "Enter" && submit()} />
              {err && <div className="text-bad text-sm font-semibold mt-1.5">⚠ {err}</div>}
            </div>
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
