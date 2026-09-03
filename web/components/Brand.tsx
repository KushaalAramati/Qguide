import Link from "next/link";
import { BRANDING } from "@/lib/branding";

/**
 * The product mark. Every place that would otherwise hardcode a logo or the app
 * name renders this, so a rebrand is a config change.
 */
export function LogoMark({ size = 26 }: { size?: number }) {
  if (BRANDING.LOGO_URL) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img src={BRANDING.LOGO_URL} alt={BRANDING.APP_NAME} width={size} height={size}
           style={{ width: size, height: size, objectFit: "contain" }} />
    );
  }
  return (
    <span
      className="grid place-items-center border border-brand bg-brand/[0.12] text-brand font-semibold flex-none"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.5) }}
      aria-hidden
    >
      {BRANDING.LOGO_MARK}
    </span>
  );
}

export function Wordmark({ size = 26, className = "" }: { size?: number; className?: string }) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <LogoMark size={size} />
      <span className="text-title font-medium tracking-tightest truncate">{BRANDING.APP_NAME}</span>
    </span>
  );
}

/** Legal/footer links — used on auth screens and inside the app shell. */
export function LegalFooter({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-faint ${className}`}>
      <span>
        © {new Date().getFullYear()} {BRANDING.LEGAL_COMPANY_NAME}
      </span>
      <Link href="/terms" className="hover:text-brand">Terms</Link>
      <Link href="/privacy" className="hover:text-brand">Privacy</Link>
      <Link href="/disclaimer" className="hover:text-brand">Scientific disclaimer</Link>
      <a href={`mailto:${BRANDING.SUPPORT_EMAIL}`} className="hover:text-brand">Support</a>
    </div>
  );
}
