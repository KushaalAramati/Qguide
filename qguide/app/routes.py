"""
FastAPI routes for Q-Guide.

Thin HTTP layer over the core pipeline. The API is deliberately stateless and
returns plain Pydantic models (JSON) so a React frontend can consume it directly;
the Streamlit prototype calls the same `core.pipeline` functions in-process.
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from qguide.app import auth, billing, emailer, ratelimit, store
from qguide.app import roles as roles_mod
from qguide.app.branding import BRANDING
from qguide.app.legal import LEGAL_DOCUMENTS, TERMS_VERSION


def bootstrap_admin_emails() -> set:
    """Environment-configured initial admins (ADMIN_EMAILS, comma-separated).
    These are a bootstrap mechanism only -- the authoritative role lives in the
    database and is read on every request."""
    return roles_mod.bootstrap_admin_emails()


def is_admin(email: str) -> bool:
    """Authoritative admin check: database role first, env allowlist as bootstrap."""
    email = (email or "").strip().lower()
    if store.get_role(email) == roles_mod.ADMIN:
        return True
    return email in bootstrap_admin_emails()
from qguide.app.schemas import DesignRequest, DesignResponse, Guide
from qguide.core import (
    formula_explainer,
    optimization,
    pipeline,
    precision_score,
    quantum_comparison_report,
)
from qguide.core.explainability import assumptions
from qguide.core.guide_generator import CAS_PROFILES

router = APIRouter()


# --------------------------------------------------------------------------- #
# Auth dependency                                                              #
# --------------------------------------------------------------------------- #
def current_email(authorization: Optional[str] = Header(default=None)) -> str:
    """Resolve the caller from the bearer token. The token carries identity only --
    role and account status are re-read from the database on every request, so a
    demoted or suspended user loses access immediately rather than at token expiry."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    email = auth.decode_token(authorization.split(" ", 1)[1])
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = store.get_user(email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if (user.get("status") or "active") != "active":
        raise HTTPException(status_code=403,
                            detail="This account has been suspended. Contact "
                                   f"{BRANDING.support_email}.")
    return email


def current_admin(email: str = Depends(current_email)) -> str:
    if not is_admin(email):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return email


def require_permission(permission: str):
    """Dependency factory for permission-gated routes (server-side authorization;
    the UI hiding a button is never the control)."""
    def _dep(email: str = Depends(current_email)) -> str:
        if not roles_mod.has_permission(store.get_role(email), permission):
            raise HTTPException(status_code=403,
                                detail="You do not have permission to do that.")
        return email
    return _dep


def _account(email: str) -> Optional[Dict]:
    """Account summary + role/permission flags (so the UI can reflect access)."""
    a = store.account_summary(email)
    if a is not None:
        a["is_admin"] = is_admin(email)
        a["role"] = store.get_role(email)
        a["permissions"] = roles_mod.permissions_for(a["role"])
    return a


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": BRANDING.app_name, "version": "1.0"}


@router.get("/branding")
def branding() -> Dict[str, object]:
    """Product identity for clients that want it from one place (public)."""
    return {**BRANDING.as_dict(), "terms_version": TERMS_VERSION}


@router.get("/legal")
def legal_index() -> Dict[str, object]:
    return {"terms_version": TERMS_VERSION,
            "documents": [{"slug": d.slug, "title": d.title, "updated": d.updated}
                          for d in LEGAL_DOCUMENTS.values()]}


@router.get("/legal/{slug}")
def legal_document(slug: str) -> Dict[str, object]:
    doc = LEGAL_DOCUMENTS.get(slug)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown legal document.")
    return doc.as_dict()


@router.get("/enzymes")
def enzymes() -> Dict[str, Dict]:
    """Supported Cas systems and their default PAM / guide length."""
    return {
        name: {"pam": p.pam, "guide_length": p.guide_length, "pam_side": p.pam_side}
        for name, p in CAS_PROFILES.items()
    }


@router.post("/design", response_model=DesignResponse)
def design(request: DesignRequest) -> DesignResponse:
    if not request.sequence.strip():
        raise HTTPException(status_code=400, detail="Empty sequence.")
    return pipeline.run_design(request)


class SensitivityRequest(BaseModel):
    request: DesignRequest
    guide_id: str
    scenarios: List[Dict[str, object]]


@router.post("/sensitivity")
def sensitivity(payload: SensitivityRequest) -> List[Dict[str, object]]:
    return pipeline.context_sensitivity(
        payload.request, payload.guide_id, payload.scenarios
    )


@router.get("/simulation/axes")
def simulation_axes() -> Dict[str, List[Dict[str, object]]]:
    """Built-in experiment-simulation sweeps (Cas enzyme, cell type, etc.)."""
    return pipeline.SIMULATION_AXES


class SimulationRequest(BaseModel):
    request: DesignRequest
    # Provide EITHER a named axis to sweep OR an explicit list of scenarios.
    axis: str | None = None
    scenarios: List[Dict[str, object]] | None = None


@router.post("/simulate")
def simulate(payload: SimulationRequest) -> List[Dict[str, object]]:
    if payload.axis:
        return pipeline.simulate_axis(payload.request, payload.axis)
    if payload.scenarios:
        return pipeline.simulate_experiments(payload.request, payload.scenarios)
    raise HTTPException(status_code=400, detail="Provide 'axis' or 'scenarios'.")


class PredictExperimentRequest(BaseModel):
    request: DesignRequest
    guide_id: str
    n_cells: int = 5000
    replicates: int = 300


@router.post("/predict-experiment")
def predict_experiment(payload: PredictExperimentRequest) -> Dict[str, object]:
    """Monte-Carlo the predicted experimental outcome of using a specific guide."""
    from qguide.core import experiment_simulation as expsim
    resp = pipeline.run_design(payload.request)
    guide = next((g for g in resp.guides if g.guide_id == payload.guide_id), None)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide {payload.guide_id} not found.")
    return expsim.simulate_experiment(guide, n_cells=payload.n_cells,
                                      replicates=payload.replicates)


@router.post("/report")
def report(request: DesignRequest) -> Dict[str, object]:
    """Structured scientific report for a design run (inputs, scores, set, warnings)."""
    from qguide.core import report as report_mod
    resp = pipeline.run_design(request)
    return report_mod.build_report(resp)


@router.post("/benchmark")
def benchmark(request: DesignRequest) -> Dict[str, object]:
    """Compare QGuide's outcome-first ranking against emulated tool-style baselines."""
    from qguide.core import benchmark as bench_mod
    resp = pipeline.run_design(request)
    return bench_mod.benchmark(resp.guides)


@router.get("/optimizer/modes")
def optimizer_modes() -> Dict[str, str]:
    return optimization.OPTIMIZER_MODES


@router.get("/optimizer/presets")
def optimizer_presets() -> Dict[str, Dict]:
    """QUBO weight presets: name -> {description, weights}. Weights are configurable."""
    from dataclasses import asdict
    return {
        name: {"description": optimization.PRESET_INFO.get(name, ""),
               "weights": asdict(w)}
        for name, w in optimization.PRESETS.items()
    }


@router.get("/precision/presets")
def precision_presets() -> Dict[str, Dict]:
    """QGuide Precision Score weight presets: name -> {positive, penalty} weight maps."""
    out: Dict[str, Dict] = {}
    for name in precision_score.preset_names():
        w = precision_score.get_weights(name)
        out[name] = {"positive": w.positive, "penalty": w.penalty}
    return out


class CompareBody(BaseModel):
    request: DesignRequest
    set_size: Optional[int] = None
    preset: str = "balanced"


@router.post("/optimizer/compare")
def optimizer_compare(body: CompareBody) -> Dict[str, object]:
    """Top-N vs classical vs quantum-inspired guide-set comparison, plus a plain-English
    set explanation. Free (no credit) — mirrors /design. Honest about the quantum layer."""
    if not body.request.sequence.strip():
        raise HTTPException(status_code=400, detail="Empty sequence.")
    resp = pipeline.run_design(body.request)
    if not resp.guides:
        raise HTTPException(status_code=400, detail="No guides found for this sequence / PAM.")
    set_size = body.set_size or body.request.set_size
    preset = body.preset or getattr(body.request, "optimizer_preset", "balanced")
    comparison = quantum_comparison_report.compare_selection_strategies(
        resp.guides, resp.request, set_size=set_size, preset=preset)
    explanation = formula_explainer.explain_set(resp.guides, comparison, preset=preset)
    return {"comparison": comparison, "set_explanation": explanation}


class ExplainBody(BaseModel):
    request: DesignRequest
    guide_id: Optional[str] = None      # defaults to the top-ranked guide


@router.post("/precision/explain")
def precision_explain(body: ExplainBody) -> Dict[str, object]:
    """Formula-level explanation of a guide's QGuide Precision Score (why high/low,
    which variables helped/hurt, what data was missing, what to validate)."""
    if not body.request.sequence.strip():
        raise HTTPException(status_code=400, detail="Empty sequence.")
    resp = pipeline.run_design(body.request)
    if not resp.guides:
        raise HTTPException(status_code=400, detail="No guides found for this sequence / PAM.")
    guide = (next((g for g in resp.guides if g.guide_id == body.guide_id), None)
             if body.guide_id else resp.guides[0])
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide {body.guide_id} not found.")
    return formula_explainer.explain_precision(guide)


@router.get("/assumptions")
def get_assumptions() -> Dict[str, List[str]]:
    return {"assumptions": assumptions()}


# --------------------------------------------------------------------------- #
# Auth + account                                                              #
# --------------------------------------------------------------------------- #
class SignupBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    #: Explicit consent, recorded with a timestamp and the terms version.
    accept_terms: bool = False
    institution: Optional[str] = None
    research_area: Optional[str] = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


def _client_key(request: Optional[Request], email: str) -> str:
    ip = ""
    if request is not None and request.client:
        ip = request.client.host or ""
    return f"{ip}|{(email or '').strip().lower()}"


LOGIN_LIMIT = int(os.environ.get("LOGIN_RATE_LIMIT", "10"))
LOGIN_WINDOW = int(os.environ.get("LOGIN_RATE_WINDOW", "300"))


@router.post("/auth/signup")
def signup(body: SignupBody, request: Request = None) -> Dict[str, object]:
    if not body.accept_terms:
        raise HTTPException(
            status_code=400,
            detail="You must accept the Terms of Service and Privacy Policy to "
                   "create an account.")
    allowed, retry = ratelimit.check(f"signup:{_client_key(request, body.email)}",
                                     limit=5, window_seconds=600)
    if not allowed:
        raise HTTPException(status_code=429,
                            detail=f"Too many sign-up attempts. Try again in {retry}s.")
    ok, msg = store.create_user(
        body.name, body.email, body.password, billing.SIGNUP_BONUS,
        institution=body.institution, research_area=body.research_area,
        terms_version=TERMS_VERSION, accepted_terms=True)
    if not ok:
        # Policy/validation failures are 400; a taken address is 409.
        code = 409 if "already exists" in msg else 400
        raise HTTPException(status_code=code, detail=msg)
    email = body.email.strip().lower()
    store.touch_login(email)
    try:
        emailer.send_welcome(email, body.name)
    except Exception:                                     # noqa: BLE001
        pass
    return {"token": auth.make_token(email), "account": _account(email)}


@router.post("/auth/login")
def login(body: LoginBody, request: Request = None) -> Dict[str, object]:
    key = f"login:{_client_key(request, body.email)}"
    allowed, retry = ratelimit.check(key, limit=LOGIN_LIMIT, window_seconds=LOGIN_WINDOW)
    if not allowed:
        raise HTTPException(status_code=429,
                            detail=f"Too many sign-in attempts. Try again in {retry}s.")
    ok, reason = store.authenticate(body.email, body.password)
    if not ok:
        # Distinct codes so the UI can show a precise message.
        if reason == "bad_password":
            raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
        if reason == "suspended":
            raise HTTPException(status_code=403,
                                detail="This account has been suspended. Contact "
                                       f"{BRANDING.support_email}.")
        raise HTTPException(status_code=404, detail="No account found for that email.")
    email = body.email.strip().lower()
    ratelimit.reset(key)
    return {"token": auth.make_token(email), "account": _account(email)}


@router.get("/me")
def me(email: str = Depends(current_email)) -> Dict[str, object]:
    return _account(email)


class ChangePwBody(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
def change_password(body: ChangePwBody, email: str = Depends(current_email)) -> Dict[str, object]:
    ok, reason = store.change_password(email, body.current_password, body.new_password)
    if not ok:
        if reason == "bad_password":
            raise HTTPException(status_code=401, detail="Current password is incorrect.")
        raise HTTPException(status_code=400, detail=reason)
    return {"ok": True}


class ForgotBody(BaseModel):
    email: EmailStr


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotBody, request: Request = None) -> Dict[str, object]:
    """Send a password-reset link. Always returns 200 so the endpoint cannot be used
    to enumerate registered addresses.

    The token is only ever included in the response when NO email backend is
    configured AND QGUIDE_DEV_EMAIL=1 -- so a production deployment (which has SMTP
    configured) can never leak it."""
    email = body.email.strip().lower()
    allowed, retry = ratelimit.check(f"forgot:{_client_key(request, email)}",
                                     limit=5, window_seconds=900)
    if not allowed:
        raise HTTPException(status_code=429,
                            detail=f"Too many reset requests. Try again in {retry}s.")
    exists = store.user_exists(email)
    token = auth.make_reset_token(email) if exists else None
    if exists and token:
        try:
            emailer.send_password_reset(email, token)
        except Exception:                                 # noqa: BLE001
            pass
    dev_mode = (not emailer.is_configured()
                and os.environ.get("QGUIDE_DEV_EMAIL", "") == "1")
    out: Dict[str, object] = {
        "ok": True,
        "dev_mode": dev_mode,
        "message": ("If an account exists for that address, a password reset link "
                    "has been sent."),
    }
    if dev_mode:
        out["reset_token"] = token
        out["message"] = ("Dev mode: no email backend is configured, so the reset "
                          "token is shown here instead of being emailed.")
    return out


class ResetBody(BaseModel):
    token: str
    new_password: str


@router.post("/auth/reset-password")
def reset_password(body: ResetBody) -> Dict[str, object]:
    email = auth.decode_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    ok, reason = store.reset_password(email, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    return {"ok": True, "token": auth.make_token(email), "account": _account(email)}


class ProfileBody(BaseModel):
    """Self-editable profile fields ONLY. Role, status, plan and credits are
    intentionally absent: privilege can never be changed by the account holder."""
    name: Optional[str] = None
    institution: Optional[str] = Field(default=None, max_length=255)
    research_area: Optional[str] = Field(default=None, max_length=255)


@router.patch("/account/profile")
def update_profile(body: ProfileBody, email: str = Depends(current_email)) -> Dict[str, object]:
    if store.update_profile(email, body.name, body.institution,
                            body.research_area) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return _account(email)


# --------------------------------------------------------------------------- #
# Billing / credits                                                           #
# --------------------------------------------------------------------------- #
@router.get("/billing/packages")
def packages() -> Dict[str, object]:
    return {"credits_per_run": billing.CREDITS_PER_RUN,
            "signup_bonus": billing.SIGNUP_BONUS,
            "packages": billing.CREDIT_PACKAGES}


class BuyBody(BaseModel):
    credits: int
    price: float = 0.0
    label: str = "Credit pack"


@router.post("/credits/buy")
def buy(body: BuyBody, email: str = Depends(current_email)) -> Dict[str, object]:
    if body.credits <= 0:
        raise HTTPException(status_code=400, detail="Credits must be positive.")
    store.buy_credits(email, body.credits, body.price, body.label)
    return _account(email)


# --------------------------------------------------------------------------- #
# Admin (gated by ADMIN_EMAILS)                                               #
# --------------------------------------------------------------------------- #
@router.get("/admin/users")
def admin_users(_: str = Depends(current_admin)) -> List[Dict[str, object]]:
    """Account-level user list. Includes a project COUNT per user, never project
    contents (least privilege: admins operate the platform, they do not read
    other people's research)."""
    counts = store.user_project_counts()
    users = store.list_all_users()
    for u in users:
        u["n_projects"] = counts.get(u["email"], 0)
    return users


@router.get("/admin/stats")
def admin_stats(_: str = Depends(current_admin)) -> Dict[str, object]:
    return store.admin_stats()


@router.get("/admin/activity")
def admin_activity(limit: int = 50, _: str = Depends(current_admin)) -> List[Dict[str, object]]:
    return store.admin_activity(limit)


@router.get("/admin/health")
def admin_health(_: str = Depends(current_admin)) -> Dict[str, object]:
    """Operational health: database, migrations, email backend, environment flags.
    Secrets are never included -- only whether they are configured."""
    import platform
    db = store.db_health()
    return {
        "database": db,
        "email": {"backend": "smtp" if emailer.is_configured() else "console",
                  "configured": emailer.is_configured()},
        "auth": {"jwt_secret_configured": auth.JWT_SECRET != auth.DEV_JWT_SECRET,
                 "token_ttl_days": auth.TOKEN_TTL_SECONDS // 86400},
        "cors": {"origins": [o for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o]},
        "runtime": {"python": platform.python_version(),
                    "environment": os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "unset"},
        "quantum": {"dimod_available": _dimod_available()},
    }


def _dimod_available() -> bool:
    try:
        import dimod  # noqa: F401
        return True
    except Exception:                                     # noqa: BLE001
        return False


class SetCreditsBody(BaseModel):
    email: EmailStr
    credits: int


@router.post("/admin/credits")
def admin_set_credits(body: SetCreditsBody, admin: str = Depends(current_admin)) -> Dict[str, object]:
    u = store.set_credits(body.email, body.credits, admin)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return u


class SetRoleBody(BaseModel):
    email: EmailStr
    role: str


@router.get("/admin/roles")
def admin_roles(_: str = Depends(current_admin)) -> Dict[str, object]:
    return {"roles": list(roles_mod.ASSIGNABLE_ROLES),
            "permissions": {r: roles_mod.permissions_for(r)
                            for r in roles_mod.ASSIGNABLE_ROLES}}


@router.post("/admin/role")
def admin_set_role(body: SetRoleBody,
                   admin: str = Depends(current_admin)) -> Dict[str, object]:
    """Assign a role. Guard rails: only admins reach this, and the last remaining
    admin cannot demote themselves (which would lock the instance out)."""
    role = roles_mod.normalize(body.role)
    if body.role.strip().upper() not in roles_mod.ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {body.role}")
    target = body.email.strip().lower()
    if target == admin.strip().lower() and role != roles_mod.ADMIN:
        if store.count_admins() <= 1:
            raise HTTPException(status_code=400,
                                detail="You are the only administrator — promote "
                                       "someone else before removing your own admin role.")
    u = store.set_role(target, role, admin)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return u


class SetStatusBody(BaseModel):
    email: EmailStr
    status: str


@router.post("/admin/status")
def admin_set_status(body: SetStatusBody,
                     admin: str = Depends(current_admin)) -> Dict[str, object]:
    target = body.email.strip().lower()
    if target == admin.strip().lower():
        raise HTTPException(status_code=400,
                            detail="You cannot change your own account status.")
    u = store.set_status(target, body.status, admin)
    if u is None:
        raise HTTPException(status_code=400,
                            detail="Unknown user or status (use 'active' or 'suspended').")
    return u


# --------------------------------------------------------------------------- #
# Projects                                                                     #
# --------------------------------------------------------------------------- #
@router.get("/projects")
def list_projects(email: str = Depends(current_email)) -> List[Dict[str, object]]:
    return store.list_projects_meta(email)


@router.get("/projects/{pid}")
def get_project(pid: str, email: str = Depends(current_email)) -> Dict[str, object]:
    proj = store.get_project(email, pid)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"id": proj["id"], "name": proj["name"], "created": proj["created"],
            "elapsed": proj["elapsed"], "selected_guide": proj["selected_guide"],
            "response": proj["response"]}


@router.delete("/projects/{pid}")
def remove_project(pid: str, email: str = Depends(current_email)) -> Dict[str, bool]:
    return {"deleted": store.delete_project(email, pid)}


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[str] = None
    archived: Optional[bool] = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, email: str = Depends(current_email)) -> Dict[str, bool]:
    done = False
    if body.name is not None:
        done = store.rename_project(email, pid, body.name) or done
    if body.folder_id is not None or (body.folder_id is None and "folder_id" in body.model_fields_set):
        done = store.move_project(email, pid, body.folder_id) or done
    if body.archived is not None:
        done = store.set_archived(email, pid, body.archived) or done
    if not done:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"ok": True}


@router.get("/folders")
def list_folders(email: str = Depends(current_email)) -> List[Dict[str, object]]:
    return store.list_folders(email)


class FolderBody(BaseModel):
    name: str
    parent_id: Optional[str] = None


@router.post("/folders")
def create_folder(body: FolderBody, email: str = Depends(current_email)) -> Dict[str, object]:
    return store.create_folder(email, body.name, body.parent_id)


class FolderRenameBody(BaseModel):
    name: str


@router.patch("/folders/{fid}")
def rename_folder(fid: str, body: FolderRenameBody, email: str = Depends(current_email)) -> Dict[str, bool]:
    if not store.rename_folder(email, fid, body.name):
        raise HTTPException(status_code=404, detail="Folder not found.")
    return {"ok": True}


@router.delete("/folders/{fid}")
def delete_folder(fid: str, email: str = Depends(current_email)) -> Dict[str, bool]:
    if not store.delete_folder(email, fid):
        raise HTTPException(status_code=404, detail="Folder not found.")
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Run (auth + credit gated): the React app's main action                      #
# --------------------------------------------------------------------------- #
class RunBody(BaseModel):
    request: DesignRequest


@router.post("/run")
def run(body: RunBody, email: str = Depends(current_email)) -> Dict[str, object]:
    req = body.request
    if not req.sequence.strip():
        raise HTTPException(status_code=400, detail="Empty sequence.")
    user = store.get_user(email)
    if user["credits"] < billing.CREDITS_PER_RUN:
        raise HTTPException(status_code=402, detail="Insufficient credits.")

    t0 = time.perf_counter()
    resp = pipeline.run_design(req)
    elapsed = round(time.perf_counter() - t0, 3)
    if not resp.guides:
        raise HTTPException(status_code=400, detail="No guides found for this sequence / PAM.")

    balance = store.charge_run(email, billing.CREDITS_PER_RUN,
                               f"Design run: {req.gene_name or 'untitled'}")
    if balance is None:
        raise HTTPException(status_code=402, detail="Insufficient credits.")

    pid = store.next_pid(email)
    from datetime import datetime
    proj = {"id": pid, "name": req.gene_name or "untitled",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "elapsed": elapsed,
            "selected_guide": resp.best_single_guide_id, "request": req, "response": resp}
    store.save_project(email, proj)
    return {"project_id": pid, "balance": balance, "elapsed": elapsed,
            "name": proj["name"], "created": proj["created"], "response": resp}
