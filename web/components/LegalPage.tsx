"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { BRANDING } from "@/lib/branding";
import { LogoMark, LegalFooter } from "@/components/Brand";

interface Section { heading: string; body: string }
interface Doc { slug: string; title: string; updated: string; summary: string; sections: Section[] }

const TABS: [string, string][] = [
  ["/terms", "Terms of Service"],
  ["/privacy", "Privacy Policy"],
  ["/disclaimer", "Scientific Disclaimer"],
];

/**
 * Renders a legal document served by the backend (`/legal/{slug}`), so the text
 * has exactly one source and can be replaced with lawyer-reviewed language in
 * `qguide/app/legal.py` without touching the frontend.
 */
export function LegalPage({ slug }: { slug: string }) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let live = true;
    setDoc(null); setErr("");
    api.legal(slug)
      .then((d) => { if (live) setDoc(d); })
      .catch((e) => { if (live) setErr(e.message || "Could not load this document."); });
    return () => { live = false; };
  }, [slug]);

  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="border-b border-border bg-surface">
        <div className="max-w-3xl mx-auto px-5 py-3 flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 hover:opacity-80">
            <LogoMark size={24} />
            <span className="text-title font-medium tracking-tightest">{BRANDING.APP_NAME}</span>
          </Link>
          <span className="flex-1" />
          <Link href="/login" className="text-[11.5px] text-brand hover:underline">Sign in</Link>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-5 py-6">
        <nav className="flex flex-wrap gap-x-1 border-b border-border mb-5">
          {TABS.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={href === `/${slug}` ? "page" : undefined}
              className={`px-3 py-2 text-[11.5px] border-b-2 -mb-px ${
                href === `/${slug}`
                  ? "text-brand border-brand"
                  : "text-faint border-transparent hover:text-ink"
              }`}
            >
              {label}
            </Link>
          ))}
        </nav>

        {err && (
          <div className="panel">
            <div className="panel-head">unavailable</div>
            <div className="panel-body text-[12px] text-muted">
              {err}
              <div className="mt-2 text-faint text-[11px]">
                Contact{" "}
                <a className="text-brand hover:underline" href={`mailto:${BRANDING.SUPPORT_EMAIL}`}>
                  {BRANDING.SUPPORT_EMAIL}
                </a>{" "}
                for a copy of this document.
              </div>
            </div>
          </div>
        )}

        {!doc && !err && (
          <div className="flex flex-col gap-3" aria-busy>
            <div className="h-6 w-1/3 bg-track animate-pulse" />
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex flex-col gap-1.5">
                <div className="h-3 w-1/4 bg-track animate-pulse" />
                <div className="h-3 w-full bg-track/60 animate-pulse" />
                <div className="h-3 w-5/6 bg-track/60 animate-pulse" />
              </div>
            ))}
          </div>
        )}

        {doc && (
          <article className="font-prose">
            <h1 className="text-[24px] font-medium text-title tracking-tightest font-mono">
              {doc.title}
            </h1>
            <p className="text-[12px] text-muted mt-1">{doc.summary}</p>
            <p className="text-[10.5px] text-faint mt-1 font-mono">
              {BRANDING.LEGAL_COMPANY_NAME} · last updated {doc.updated}
            </p>

            <div className="mt-5 flex flex-col gap-5">
              {doc.sections.map((sec) => (
                <section key={sec.heading}>
                  <h2 className="text-[13px] font-mono font-medium text-title mb-1.5">{sec.heading}</h2>
                  {sec.body.split("\n\n").map((para, i) => (
                    <p key={i} className="text-[13px] leading-relaxed text-cell mb-2">{para}</p>
                  ))}
                </section>
              ))}
            </div>

            <div className="mt-8 border border-warn/30 bg-warn/[0.06] px-3 py-2.5 text-[11.5px] text-warn leading-relaxed">
              This text is an operational draft written for clarity, not reviewed by
              legal counsel. {BRANDING.LEGAL_COMPANY_NAME} should replace it with
              counsel-approved language before commercial launch.
            </div>
          </article>
        )}

        <LegalFooter className="mt-8 pt-4 border-t border-divider" />
      </div>
    </div>
  );
}
