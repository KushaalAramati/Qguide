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

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr

from qguide.app import auth, billing, store

# Admin allowlist: set ADMIN_EMAILS (comma-separated) on the server.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def is_admin(email: str) -> bool:
    return (email or "").strip().lower() in ADMIN_EMAILS
from qguide.app.schemas import DesignRequest, DesignResponse, Guide
from qguide.core import optimization, pipeline
from qguide.core.explainability import assumptions
from qguide.core.guide_generator import CAS_PROFILES

router = APIRouter()


# --------------------------------------------------------------------------- #
# Auth dependency                                                              #
# --------------------------------------------------------------------------- #
def current_email(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    email = auth.decode_token(authorization.split(" ", 1)[1])
    if not email or store.get_user(email) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return email


def current_admin(email: str = Depends(current_email)) -> str:
    if not is_admin(email):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return email


def _account(email: str) -> Optional[Dict]:
    """Account summary + the is_admin flag (so the UI can show admin tools)."""
    a = store.account_summary(email)
    if a is not None:
        a["is_admin"] = is_admin(email)
    return a


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "q-guide", "version": "1.0"}


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


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/signup")
def signup(body: SignupBody) -> Dict[str, object]:
    ok, msg = store.create_user(body.name, body.email, body.password, billing.SIGNUP_BONUS)
    if not ok:
        raise HTTPException(status_code=409, detail=msg)
    email = body.email.strip().lower()
    store.touch_login(email)
    return {"token": auth.make_token(email), "account": _account(email)}


@router.post("/auth/login")
def login(body: LoginBody) -> Dict[str, object]:
    ok, reason = store.authenticate(body.email, body.password)
    if not ok:
        # Distinct codes so the UI can show a precise message.
        if reason == "bad_password":
            raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
        raise HTTPException(status_code=404, detail="No account found for that email.")
    email = body.email.strip().lower()
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
def forgot_password(body: ForgotBody) -> Dict[str, object]:
    """DEV MODE: no email provider is configured, so the reset token is returned in
    the response (clearly labelled). In production this token would be emailed and
    NEVER returned to the client."""
    email = body.email.strip().lower()
    exists = store.user_exists(email)
    token = auth.make_reset_token(email) if exists else None
    # Always return 200 (do not leak which emails exist).
    return {"ok": True, "dev_mode": True,
            "message": "Reset link generated. (Dev mode: no email is sent — token returned below.)",
            "reset_token": token}


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
    name: str


@router.patch("/account/profile")
def update_profile(body: ProfileBody, email: str = Depends(current_email)) -> Dict[str, object]:
    if store.update_profile(email, body.name) is None:
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
    return store.list_all_users()


class SetCreditsBody(BaseModel):
    email: EmailStr
    credits: int


@router.post("/admin/credits")
def admin_set_credits(body: SetCreditsBody, admin: str = Depends(current_admin)) -> Dict[str, object]:
    u = store.set_credits(body.email, body.credits, admin)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
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
