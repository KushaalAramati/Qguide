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
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import Column, Float, Integer, String, Text, select, text

from qguide.app.db import Base, engine, session_scope
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


class Folder(Base):
    __tablename__ = "folders"
    email = Column(String(255), primary_key=True)
    fid = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    parent_fid = Column(String(32))         # nullable -> top level; supports subfolders
    created = Column(String(32), nullable=False)
    fcounter_placeholder = Column(Integer, default=0)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Best-effort additive migrations for DBs created before a column existed.
    Each ALTER runs in its own transaction; a 'duplicate column' error (column
    already present) is swallowed. Portable across SQLite and Postgres."""
    for stmt in ["ALTER TABLE users ADD COLUMN last_login VARCHAR(32)",
                 "ALTER TABLE projects ADD COLUMN folder_id VARCHAR(32)",
                 "ALTER TABLE projects ADD COLUMN archived INTEGER DEFAULT 0",
                 "ALTER TABLE users ADD COLUMN fcounter INTEGER DEFAULT 0"]:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass


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


def _user_dict(u: User) -> Dict:
    return {"name": u.name, "email": u.email, "plan": u.plan, "credits": u.credits,
            "runs": u.runs, "counter": u.counter, "created": u.created,
            "last_login": u.last_login}


def _tx_dict(t: Transaction) -> Dict:
    return {"ts": t.ts, "type": t.type, "amount": t.amount, "balance": t.balance,
            "desc": t.descr, "price": t.price}


# --------------------------------------------------------------------------- #
# Accounts                                                                      #
# --------------------------------------------------------------------------- #
def create_user(name: str, email: str, password: str, bonus: int) -> Tuple[bool, str]:
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not name or not email or not password:
        return False, "Please fill in name, email and password."
    if "@" not in email:
        return False, "Please enter a valid email."
    init_db()
    with session_scope() as s:
        if s.get(User, email):
            return False, "An account with that email already exists — sign in instead."
        salt, h = _make_pw(password)
        now = _now()
        s.add(User(email=email, name=name, pw_salt=salt, pw_hash=h, plan="Free trial",
                   credits=bonus, runs=0, counter=0, created=now))
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
                          response_json=resp.model_dump_json()))


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
            out.append({"id": p.pid, "name": p.name, "created": p.created, "elapsed": p.elapsed,
                        "n_guides": p.n_guides, "best_guide": p.best_guide,
                        "folder_id": getattr(p, "folder_id", None), "archived": arch})
        return out


def _reconstruct(p: Project) -> Dict:
    return {"id": p.pid, "name": p.name, "created": p.created, "elapsed": p.elapsed,
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
    if not new or len(new) < 6:
        return False, "New password must be at least 6 characters."
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
    if not new or len(new) < 6:
        return False, "New password must be at least 6 characters."
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


def update_profile(email: str, name: Optional[str] = None) -> Optional[Dict]:
    email = (email or "").strip().lower()
    with session_scope() as s:
        u = s.get(User, email)
        if not u:
            return None
        if name is not None and name.strip():
            u.name = name.strip()
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
