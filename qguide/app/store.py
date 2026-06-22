"""
SQLite persistence for accounts, credits, transactions and projects.

Pure stdlib (`sqlite3`) -- no extra dependency. The DB file location is taken from
the QGUIDE_DB env var, defaulting to `qguide_data.db` in the working directory
(which is the repo root on Streamlit Community Cloud). This makes accounts, hashed
passwords, credit balances, the transaction ledger and saved projects survive page
refreshes and be shared across sessions, persisting for the life of the host
instance.

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes -- never plaintext.

Projects are persisted as JSON (the Pydantic request/response round-trip via
model_dump_json / model_validate_json); transient caches (predictions, sweep
results) are recomputed on demand and not stored.
"""
from __future__ import annotations

import binascii
import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Optional, Tuple

from qguide.app.schemas import DesignRequest, DesignResponse

DB_PATH = os.environ.get("QGUIDE_DB", "qguide_data.db")


# --------------------------------------------------------------------------- #
# Connection / schema                                                           #
# --------------------------------------------------------------------------- #
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def _db():
    """Connection context manager that commits on success and ALWAYS closes
    (sqlite3's own `with conn:` commits but does not close -> leaked handles)."""
    conn = _conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                pw_salt TEXT NOT NULL,
                pw_hash TEXT NOT NULL,
                plan TEXT NOT NULL,
                credits INTEGER NOT NULL,
                runs INTEGER NOT NULL DEFAULT 0,
                counter INTEGER NOT NULL DEFAULT 0,
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                ts TEXT NOT NULL,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                balance INTEGER NOT NULL,
                descr TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS projects (
                email TEXT NOT NULL,
                pid TEXT NOT NULL,
                name TEXT NOT NULL,
                created TEXT NOT NULL,
                elapsed REAL NOT NULL,
                selected_guide TEXT,
                n_guides INTEGER,
                best_guide TEXT,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                PRIMARY KEY (email, pid)
            );
            """
        )


# --------------------------------------------------------------------------- #
# Passwords                                                                     #
# --------------------------------------------------------------------------- #
def _hash(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 100_000).hex()


def _make_pw(pw: str) -> Tuple[str, str]:
    salt = os.urandom(16)
    return binascii.hexlify(salt).decode(), _hash(pw, salt)


def _check_pw(pw: str, salt_hex: str, hash_hex: str) -> bool:
    salt = binascii.unhexlify(salt_hex)
    return _hash(pw, salt) == hash_hex


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


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
    with _db() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            return False, "An account with that email already exists — sign in instead."
        salt, h = _make_pw(password)
        now = _now()
        c.execute("INSERT INTO users(email,name,pw_salt,pw_hash,plan,credits,runs,counter,created) "
                  "VALUES (?,?,?,?,?,?,?,?,?)",
                  (email, name, salt, h, "Free trial", bonus, 0, 0, now))
        c.execute("INSERT INTO transactions(email,ts,type,amount,balance,descr,price) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (email, now, "bonus", bonus, bonus, "Welcome bonus", 0.0))
    return True, "Account created."


def authenticate(email: str, password: str) -> Tuple[bool, str]:
    email = (email or "").strip().lower()
    init_db()
    with _db() as c:
        row = c.execute("SELECT pw_salt,pw_hash FROM users WHERE email=?", (email,)).fetchone()
    if not row or not _check_pw(password, row["pw_salt"], row["pw_hash"]):
        return False, "Invalid email or password."
    return True, "Signed in."


def load_account(email: str) -> Optional[Dict]:
    """Full account dict (incl. transactions + reconstructed projects)."""
    email = (email or "").strip().lower()
    init_db()
    with _db() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not u:
            return None
        txs = c.execute("SELECT ts,type,amount,balance,descr,price FROM transactions "
                        "WHERE email=? ORDER BY id", (email,)).fetchall()
        projs = c.execute("SELECT * FROM projects WHERE email=?", (email,)).fetchall()

    account = {
        "name": u["name"], "email": u["email"], "plan": u["plan"],
        "credits": u["credits"], "runs": u["runs"], "counter": u["counter"],
        "created": u["created"],
        "transactions": [{"ts": t["ts"], "type": t["type"], "amount": t["amount"],
                          "balance": t["balance"], "desc": t["descr"], "price": t["price"]}
                         for t in txs],
        "projects": {},
    }
    for p in projs:
        try:
            proj = {
                "id": p["pid"], "name": p["name"], "created": p["created"],
                "elapsed": p["elapsed"], "selected_guide": p["selected_guide"],
                "request": DesignRequest.model_validate_json(p["request_json"]),
                "response": DesignResponse.model_validate_json(p["response_json"]),
                "pred": None, "pred_cmp": None, "sim_results": None,
            }
            account["projects"][p["pid"]] = proj
        except Exception:
            continue  # skip a project that fails to deserialize rather than break login
    return account


def persist_counters(email: str, credits: int, plan: str, runs: int, counter: int) -> None:
    with _db() as c:
        c.execute("UPDATE users SET credits=?, plan=?, runs=?, counter=? WHERE email=?",
                  (credits, plan, runs, counter, (email or "").strip().lower()))


def add_transaction(email: str, ttype: str, amount: int, balance: int,
                    desc: str, price: float = 0.0) -> None:
    with _db() as c:
        c.execute("INSERT INTO transactions(email,ts,type,amount,balance,descr,price) "
                  "VALUES (?,?,?,?,?,?,?)",
                  ((email or "").strip().lower(), _now(), ttype, amount, balance, desc, price))


def save_project(email: str, proj: Dict) -> None:
    """Upsert a project (serialise the Pydantic request/response to JSON)."""
    resp = proj["response"]
    req = proj["request"]
    n_guides = len(resp.guides)
    best = resp.best_single_guide_id
    with _db() as c:
        c.execute(
            "INSERT INTO projects(email,pid,name,created,elapsed,selected_guide,n_guides,"
            "best_guide,request_json,response_json) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(email,pid) DO UPDATE SET name=excluded.name, "
            "selected_guide=excluded.selected_guide, response_json=excluded.response_json",
            ((email or "").strip().lower(), proj["id"], proj["name"], proj["created"],
             proj["elapsed"], proj.get("selected_guide"), n_guides, best,
             req.model_dump_json(), resp.model_dump_json()))
