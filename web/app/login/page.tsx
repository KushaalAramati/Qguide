"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";
import { Dna } from "@/components/Dna";
import { LogoMark, LegalFooter } from "@/components/Brand";
import { BRANDING } from "@/lib/branding";

/**
 * Sign in / create account.
 *
 * Account creation requires explicit acceptance of the Terms and Privacy Policy —
 * the backend rejects a signup without it, so this checkbox is the UI half of a
 * server-enforced rule, not decoration.
 */
export default function LoginPage() {
  const router = useRouter();
  const { setAccount } = useAuth();
  const [tab, setTab] = useState<"in" | "up">("in");
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [institution, setInstitution] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [accept, setAccept] = useState(false);
  const [err, setErr] = useState("");
  const [fieldErr, setFieldErr] = useState<"password" | "email" | "terms" | "">("");
  const [busy, setBusy] = useState(false);

  const pwTooShort = tab === "up" && pw.length > 0 && pw.length < 8;
  const canSubmit =
    tab === "in"
      ? !!email && !!pw
      : !!first.trim() && !!email && pw.length >= 8 && accept;

  function switchTab(t: "in" | "up") {
    setTab(t);
    setErr("");
    setFieldErr("");
  }

  async function submit() {
    if (busy || !canSubmit) return;
    setErr("");
    setFieldErr("");
    setBusy(true);
    try {
      const res =
        tab === "in"
          ? await api.login(email, pw)
          : await api.signup({
              name: `${first} ${last}`.trim(),
              email,
              password: pw,
              accept_terms: accept,
              institution: institution.trim() || undefined,
            });
      setToken(res.token);
      setAccount(res.account);
      router.replace("/dashboard");
    } catch (e: any) {
      const msg: string = e.message || "Something went wrong.";
      if (tab === "in" && e.status === 401) {
        setErr("Incorrect password. Please try again.");
        setFieldErr("password");
      } else if (tab === "in" && e.status === 404) {
        setErr("No account found for that email address.");
        setFieldErr("email");
      } else if (e.status === 403) {
        setErr(msg);
      } else if (e.status === 429) {
        setErr(msg);
      } else if (e.status === 409) {
        setErr("An account with that email already exists — sign in instead.");
        setFieldErr("email");
      } else if (e.status === 400 && /password/i.test(msg)) {
        setErr(msg);
        setFieldErr("password");
      } else if (e.status === 400 && /terms/i.test(msg)) {
        setErr(msg);
        setFieldErr("terms");
      } else {
        setErr(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  const bad = (f: string) => (fieldErr === f ? "!border-bad focus:!border-bad" : "");

  return (
    <div className="min-h-screen grid place-items-center p-4 bg-bg">
      <div className="w-full max-w-md">
        {/* ---- product mark ---- */}
        <div className="flex flex-col items-center gap-2 mb-3">
          <LogoMark size={40} />
          <h1 className="text-[22px] font-medium text-title tracking-tightest">
            {BRANDING.APP_NAME}
          </h1>
          <p className="text-[11.5px] text-muted text-center">{BRANDING.TAGLINE}</p>
        </div>
        <Dna width={460} height={48} turns={5} />

        <div className="panel mt-3">
          <div className="flex border-b border-border">
            {(["in", "up"] as const).map((t) => (
              <button
                key={t}
                onClick={() => switchTab(t)}
                aria-current={tab === t ? "page" : undefined}
                className={`px-4 py-2 text-[12px] border-b-2 -mb-px transition-colors ${
                  tab === t
                    ? "text-brand border-brand bg-brand/[0.05]"
                    : "text-faint border-transparent hover:text-ink"
                }`}
              >
                {t === "in" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <div className="p-4 flex flex-col gap-3">
            {tab === "up" && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label mb-1 block" htmlFor="first">First name</label>
                    <input id="first" className="input" value={first} autoComplete="given-name"
                           onChange={(e) => setFirst(e.target.value)} />
                  </div>
                  <div>
                    <label className="label mb-1 block" htmlFor="last">Last name</label>
                    <input id="last" className="input" value={last} autoComplete="family-name"
                           onChange={(e) => setLast(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="label mb-1 block" htmlFor="inst">
                    Institution <span className="normal-case tracking-normal">(optional)</span>
                  </label>
                  <input id="inst" className="input" value={institution}
                         placeholder="Lab, university or company"
                         onChange={(e) => setInstitution(e.target.value)} />
                </div>
              </>
            )}

            <div>
              <label className="label mb-1 block" htmlFor="email">Email</label>
              <input
                id="email"
                className={`input ${bad("email")}`}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setErr(""); setFieldErr(""); }}
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
            </div>

            <div>
              <label className="label mb-1 block" htmlFor="pw">Password</label>
              <input
                id="pw"
                className={`input ${bad("password")}`}
                type="password"
                autoComplete={tab === "in" ? "current-password" : "new-password"}
                value={pw}
                onChange={(e) => { setPw(e.target.value); setErr(""); setFieldErr(""); }}
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
              {tab === "up" && (
                <div className={`text-[10.5px] mt-1 ${pwTooShort ? "text-warn" : "text-faint"}`}>
                  At least 8 characters, with letters and numbers.
                </div>
              )}
              {tab === "in" && (
                <div className="text-right mt-1.5">
                  <Link href="/forgot" className="text-[11px] text-brand hover:underline">
                    Forgot password?
                  </Link>
                </div>
              )}
            </div>

            {tab === "up" && (
              <label
                className={`flex items-start gap-2 text-[11px] leading-relaxed cursor-pointer p-2 border ${
                  fieldErr === "terms" ? "border-bad bg-bad/[0.06]" : "border-border bg-well"
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 accent-current"
                  checked={accept}
                  onChange={(e) => { setAccept(e.target.checked); setFieldErr(""); }}
                />
                <span className="text-muted">
                  I agree to the{" "}
                  <Link href="/terms" target="_blank" className="text-brand hover:underline">Terms of Service</Link>,{" "}
                  <Link href="/privacy" target="_blank" className="text-brand hover:underline">Privacy Policy</Link>{" "}
                  and the{" "}
                  <Link href="/disclaimer" target="_blank" className="text-brand hover:underline">
                    Scientific Disclaimer
                  </Link>{" "}
                  — {BRANDING.APP_NAME} output is for research use and is not validated
                  laboratory or clinical advice.
                </span>
              </label>
            )}

            {err && (
              <div role="alert" className="border border-bad/40 bg-bad/[0.07] text-bad text-[11.5px] px-2.5 py-2">
                {err}
              </div>
            )}

            <Button onClick={submit} disabled={busy || !canSubmit} full>
              {busy
                ? tab === "in" ? "Signing in…" : "Creating account…"
                : tab === "in" ? "Sign in" : "Create account"}
            </Button>

            {tab === "in" ? (
              <div className="text-[11px] text-faint text-center">
                New here?{" "}
                <button onClick={() => switchTab("up")} className="text-brand hover:underline">
                  Create an account
                </button>
              </div>
            ) : (
              <div className="text-[11px] text-faint text-center">
                Already have an account?{" "}
                <button onClick={() => switchTab("in")} className="text-brand hover:underline">
                  Sign in
                </button>
              </div>
            )}
          </div>
        </div>

        <LegalFooter className="mt-4 justify-center" />
      </div>
    </div>
  );
}
