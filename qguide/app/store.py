"""
Persistence layer for accounts, credits, transactions and projects.

SQLAlchemy ORM over the engine in `db.py` (SQLite locally, Postgres on Render).
Passwords are salted PBKDF2-HMAC-SHA256 hashes -- never plaintext. Projects are
stored as JSON (Pydantic round-trip); transient caches are recomputed on demand.

Two surfaces share these tables:
  * the Streamlit app uses create_user / authenticate / load_account /
    persist_counters / add_transaction / save_project,
  * the FastAPI backend uses the atomic helpers (charge_run / buy_credits /
    next_pid / get_user / list_projects_meta / get_project).
"""
from __future__ import annotations

import binascii
import hashlib
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import uuid

from sqlalchemy import Column, Float, Index, Integer, String, Text, select, text

from qguide.app import roles as roles_mod
from qguide.app.db import Base, engine, session_scope
from qguide.app.migrations import run_migrations
from qguide.app.schemas import DesignRequest, DesignResponse


# --------------------------------------------------------------------------- #
# Models                                                                        #
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"
    email = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    pw_salt = Column(String(64), nullable=False)
    pw_hash = Column(String(128), nullable=False)
    plan = Column(String(64), nullable=False, default="Free trial")
    credits = Column(Integer, nullable=False, default=0)
    runs = Column(Integer, nullable=False, default=0)
    counter = Column(Integer, nullable=False, default=0)
    fcounter = Column(Integer, default=0)
    created = Column(String(32), nullable=False)
    last_login = Column(String(32))
    # --- access control / profile (see migrations 0002) ---
    role = Column(String(32), nullable=False, default=roles_mod.USER)
    status = Column(String(16), nullable=False, default="active")
    institution = Column(String(255))
    research_area = Column(String(255))
    terms_accepted_at = Column(String(32))
    terms_version = Column(String(16))
    # --- onboarding (migration 0003): shown once, replayable from Settings ---
    onboarding_completed = Column(Integer, nullable=False, default=0)
    onboarding_step = Column(Integer, nullable=False, default=0)
    onboarding_completed_at = Column(String(32))
    # --- notification preferences, JSON (migration 0007) ---
    notification_prefs = Column(Text)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    ts = Column(String(32), nullable=False)
    type = Column(String(32), nullable=False)
    amount = Column(Integer, nullable=False)
    balance = Column(Integer, nullable=False)
    descr = Column(Text, nullable=False)
    price = Column(Float, nullable=False, default=0.0)


class Project(Base):
    __tablename__ = "projects"
    email = Column(String(255), primary_key=True)
    pid = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    created = Column(String(32), nullable=False)
    elapsed = Column(Float, nullable=False)
    selected_guide = Column(String(64))
    n_guides = Column(Integer)
    best_guide = Column(String(64))
    request_json = Column(Text, nullable=False)
    response_json = Column(Text, nullable=False)
    folder_id = Column(String(32))          # nullable -> "unfiled"
    archived = Column(Integer, default=0)   # 0 = active, 1 = archived (soft state)
    # Global identity (migration 0004). `email`+`pid` stays the owner's short
    # handle; `uid` is what collaborators address the project by.
    uid = Column(String(36), index=True)
    # Research metadata (migration 0006). Organism/nuclease/outcome live in the
    # stored request; these are the human annotations around it.
    experiment_name = Column(String(255))
    cell_line = Column(String(255))
    target_gene = Column(String(255))
    experiment_type = Column(String(64))
    notes = Column(Text)
    tags = Column(Text)             # JSON list of strings
    citations = Column(Text)        # JSON list of {"label","url"|"doi"}
    metadata_updated = Column(String(32))
    metadata_updated_by = Column(String(255))


class AnalysisTemplate(Base):
    """Saved DesignRequest parameters (everything except the sequence) so a
    researcher can re-apply a validated configuration to new targets."""
    __tablename__ = "analysis_templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_email = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    params_json = Column(Text, nullable=False)
    created = Column(String(32), nullable=False)
    updated = Column(String(32), nullable=False)


class ProjectMembership(Base):
    """Who, besides the owner, can open a project and what they may do.

    Roles: OWNER (implicit -- the project row's `email`; an OWNER row is never
    stored), EDITOR, VIEWER. See `qguide.app.access` for the permission rules.
    """
    __tablename__ = "project_memberships"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_uid = Column(String(36), nullable=False, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    invited_by = Column(String(255))
    created = Column(String(32), nullable=False)
    __table_args__ = (Index("ix_membership_project_user", "project_uid", "user_email",
                            unique=True),)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String(255), nullable=False, index=True)
    type = Column(String(48), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    link = Column(String(512))
    read = Column(Integer, nullable=False, default=0)
    created = Column(String(32), nullable=False)


class Folder(Base):
    __tablename__ = "folders"
    email = Column(String(255), primary_key=True)
    fid = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    parent_fid = Column(String(32))         # nullable -> top level; supports subfolders
    created = Column(String(32), nullable=False)
    fcounter_placeholder = Column(Integer, default=0)


_DB_READY = False


def init_db(force: bool = False) -> None:
    """Create tables and run pending migrations. Cheap to call repeatedly: the
    work is done once per process unless `force` is set."""
    global _DB_READY
    if _DB_READY and not force:
        return
    Base.metadata.create_all(engine)
    run_migrations(engine)
    _DB_READY = True


def _migrate() -> None:
    """Deprecated alias kept for callers outside this package."""
    run_migrations(engine)


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #
def _hash(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 100_000).hex()


def _make_pw(pw: str) -> Tuple[str, str]:
    salt = os.urandom(16)
    return binascii.hexlify(salt).decode(), _hash(pw, salt)


def _check_pw(pw: str, salt_hex: str, hash_hex: str) -> bool:
    return _hash(pw, binascii.unhexlify(salt_hex)) == hash_hex


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


MIN_PASSWORD_LENGTH = 8


def validate_password(pw: str) -> Tuple[bool, str]:
    """Single source of truth for the password policy (signup, change, reset)."""
    pw = pw or ""
    if len(pw) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if pw.isdigit() or pw.isalpha():
        return False, "Password must contain both letters and numbers."
    if pw.lower() in {"password", "password1", "12345678", "qwertyui"}:
        return False, "That password is too common. Please choose another."
    return True, "ok"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def _user_dict(u: User) -> Dict:
    role = roles_mod.normalize(getattr(u, "role", None))
    return {"name": u.name, "email": u.email, "plan": u.plan, "credits": u.credits,
            "runs": u.runs, "counter": u.counter, "created": u.created,
            "last_login": u.last_login,
            "role": role,
            "status": getattr(u, "status", None) or "active",
            "institution": getattr(u, "institution", None),
            "research_area": getattr(u, "research_area", None),
            "terms_accepted_at": getattr(u, "terms_accepted_at", None),
            "onboarding": {"completed": bool(getattr(u, "onboarding_completed", 0) or 0),
                           "step": int(getattr(u, "onboarding_step", 0) or 0),
                           "completed_at": getattr(u, "onboarding_completed_at", None)},
            "permissions": roles_mod.permissions_for(role)}


def _tx_dict(t: Transaction) -> Dict:
    return {"ts": t.ts, "type": t.type, "amount": t.amount, "balance": t.balance,
            "desc": t.descr, "price": t.price}


# --------------------------------------------------------------------------- #
# Accounts                                                                      #
# --------------------------------------------------------------------------- #
def create_user(name: str, email: str, password: str, bonus: int,
                *, institution: Optional[str] = None,
                research_area: Optional[str] = None,
                terms_version: Optional[str] = None,
                accepted_terms: bool = False) -> Tuple[bool, str]:
    """Create an account. The role is NEVER taken from the caller: new accounts are
    always USER unless the email is in the environment-configured admin allowlist."""
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not name or not email or not password:
        return False, "Please fill in name, email and password."
    if not validate_email(email):
        return False, "Please enter a valid email address."
    ok, why = validate_password(password)
    if not ok:
        return False, why
    init_db()
    role = (roles_mod.ADMIN if email in roles_mod.bootstrap_admin_emails()
            else roles_mod.USER)
    with session_scope() as s:
        if s.get(User, email):
            return False, "An account with that email already exists — sign in instead."
        salt, h = _make_pw(password)
        now = _now()
        s.add(User(email=email, name=name, pw_salt=salt, pw_hash=h, plan="Free trial",
                   credits=bonus, runs=0, counter=0, created=now,
                   role=role, status="active",
                   institution=(institution or None), research_area=(research_area or None),
                   terms_accepted_at=(now if accepted_terms else None),
                   terms_version=(terms_version if accepted_terms else None)))
        s.add(Transaction(email=email, ts=now, type="bonus", amount=bonus,
                          balance=bonus, descr="Welcome bonus", price=0.0))
    return True, "Account created."


def authenticate(email: str, password: str) -> Tuple[bool, str]:
    """Returns (ok, reason). reason is 'no_user' or 'bad_password' on failure so
    the UI can show a precise message."""
    email = (email or "").strip().lower()
    init_db()
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return False, "no_user"
        if not _check_pw(password, u.pw_salt, u.pw_hash):
            return False, "bad_password"
        if (getattr(u, "status", "active") or "active") != "active":
            return False, "suspended"
        # Environment-configured admins are promoted on sign-in (bootstrap path);
        # this is the only automatic role change in the system.
        if email in roles_mod.bootstrap_admin_emails() and \
                roles_mod.normalize(u.role) != roles_mod.ADMIN:
            u.role = roles_mod.ADMIN
        u.last_login = _now()
    return True, "ok"


def touch_login(email: str) -> None:
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        if u:
            u.last_login = _now()


# --------------------------------------------------------------------------- #
# Admin                                                                         #
# --------------------------------------------------------------------------- #
def list_all_users() -> List[Dict]:
    with session_scope() as s:
        users = s.scalars(select(User).order_by(User.created.desc())).all()
        return [_user_dict(u) for u in users]


def set_credits(email: str, credits: int, admin_email: str) -> Optional[Dict]:
    """Set a user's balance to an absolute value (admin action), logged."""
    email = (email or "").strip().lower()
    credits = max(0, int(credits))
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        delta = credits - u.credits
        u.credits = credits
        s.add(Transaction(email=email, ts=_now(), type="admin", amount=delta,
                          balance=credits, descr=f"Admin set by {admin_email}", price=0.0))
        return _user_dict(u)


def get_user(email: str) -> Optional[Dict]:
    init_db()
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        return _user_dict(u) if u else None


def account_summary(email: str) -> Optional[Dict]:
    """User fields + transaction ledger (no heavy project payloads)."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        txs = s.scalars(select(Transaction).where(Transaction.email == email)
                        .order_by(Transaction.id)).all()
        d = _user_dict(u)
        d["transactions"] = [_tx_dict(t) for t in txs]
        return d


def add_transaction(email: str, ttype: str, amount: int, balance: int,
                    desc: str, price: float = 0.0) -> None:
    with session_scope() as s:
        s.add(Transaction(email=(email or "").strip().lower(), ts=_now(), type=ttype,
                          amount=amount, balance=balance, descr=desc, price=price))


def persist_counters(email: str, credits: int, plan: str, runs: int, counter: int) -> None:
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        if u:
            u.credits, u.plan, u.runs, u.counter = credits, plan, runs, counter


# --- Atomic helpers (preferred for the API) --------------------------------- #
def charge_run(email: str, cost: int, desc: str) -> Optional[int]:
    """Atomically check balance, deduct `cost`, bump runs, log usage.
    Returns the new balance, or None if the user can't afford it."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u or u.credits < cost:
            return None
        u.credits -= cost
        u.runs += 1
        s.add(Transaction(email=email, ts=_now(), type="usage", amount=-cost,
                          balance=u.credits, descr=desc, price=0.0))
        return u.credits


def buy_credits(email: str, amount: int, price: float, label: str) -> Optional[int]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        u.credits += amount
        if u.plan == "Free trial":
            u.plan = "Pay-as-you-go"
        s.add(Transaction(email=email, ts=_now(), type="purchase", amount=amount,
                          balance=u.credits, descr=label, price=price))
        return u.credits


def next_pid(email: str) -> str:
    """Atomically increment the per-user project counter and return a new id."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        u.counter += 1
        return f"P{u.counter:03d}"


# --------------------------------------------------------------------------- #
# Projects                                                                      #
# --------------------------------------------------------------------------- #
def save_project(email: str, proj: Dict) -> None:
    email = (email or "").strip().lower()
    resp, req = proj["response"], proj["request"]
    with session_scope() as s:
        existing = s.get(Project, {"email": email, "pid": proj["id"]})
        if existing:
            existing.name = proj["name"]
            existing.selected_guide = proj.get("selected_guide")
            existing.response_json = resp.model_dump_json()
        else:
            s.add(Project(email=email, pid=proj["id"], name=proj["name"],
                          created=proj["created"], elapsed=proj["elapsed"],
                          selected_guide=proj.get("selected_guide"),
                          n_guides=len(resp.guides), best_guide=resp.best_single_guide_id,
                          request_json=req.model_dump_json(),
                          response_json=resp.model_dump_json(),
                          uid=proj.get("uid") or uuid.uuid4().hex))


def list_projects_meta(email: str, include_archived: bool = True) -> List[Dict]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        rows = s.scalars(select(Project).where(Project.email == email)
                         .order_by(Project.pid.desc())).all()
        out = []
        for p in rows:
            arch = bool(getattr(p, "archived", 0) or 0)
            if arch and not include_archived:
                continue
            out.append(_meta(p, arch))
        return out


def _meta(p: Project, arch: Optional[bool] = None) -> Dict:
    if arch is None:
        arch = bool(getattr(p, "archived", 0) or 0)
    return {"id": p.pid, "uid": getattr(p, "uid", None), "name": p.name, "created": p.created,
            "elapsed": p.elapsed, "n_guides": p.n_guides, "best_guide": p.best_guide,
            "folder_id": getattr(p, "folder_id", None), "archived": arch,
            "owner_email": p.email}


def _reconstruct(p: Project) -> Dict:
    return {"id": p.pid, "uid": getattr(p, "uid", None), "owner_email": p.email,
            "name": p.name, "created": p.created, "elapsed": p.elapsed,
            "selected_guide": p.selected_guide,
            "request": DesignRequest.model_validate_json(p.request_json),
            "response": DesignResponse.model_validate_json(p.response_json),
            "pred": None, "pred_cmp": None, "sim_results": None}


def get_project(email: str, pid: str) -> Optional[Dict]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        p = s.get(Project, {"email": email, "pid": pid})
        return _reconstruct(p) if p else None


def delete_project(email: str, pid: str) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        p = s.get(Project, {"email": email, "pid": pid})
        if not p:
            return False
        s.delete(p)
        return True


def load_account(email: str) -> Optional[Dict]:
    """Full account incl. all reconstructed projects (used by the Streamlit app)."""
    email = (email or "").strip().lower()
    summary = account_summary(email)
    if summary is None:
        return None
    summary["projects"] = {}
    with session_scope() as s:
        rows = s.scalars(select(Project).where(Project.email == email)).all()
        for p in rows:
            try:
                summary["projects"][p.pid] = _reconstruct(p)
            except Exception:
                continue
    return summary


# --------------------------------------------------------------------------- #
# Password management (change / reset)                                          #
# --------------------------------------------------------------------------- #
def change_password(email: str, current: str, new: str) -> Tuple[bool, str]:
    email = (email or "").strip().lower()
    ok, why = validate_password(new)
    if not ok:
        return False, why
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return False, "no_user"
        if not _check_pw(current, u.pw_salt, u.pw_hash):
            return False, "bad_password"
        salt, h = _make_pw(new)
        u.pw_salt, u.pw_hash = salt, h
    return True, "ok"


def reset_password(email: str, new: str) -> Tuple[bool, str]:
    """Set a new password without the old one (used by a verified reset token)."""
    email = (email or "").strip().lower()
    ok, why = validate_password(new)
    if not ok:
        return False, why
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return False, "no_user"
        salt, h = _make_pw(new)
        u.pw_salt, u.pw_hash = salt, h
    return True, "ok"


def user_exists(email: str) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        return s.get(User, email) is not None


def update_profile(email: str, name: Optional[str] = None,
                   institution: Optional[str] = None,
                   research_area: Optional[str] = None) -> Optional[Dict]:
    """Self-service profile edit. Deliberately narrow: role, status, plan and
    credits are NOT editable here, so a user can never escalate their own access."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        if name is not None and name.strip():
            u.name = name.strip()
        if institution is not None:
            u.institution = institution.strip() or None
        if research_area is not None:
            u.research_area = research_area.strip() or None
        return _user_dict(u)


# --------------------------------------------------------------------------- #
# Folders + project organisation                                               #
# --------------------------------------------------------------------------- #
def next_fid(email: str) -> str:
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        u.fcounter = (getattr(u, "fcounter", 0) or 0) + 1
        return f"F{u.fcounter:03d}"


def list_folders(email: str) -> List[Dict]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        rows = s.scalars(select(Folder).where(Folder.email == email)
                         .order_by(Folder.fid)).all()
        return [{"id": f.fid, "name": f.name, "parent_id": f.parent_fid,
                 "created": f.created} for f in rows]


def create_folder(email: str, name: str, parent_id: Optional[str] = None) -> Dict:
    email = (email or "").strip().lower()
    fid = next_fid(email)
    with session_scope() as s:
        s.add(Folder(email=email, fid=fid, name=(name or "New folder").strip(),
                     parent_fid=parent_id, created=_now()))
    return {"id": fid, "name": (name or "New folder").strip(), "parent_id": parent_id}


def rename_folder(email: str, fid: str, name: str) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        f = s.get(Folder, {"email": email, "fid": fid})
        if not f:
            return False
        f.name = (name or f.name).strip()
        return True


def delete_folder(email: str, fid: str) -> bool:
    """Delete a folder; its projects and subfolders are moved to the parent (unfiled
    if top-level). Non-destructive to scientific work."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        f = s.get(Folder, {"email": email, "fid": fid})
        if not f:
            return False
        parent = f.parent_fid
        for sub in s.scalars(select(Folder).where(Folder.email == email,
                                                   Folder.parent_fid == fid)).all():
            sub.parent_fid = parent
        for p in s.scalars(select(Project).where(Project.email == email,
                                                 Project.folder_id == fid)).all():
            p.folder_id = parent
        s.delete(f)
        return True


def move_project(email: str, pid: str, folder_id: Optional[str]) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        p = s.get(Project, {"email": email, "pid": pid})
        if not p:
            return False
        p.folder_id = folder_id or None
        return True


def rename_project(email: str, pid: str, name: str) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        p = s.get(Project, {"email": email, "pid": pid})
        if not p:
            return False
        p.name = (name or p.name).strip()
        return True


def set_archived(email: str, pid: str, archived: bool) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        p = s.get(Project, {"email": email, "pid": pid})
        if not p:
            return False
        p.archived = 1 if archived else 0
        return True


# --- Roles, account status and admin analytics ------------------------------ #
def get_role(email: str) -> str:
    """Authoritative role lookup -- always read from the database, never from a
    token claim or a request body."""
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        return roles_mod.normalize(getattr(u, "role", None)) if u else roles_mod.USER


def get_status(email: str) -> Optional[str]:
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        return (getattr(u, "status", "active") or "active") if u else None


def set_role(email: str, role: str, actor_email: str) -> Optional[Dict]:
    """Assign a role (admin action). Returns the updated user, or None if unknown."""
    email = (email or "").strip().lower()
    role = roles_mod.normalize(role)
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        u.role = role
        s.add(Transaction(email=email, ts=_now(), type="admin", amount=0,
                          balance=u.credits,
                          descr=f"Role set to {role} by {actor_email}", price=0.0))
        return _user_dict(u)


def set_status(email: str, status: str, actor_email: str) -> Optional[Dict]:
    status = (status or "").strip().lower()
    if status not in ("active", "suspended"):
        return None
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        u.status = status
        s.add(Transaction(email=email, ts=_now(), type="admin", amount=0,
                          balance=u.credits,
                          descr=f"Account {status} by {actor_email}", price=0.0))
        return _user_dict(u)


def count_admins() -> int:
    with session_scope() as s:
        return len([u for u in s.scalars(select(User)).all()
                    if roles_mod.normalize(getattr(u, "role", None)) == roles_mod.ADMIN])


def ensure_bootstrap_admins() -> List[str]:
    """Promote every ADMIN_EMAILS address that already has an account. Called at
    startup so a fresh deployment has an administrator without any UI action."""
    wanted = roles_mod.bootstrap_admin_emails()
    if not wanted:
        return []
    promoted = []
    with session_scope() as s:
        for email in wanted:
            u = s.get(User, email)
            if u and roles_mod.normalize(getattr(u, "role", None)) != roles_mod.ADMIN:
                u.role = roles_mod.ADMIN
                promoted.append(email)
    return promoted


# --------------------------------------------------------------------------- #
# Admin analytics (account-level only -- never project contents)               #
# --------------------------------------------------------------------------- #
def _cutoff(days: int) -> str:
    from datetime import timedelta
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")


def admin_stats() -> Dict:
    """Aggregate platform statistics for the admin dashboard. Deliberately limited
    to account/usage metadata: no sequences, results or project names leave here."""
    from sqlalchemy import func
    d7, d30 = _cutoff(7), _cutoff(30)
    with session_scope() as s:
        users = s.scalars(select(User)).all()
        n_users = len(users)
        active_30 = sum(1 for u in users if (u.last_login or "") >= d30)
        active_7 = sum(1 for u in users if (u.last_login or "") >= d7)
        new_7 = sum(1 for u in users if (u.created or "") >= d7)
        new_30 = sum(1 for u in users if (u.created or "") >= d30)
        suspended = sum(1 for u in users if (getattr(u, "status", "active") or "active") != "active")
        by_plan: Dict[str, int] = {}
        by_role: Dict[str, int] = {}
        for u in users:
            by_plan[u.plan] = by_plan.get(u.plan, 0) + 1
            r = roles_mod.normalize(getattr(u, "role", None))
            by_role[r] = by_role.get(r, 0) + 1

        n_projects = s.scalar(select(func.count()).select_from(Project)) or 0
        projects_30 = s.scalar(select(func.count()).select_from(Project)
                               .where(Project.created >= d30)) or 0
        projects_7 = s.scalar(select(func.count()).select_from(Project)
                              .where(Project.created >= d7)) or 0
        total_runs = sum(u.runs for u in users)
        credits_out = sum(u.credits for u in users)
        purchases = s.scalars(select(Transaction).where(Transaction.type == "purchase")).all()
        revenue = round(sum(t.price or 0.0 for t in purchases), 2)
        revenue_30 = round(sum(t.price or 0.0 for t in purchases if t.ts >= d30), 2)

        recent = sorted(users, key=lambda u: u.created or "", reverse=True)[:10]
        recent_signups = [{"name": u.name, "email": u.email, "created": u.created,
                           "plan": u.plan, "role": roles_mod.normalize(getattr(u, "role", None))}
                          for u in recent]

        # 12-week signup / project series for a small trend chart.
        from datetime import timedelta
        weeks = []
        now = datetime.now()
        for i in range(11, -1, -1):
            start = (now - timedelta(days=7 * (i + 1))).strftime("%Y-%m-%d %H:%M")
            end = (now - timedelta(days=7 * i)).strftime("%Y-%m-%d %H:%M")
            weeks.append({
                "week_ending": end[:10],
                "signups": sum(1 for u in users if start <= (u.created or "") < end),
                "projects": int(s.scalar(select(func.count()).select_from(Project)
                                         .where(Project.created >= start,
                                                Project.created < end)) or 0),
            })

    return {
        "users": {"total": n_users, "active_7d": active_7, "active_30d": active_30,
                  "new_7d": new_7, "new_30d": new_30, "suspended": suspended},
        "projects": {"total": int(n_projects), "new_7d": int(projects_7),
                     "new_30d": int(projects_30)},
        "usage": {"total_runs": total_runs, "credits_in_circulation": credits_out},
        "billing": {"revenue_total": revenue, "revenue_30d": revenue_30,
                    "purchases": len(purchases), "users_by_plan": by_plan},
        "users_by_role": by_role,
        "recent_signups": recent_signups,
        "weekly": weeks,
    }


def admin_activity(limit: int = 50) -> List[Dict]:
    """Recent platform activity from the ledger (runs, purchases, admin actions).
    Descriptions are already free of sequence data; project names are not included."""
    limit = max(1, min(int(limit), 200))
    with session_scope() as s:
        rows = s.scalars(select(Transaction).order_by(Transaction.id.desc())
                         .limit(limit)).all()
        return [{"ts": t.ts, "email": t.email, "type": t.type, "amount": t.amount,
                 "balance": t.balance, "price": t.price,
                 # usage descriptions embed the gene name -> keep only the kind
                 "desc": ("Design run" if t.type == "usage" else t.descr)}
                for t in rows]


def user_project_counts() -> Dict[str, int]:
    from sqlalchemy import func
    with session_scope() as s:
        rows = s.execute(select(Project.email, func.count()).group_by(Project.email)).all()
        return {email: int(n) for email, n in rows}


def db_health() -> Dict:
    """Cheap liveness probe + migration version for the admin health panel."""
    from sqlalchemy import text as _text
    out: Dict = {"ok": False, "dialect": engine.dialect.name, "migration_version": None}
    try:
        with engine.connect() as conn:
            conn.execute(_text("SELECT 1"))
            v = conn.execute(_text("SELECT MAX(version) FROM schema_migrations")).scalar()
        out["ok"] = True
        out["migration_version"] = int(v) if v is not None else 0
    except Exception as exc:                              # noqa: BLE001
        out["error"] = str(exc)[:200]
    return out


# --------------------------------------------------------------------------- #
# Onboarding                                                                    #
# --------------------------------------------------------------------------- #
def get_onboarding(email: str) -> Optional[Dict]:
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        return _user_dict(u)["onboarding"] if u else None


def update_onboarding(email: str, step: Optional[int] = None,
                      completed: Optional[bool] = None) -> Optional[Dict]:
    """Persist tour progress. `completed=True` marks it done (Finish or Skip);
    `completed=False` resets it so the tour replays on the next visit."""
    with session_scope() as s:
        u = s.get(User, (email or "").strip().lower())
        if not u:
            return None
        if step is not None:
            u.onboarding_step = max(0, int(step))
        if completed is not None:
            u.onboarding_completed = 1 if completed else 0
            u.onboarding_completed_at = _now() if completed else None
            if not completed:
                u.onboarding_step = 0
        return _user_dict(u)["onboarding"]


# --------------------------------------------------------------------------- #
# Collaboration: project lookup by global id, memberships                       #
# --------------------------------------------------------------------------- #
def _find_project(s, email: str, ident: str) -> Optional[Project]:
    """Resolve `ident` as a global uid first, then as the caller's own pid."""
    ident = (ident or "").strip()
    if not ident:
        return None
    p = s.scalars(select(Project).where(Project.uid == ident)).first()
    if p is not None:
        return p
    return s.get(Project, {"email": email, "pid": ident})


def resolve_project(email: str, ident: str) -> Optional[Dict]:
    """Metadata for a project addressed by uid or (own) pid -- no payloads."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        p = _find_project(s, email, ident)
        return _meta(p) if p else None


def get_project_by_uid(uid: str) -> Optional[Dict]:
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        return _reconstruct(p) if p else None


def membership_role(uid: str, email: str) -> Optional[str]:
    """EDITOR / VIEWER for a collaborator, None otherwise (owner is not stored)."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        m = s.scalars(select(ProjectMembership).where(
            ProjectMembership.project_uid == uid,
            ProjectMembership.user_email == email)).first()
        return m.role if m else None


def list_members(uid: str) -> List[Dict]:
    """Owner first, then collaborators, with display names."""
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        if p is None:
            return []
        rows = s.scalars(select(ProjectMembership).where(
            ProjectMembership.project_uid == uid).order_by(ProjectMembership.id)).all()
        emails = [p.email] + [m.user_email for m in rows]
        users = {u.email: u for u in s.scalars(select(User).where(User.email.in_(emails))).all()}
        out = [{"email": p.email, "name": users[p.email].name if p.email in users else p.email,
                "role": "OWNER", "invited_by": None, "created": p.created}]
        for m in rows:
            u = users.get(m.user_email)
            out.append({"email": m.user_email, "name": u.name if u else m.user_email,
                        "role": m.role, "invited_by": m.invited_by, "created": m.created})
        return out


def upsert_member(uid: str, email: str, role: str, invited_by: str) -> Dict:
    email = (email or "").strip().lower()
    with session_scope() as s:
        m = s.scalars(select(ProjectMembership).where(
            ProjectMembership.project_uid == uid,
            ProjectMembership.user_email == email)).first()
        created = m is None
        if m is None:
            m = ProjectMembership(project_uid=uid, user_email=email, role=role,
                                  invited_by=invited_by, created=_now())
            s.add(m)
        else:
            m.role = role
        return {"email": email, "role": role, "created": created}


def remove_member(uid: str, email: str) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        m = s.scalars(select(ProjectMembership).where(
            ProjectMembership.project_uid == uid,
            ProjectMembership.user_email == email)).first()
        if m is None:
            return False
        s.delete(m)
        return True


def remove_all_members(uid: str) -> None:
    with session_scope() as s:
        for m in s.scalars(select(ProjectMembership).where(
                ProjectMembership.project_uid == uid)).all():
            s.delete(m)


def list_shared_projects(email: str) -> List[Dict]:
    """Projects shared WITH `email` (metadata + the caller's role + owner name)."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        rows = s.execute(select(ProjectMembership, Project).join(
            Project, Project.uid == ProjectMembership.project_uid).where(
            ProjectMembership.user_email == email).order_by(ProjectMembership.id.desc())).all()
        owners = {p.email for _, p in rows}
        names = {u.email: u.name for u in s.scalars(select(User).where(User.email.in_(owners))).all()} if owners else {}
        out = []
        for m, p in rows:
            d = _meta(p)
            d.update({"role": m.role, "shared": True, "owner_name": names.get(p.email, p.email),
                      "folder_id": None, "archived": False})
            out.append(d)
        return out


def member_counts(owner_email: str) -> Dict[str, int]:
    """uid -> number of collaborators, for the owner's projects."""
    from sqlalchemy import func
    owner_email = (owner_email or "").strip().lower()
    with session_scope() as s:
        rows = s.execute(select(ProjectMembership.project_uid, func.count()).join(
            Project, Project.uid == ProjectMembership.project_uid).where(
            Project.email == owner_email).group_by(ProjectMembership.project_uid)).all()
        return {uid: int(n) for uid, n in rows}


def update_project_result(uid: str, resp: DesignResponse, elapsed: float) -> bool:
    """Replace a project's stored result after an editor re-runs it in place."""
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        if p is None:
            return False
        p.response_json = resp.model_dump_json()
        p.elapsed = elapsed
        p.n_guides = len(resp.guides)
        p.best_guide = resp.best_single_guide_id
        if p.selected_guide not in {g.guide_id for g in resp.guides}:
            p.selected_guide = resp.best_single_guide_id
        return True


def set_selected_guide(uid: str, guide_id: str) -> bool:
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        if p is None:
            return False
        p.selected_guide = guide_id
        return True


def rename_project_uid(uid: str, name: str) -> bool:
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        if p is None:
            return False
        p.name = (name or p.name).strip()
        return True


def delete_project_uid(uid: str) -> bool:
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        if p is None:
            return False
        for m in s.scalars(select(ProjectMembership).where(
                ProjectMembership.project_uid == uid)).all():
            s.delete(m)
        s.delete(p)
        return True


def lookup_user(email: str) -> Optional[Dict]:
    """Minimal public profile for the invite dialog (exact email match only)."""
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u or (getattr(u, "status", "active") or "active") != "active":
            return None
        return {"email": u.email, "name": u.name, "institution": getattr(u, "institution", None)}


# --------------------------------------------------------------------------- #
# Notifications (API surface lands with the notifications phase)               #
# --------------------------------------------------------------------------- #
def add_notification(email: str, ntype: str, title: str, message: str = "",
                     link: Optional[str] = None) -> int:
    email = (email or "").strip().lower()
    prefs = get_notification_prefs(email)
    if prefs.get(_pref_key(ntype)) is False:
        return 0
    with session_scope() as s:
        n = Notification(user_email=email, type=ntype, title=title[:255], message=message,
                         link=link, read=0, created=_now())
        s.add(n)
        s.flush()
        return int(n.id)


# --------------------------------------------------------------------------- #
# Research tools: project metadata, templates                                  #
# --------------------------------------------------------------------------- #
METADATA_FIELDS = ("experiment_name", "cell_line", "target_gene", "experiment_type", "notes")


def _loads(v, default):
    try:
        return json.loads(v) if v else default
    except Exception:                                     # noqa: BLE001
        return default


def project_metadata(p: Project) -> Dict:
    return {
        "experiment_name": getattr(p, "experiment_name", None),
        "cell_line": getattr(p, "cell_line", None),
        "target_gene": getattr(p, "target_gene", None),
        "experiment_type": getattr(p, "experiment_type", None),
        "notes": getattr(p, "notes", None) or "",
        "tags": _loads(getattr(p, "tags", None), []),
        "citations": _loads(getattr(p, "citations", None), []),
        "updated": getattr(p, "metadata_updated", None),
        "updated_by": getattr(p, "metadata_updated_by", None),
    }


def get_metadata(uid: str) -> Optional[Dict]:
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        return project_metadata(p) if p else None


def update_metadata(uid: str, patch: Dict, actor: str) -> Optional[Dict]:
    with session_scope() as s:
        p = s.scalars(select(Project).where(Project.uid == uid)).first()
        if p is None:
            return None
        for f in METADATA_FIELDS:
            if f in patch:
                v = patch[f]
                setattr(p, f, (v.strip() if isinstance(v, str) else v) or None)
        if "tags" in patch:
            tags = [str(t).strip() for t in (patch["tags"] or []) if str(t).strip()]
            p.tags = json.dumps(sorted(set(tags), key=str.lower)[:50])
        if "citations" in patch:
            cites = []
            for c in (patch["citations"] or [])[:50]:
                if isinstance(c, dict) and (c.get("label") or c.get("url") or c.get("doi")):
                    cites.append({"label": str(c.get("label") or "")[:255],
                                  "url": str(c.get("url") or "")[:512],
                                  "doi": str(c.get("doi") or "")[:128]})
            p.citations = json.dumps(cites)
        p.metadata_updated = _now()
        p.metadata_updated_by = actor
        return project_metadata(p)


def all_tags(email: str) -> List[str]:
    """Distinct tags across the caller's own projects (for autocomplete)."""
    email = (email or "").strip().lower()
    out = set()
    with session_scope() as s:
        for p in s.scalars(select(Project).where(Project.email == email)).all():
            out.update(_loads(getattr(p, "tags", None), []))
    return sorted(out, key=str.lower)


def _tpl(t: AnalysisTemplate) -> Dict:
    return {"id": t.id, "name": t.name, "description": t.description or "",
            "params": _loads(t.params_json, {}), "created": t.created, "updated": t.updated}


def list_templates(email: str) -> List[Dict]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        rows = s.scalars(select(AnalysisTemplate).where(AnalysisTemplate.owner_email == email)
                         .order_by(AnalysisTemplate.updated.desc())).all()
        return [_tpl(t) for t in rows]


def create_template(email: str, name: str, description: str, params: Dict) -> Dict:
    email = (email or "").strip().lower()
    now = _now()
    with session_scope() as s:
        t = AnalysisTemplate(owner_email=email, name=name.strip()[:255],
                             description=(description or "")[:2000],
                             params_json=json.dumps(params), created=now, updated=now)
        s.add(t)
        s.flush()
        return _tpl(t)


def update_template(email: str, tid: int, name: Optional[str], description: Optional[str],
                    params: Optional[Dict]) -> Optional[Dict]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        t = s.get(AnalysisTemplate, tid)
        if t is None or t.owner_email != email:
            return None
        if name is not None and name.strip():
            t.name = name.strip()[:255]
        if description is not None:
            t.description = description[:2000]
        if params is not None:
            t.params_json = json.dumps(params)
        t.updated = _now()
        return _tpl(t)


def delete_template(email: str, tid: int) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        t = s.get(AnalysisTemplate, tid)
        if t is None or t.owner_email != email:
            return False
        s.delete(t)
        return True


def project_summary_for_compare(uid: str) -> Optional[Dict]:
    """Compact, comparison-friendly view of a stored project (no full payload)."""
    proj = get_project_by_uid(uid)
    if proj is None:
        return None
    resp = proj["response"]
    req = resp.request
    guides = resp.guides
    sel = set(resp.optimized_set.selected_guide_ids)

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    top = guides[:5]
    return {
        "uid": proj["uid"], "id": proj["id"], "name": proj["name"], "created": proj["created"],
        "owner_email": proj["owner_email"],
        "inputs": {"organism": req.organism, "cas_enzyme": req.cas_enzyme,
                   "desired_outcome": getattr(req.desired_outcome, "value", req.desired_outcome),
                   "risk_tolerance": req.risk_tolerance, "set_size": req.set_size,
                   "optimizer_mode": resp.optimized_set.mode, "sequence_length": len(req.sequence),
                   "cell_type": req.cell_type, "delivery_method": req.delivery_method},
        "stats": {
            "n_guides": len(guides),
            "mean_on_target": mean([g.scores.on_target for g in guides]),
            "mean_off_target_risk": mean([g.off_target.risk_score for g in guides]),
            "mean_final_score": mean([g.final_score for g in guides]),
            "high_risk_guides": sum(1 for g in guides if g.off_target.risk_score >= 0.4),
            "set_mean_final_score": mean([g.final_score for g in guides if g.guide_id in sel]),
            "set_mean_off_target_risk": mean([g.off_target.risk_score for g in guides if g.guide_id in sel]),
        },
        "optimized_set": {"guide_ids": list(resp.optimized_set.selected_guide_ids),
                          "method": resp.optimized_set.method,
                          "objective_value": resp.optimized_set.objective_value},
        "top_guides": [{"guide_id": g.guide_id, "sequence": g.sequence, "pam": g.pam,
                        "final_score": round(g.final_score, 4),
                        "on_target": round(g.scores.on_target, 4),
                        "off_target_risk": round(g.off_target.risk_score, 4),
                        "in_set": g.guide_id in sel} for g in top],
        "metadata": get_metadata(uid),
    }


def _n_dict(n: Notification) -> Dict:
    return {"id": n.id, "type": n.type, "title": n.title, "message": n.message or "",
            "link": n.link, "read": bool(n.read), "created": n.created}


def list_notifications(email: str, limit: int = 30, unread_only: bool = False) -> List[Dict]:
    email = (email or "").strip().lower()
    limit = max(1, min(int(limit), 200))
    with session_scope() as s:
        q = select(Notification).where(Notification.user_email == email)
        if unread_only:
            q = q.where(Notification.read == 0)
        rows = s.scalars(q.order_by(Notification.id.desc()).limit(limit)).all()
        return [_n_dict(n) for n in rows]


def unread_count(email: str) -> int:
    from sqlalchemy import func
    email = (email or "").strip().lower()
    with session_scope() as s:
        return int(s.scalar(select(func.count()).select_from(Notification).where(
            Notification.user_email == email, Notification.read == 0)) or 0)


def mark_read(email: str, nid: int, read: bool = True) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        n = s.get(Notification, nid)
        if n is None or n.user_email != email:
            return False
        n.read = 1 if read else 0
        return True


def mark_all_read(email: str) -> int:
    email = (email or "").strip().lower()
    with session_scope() as s:
        rows = s.scalars(select(Notification).where(
            Notification.user_email == email, Notification.read == 0)).all()
        for n in rows:
            n.read = 1
        return len(rows)


def delete_notification(email: str, nid: int) -> bool:
    email = (email or "").strip().lower()
    with session_scope() as s:
        n = s.get(Notification, nid)
        if n is None or n.user_email != email:
            return False
        s.delete(n)
        return True


# --- notification preferences (stored as JSON on the user row) --------------- #
NOTIFICATION_CATEGORIES = {
    "collaboration": "Invitations, role changes and collaborators joining or leaving",
    "project_activity": "Renames, re-runs, notes and deletions on shared projects",
    "account": "Security and account alerts",
    "billing": "Credits and subscription updates",
}
_TYPE_TO_CATEGORY = {
    "project_invite": "collaboration", "project_role_changed": "collaboration",
    "project_access_removed": "collaboration", "collaborator_left": "collaboration",
    "project_renamed": "project_activity", "project_updated": "project_activity",
    "analysis_completed": "project_activity", "project_deleted": "project_activity",
    "security": "account", "account": "account",
    "billing": "billing", "subscription": "billing",
}


def _pref_key(ntype: str) -> str:
    return _TYPE_TO_CATEGORY.get(ntype, "account")


def get_notification_prefs(email: str) -> Dict[str, bool]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        raw = getattr(u, "notification_prefs", None) if u else None
    prefs = {k: True for k in NOTIFICATION_CATEGORIES}
    prefs.update({k: bool(v) for k, v in _loads(raw, {}).items() if k in prefs})
    return prefs


def set_notification_prefs(email: str, patch: Dict[str, bool]) -> Dict[str, bool]:
    email = (email or "").strip().lower()
    prefs = get_notification_prefs(email)
    prefs.update({k: bool(v) for k, v in patch.items() if k in prefs})
    with session_scope() as s:
        u = s.get(User, email)
        if u is not None:
            u.notification_prefs = json.dumps(prefs)
    return prefs
