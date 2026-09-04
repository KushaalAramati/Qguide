"""
Central branding / product-identity configuration.

Every user-visible mention of the product name, tagline, support address or legal
entity should read from here (or from the mirrored frontend module
`web/lib/branding.ts`) rather than hardcoding a string. Renaming the product is
then a one-line change here plus the matching env vars -- no code search.

Every field is overridable by an environment variable so a rebrand (or a
white-label deployment) needs no code change at all.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Dict


def _env(key: str, default: str) -> str:
    v = os.environ.get(key)
    return v.strip() if v and v.strip() else default


@dataclass(frozen=True)
class Branding:
    app_name: str
    app_short_name: str
    app_description: str
    tagline: str
    logo_mark: str          # single-character/emoji mark used in compact chrome
    logo_url: str           # optional full logo asset (empty -> use logo_mark)
    support_email: str
    legal_company_name: str
    website_url: str
    docs_url: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


BRANDING = Branding(
    app_name=_env("APP_NAME", "QGuide"),
    app_short_name=_env("APP_SHORT_NAME", _env("APP_NAME", "QGuide")),
    app_description=_env(
        "APP_DESCRIPTION",
        "Context-aware, explainable, quantum-assisted CRISPR guide RNA design. "
        "Optimises for predicted biological outcome, not just cutting.",
    ),
    tagline=_env("APP_TAGLINE", "Explainable, outcome-first CRISPR guide design"),
    logo_mark=_env("APP_LOGO_MARK", "Q"),
    logo_url=_env("APP_LOGO_URL", ""),
    support_email=_env("SUPPORT_EMAIL", "support@qguide.bio"),
    legal_company_name=_env("LEGAL_COMPANY_NAME", "QGuide"),
    website_url=_env("APP_WEBSITE_URL", ""),
    docs_url=_env("APP_DOCS_URL", ""),
)

# Convenience aliases (import these rather than re-reading the env).
APP_NAME = BRANDING.app_name
APP_DESCRIPTION = BRANDING.app_description
TAGLINE = BRANDING.tagline
SUPPORT_EMAIL = BRANDING.support_email
LEGAL_COMPANY_NAME = BRANDING.legal_company_name
