"""
Legal and scientific-disclaimer text, kept in one replaceable module.

The text below is a good-faith operational draft written to be clear and honest
about what the platform does; it has NOT been reviewed by a lawyer. Replace the
body of each document with counsel-reviewed language when you have it -- the
structure, versioning and consent plumbing do not need to change.

Bump TERMS_VERSION whenever the Terms or Privacy Policy change materially: the
version a user accepted is stored on their account (`users.terms_version`), so
you can tell who has agreed to what and prompt for re-acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List

from qguide.app.branding import BRANDING

TERMS_VERSION = "2026-09-01"


@dataclass(frozen=True)
class LegalDocument:
    slug: str
    title: str
    updated: str
    summary: str
    #: Ordered (heading, body) sections. Body paragraphs are separated by "\n\n".
    sections: List[tuple]

    def as_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["sections"] = [{"heading": h, "body": b} for h, b in self.sections]
        return d


_APP = BRANDING.app_name
_CO = BRANDING.legal_company_name
_SUPPORT = BRANDING.support_email

TERMS = LegalDocument(
    slug="terms",
    title="Terms of Service",
    updated=TERMS_VERSION,
    summary=f"The agreement between you and {_CO} for use of {_APP}.",
    sections=[
        ("1. Acceptance",
         f"By creating an account or using {_APP} (the \"Service\"), you agree to "
         f"these Terms of Service and to the {_APP} Privacy Policy. If you are "
         "using the Service on behalf of an organisation, you confirm you are "
         "authorised to accept these terms for that organisation."),
        ("2. What the Service is",
         f"{_APP} is a computational design and analysis tool for CRISPR guide RNA "
         "selection. It generates candidate guides, scores them with interpretable "
         "models and heuristics, and produces explanations, comparisons and "
         "reports.\n\n"
         "The Service is a decision-support tool. It is not a laboratory service, "
         "a diagnostic device, or a source of medical or clinical advice."),
        ("3. Accounts and security",
         "You are responsible for the accuracy of your account information, for "
         "keeping your password confidential, and for all activity under your "
         "account. Notify us promptly at "
         f"{_SUPPORT} if you believe your account has been compromised.\n\n"
         "Administrator access is granted only through our internal controls. You "
         "may not attempt to escalate your own privileges, access another user's "
         "projects, or circumvent the Service's access controls."),
        ("4. Your content",
         "You retain all rights in the sequences, project data, notes and other "
         "material you submit (\"Your Content\"). You grant us only the limited "
         "licence needed to store and process Your Content in order to operate the "
         "Service for you and the collaborators you invite.\n\n"
         "You are responsible for having the right to submit Your Content and for "
         "complying with any obligations attached to it, including institutional, "
         "export-control and data-protection requirements."),
        ("5. Acceptable use",
         "You may not use the Service to design, plan or support work intended to "
         "cause harm, including the creation of biological agents intended to harm "
         "humans, animals, plants or the environment; nor for any unlawful purpose; "
         "nor in violation of applicable biosafety, biosecurity or research-ethics "
         "rules that apply to you or your institution."),
        ("6. Research use only",
         "The Service is provided for research and educational use. Outputs must "
         "not be used as the sole basis for clinical, diagnostic, therapeutic or "
         "regulatory decisions. See the Scientific Disclaimer for detail on model "
         "limitations."),
        ("7. Availability and changes",
         "We may modify, suspend or discontinue features. We aim to give reasonable "
         "notice of material changes that reduce functionality you rely on. Scheduled "
         "maintenance and unplanned downtime may occur."),
        ("8. Fees",
         "Paid plans and credit purchases, where offered, are described at the point "
         "of purchase. Charges are for access to computational capacity and features, "
         "not for any guarantee of experimental outcome."),
        ("9. Disclaimer of warranties",
         "The Service is provided \"as is\" and \"as available\", without warranties "
         "of any kind, whether express or implied, including fitness for a particular "
         "purpose and non-infringement. We do not warrant that predictions, scores or "
         "rankings will correspond to experimental results."),
        ("10. Limitation of liability",
         "To the maximum extent permitted by law, "
         f"{_CO} is not liable for indirect, incidental, special, consequential or "
         "exemplary damages, or for lost profits, lost data, or the cost of "
         "substitute services, arising from your use of the Service — including "
         "experimental costs incurred in reliance on its output."),
        ("11. Termination",
         "You may stop using the Service and delete your account at any time. We may "
         "suspend or terminate an account that violates these terms or that poses a "
         "security or safety risk."),
        ("12. Contact",
         f"Questions about these terms: {_SUPPORT}."),
    ],
)

PRIVACY = LegalDocument(
    slug="privacy",
    title="Privacy Policy",
    updated=TERMS_VERSION,
    summary="What we collect, why we collect it, and the choices you have.",
    sections=[
        ("Data we collect",
         "Account data: your name, email address, password hash (never the password "
         "itself), optional institution and research area, account role and status, "
         "and the date you accepted these terms.\n\n"
         "Project data: the sequences and parameters you submit, the results the "
         "Service computes, project names, folders, notes and collaborator "
         "memberships.\n\n"
         "Operational data: sign-in timestamps, credit and usage ledger entries, and "
         "server logs needed to run and secure the Service."),
        ("How we use it",
         "To operate the Service for you: run analyses, store and retrieve your "
         "projects, share projects with collaborators you invite, apply your plan's "
         "entitlements, send transactional email (password resets, invitations, "
         "security notices), and keep the platform secure and available."),
        ("Passwords",
         "Passwords are stored only as salted PBKDF2-HMAC-SHA256 hashes. Nobody at "
         f"{_CO}, including administrators, can read your password."),
        ("What administrators can see",
         "Administrators can see account-level information — name, email, role, "
         "status, plan, credit balance, run counts and sign-in times — in order to "
         "support and operate the platform. Administrators do not get automatic "
         "access to the contents of your projects, sequences or results."),
        ("Sharing",
         "We share project content only with the collaborators you invite. We use "
         "service providers for hosting, database and email delivery; they process "
         "data on our instructions. We do not sell personal data and we do not use "
         "your sequences to train models without a separate, explicit agreement."),
        ("Retention",
         "Account and project data are retained while your account is active. When "
         "you delete a project it is removed from the Service; backups age out on "
         "the provider's normal cycle. You can request account deletion at "
         f"{_SUPPORT}."),
        ("Your choices",
         "You can edit your profile, change your password, and control notification "
         "preferences in Settings. You can request a copy or deletion of your data by "
         f"contacting {_SUPPORT}."),
        ("Contact",
         f"Privacy questions: {_SUPPORT}."),
    ],
)

DISCLAIMER = LegalDocument(
    slug="disclaimer",
    title="Scientific & Research-Use Disclaimer",
    updated=TERMS_VERSION,
    summary="What the scores mean, what they do not mean, and what to validate.",
    sections=[
        ("Research use only",
         f"{_APP} is intended for research and educational use. Its output is not "
         "validated laboratory advice, not a diagnostic result, and not clinical "
         "guidance. Do not use it as the sole basis for any clinical, therapeutic, "
         "diagnostic or regulatory decision."),
        ("Predictions are computational estimates",
         "Guide scores, outcome predictions, precision scores and guide-set "
         "recommendations are produced by interpretable models and heuristics. Several "
         "components are explicitly provisional — they encode published rules and "
         "biophysical reasoning rather than being trained on your experimental system. "
         "Components are labelled in the interface with their provenance (real / "
         "heuristic / provisional); those labels are part of the result, not "
         "decoration."),
        ("Off-target analysis is heuristic",
         "Unless a genome alignment engine has been configured for your deployment, "
         "off-target assessment is sequence-heuristic: it does not perform a "
         "genome-wide alignment and cannot enumerate every genomic site. A low "
         "predicted off-target risk is not evidence of specificity. Confirm candidate "
         "guides with an appropriate genome-wide method (for example GUIDE-seq, "
         "CIRCLE-seq, or targeted amplicon sequencing) before relying on them."),
        ("Quantum-assisted optimisation",
         "Where a quantum or quantum-inspired optimiser is used, it selects guide "
         "SETS against the objective you configure. It changes how candidates are "
         "combined, not how accurate the underlying scores are. A quantum-selected "
         "set is not inherently more biologically valid than a classical one."),
        ("Validate before you commit resources",
         "Treat every recommendation as a hypothesis to test. Confirm target-site "
         "sequence and variants in your actual cell line or organism, check delivery "
         "and expression assumptions, and validate editing outcomes empirically."),
        ("No warranty",
         "Predictions are provided without warranty of accuracy or fitness for a "
         "particular purpose. You remain responsible for experimental design, "
         "biosafety review, and compliance with the rules of your institution and "
         "jurisdiction."),
    ],
)

LEGAL_DOCUMENTS: Dict[str, LegalDocument] = {
    d.slug: d for d in (TERMS, PRIVACY, DISCLAIMER)
}

#: One-line notice suitable for footers, reports and export headers.
SHORT_DISCLAIMER = (
    f"{_APP} output is a computational estimate for research use only — not "
    "validated laboratory or clinical advice. Validate experimentally."
)
