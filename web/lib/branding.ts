/**
 * Central product identity for the web app.
 *
 * Mirrors `qguide/app/branding.py`. Every visible mention of the product name,
 * tagline, support address or legal entity must read from here — renaming the
 * product is then one edit (or a set of env vars), not a codebase search.
 *
 * Values can be overridden at build time with NEXT_PUBLIC_* env vars, and the
 * backend's /branding endpoint is the runtime source of truth if you prefer to
 * drive it from the server (see `useBranding`).
 */

const env = (key: string, fallback: string) => {
  const v = process.env[key as keyof NodeJS.ProcessEnv] as string | undefined;
  return v && v.trim() ? v.trim() : fallback;
};

export interface BrandingConfig {
  APP_NAME: string;
  APP_SHORT_NAME: string;
  APP_DESCRIPTION: string;
  TAGLINE: string;
  LOGO_MARK: string;
  LOGO_URL: string;
  SUPPORT_EMAIL: string;
  LEGAL_COMPANY_NAME: string;
  WEBSITE_URL: string;
  DOCS_URL: string;
}

export const BRANDING: BrandingConfig = {
  APP_NAME: env("NEXT_PUBLIC_APP_NAME", "QGuide"),
  APP_SHORT_NAME: env("NEXT_PUBLIC_APP_SHORT_NAME", env("NEXT_PUBLIC_APP_NAME", "QGuide")),
  APP_DESCRIPTION: env(
    "NEXT_PUBLIC_APP_DESCRIPTION",
    "Context-aware, explainable CRISPR guide RNA design and analysis."
  ),
  TAGLINE: env("NEXT_PUBLIC_APP_TAGLINE", "Explainable, outcome-first CRISPR guide design"),
  LOGO_MARK: env("NEXT_PUBLIC_APP_LOGO_MARK", "Q"),
  LOGO_URL: env("NEXT_PUBLIC_APP_LOGO_URL", ""),
  SUPPORT_EMAIL: env("NEXT_PUBLIC_SUPPORT_EMAIL", "support@qguide.bio"),
  LEGAL_COMPANY_NAME: env("NEXT_PUBLIC_LEGAL_COMPANY_NAME", "QGuide"),
  WEBSITE_URL: env("NEXT_PUBLIC_APP_WEBSITE_URL", ""),
  DOCS_URL: env("NEXT_PUBLIC_APP_DOCS_URL", ""),
};

/** Lowercase, filesystem/URL-safe form of the app name (export filenames, ids). */
export const APP_SLUG = BRANDING.APP_NAME.toLowerCase().replace(/[^a-z0-9]+/g, "");

/** One-line research-use notice — keep in sync with `legal.SHORT_DISCLAIMER`. */
export const SHORT_DISCLAIMER =
  `${BRANDING.APP_NAME} output is a computational estimate for research use only — ` +
  `not validated laboratory or clinical advice. Validate experimentally.`;

export const {
  APP_NAME,
  APP_DESCRIPTION,
  TAGLINE,
  LOGO_MARK,
  SUPPORT_EMAIL,
  LEGAL_COMPANY_NAME,
} = BRANDING;
