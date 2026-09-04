"""
Project-level authorization.

Every project route resolves the caller's role through `require_project` and
nothing else. Rules:

  OWNER   the project row's owner. Full access: read, edit, run, share, delete.
  EDITOR  read, rename, save selection, re-run analyses in place.
  VIEWER  read only.

Non-members get 404 (not 403) so a guessed URL reveals nothing about whether the
project exists. Members with an insufficient role get 403.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from fastapi import HTTPException

from qguide.app import store

OWNER = "OWNER"
EDITOR = "EDITOR"
VIEWER = "VIEWER"
ROLES = (OWNER, EDITOR, VIEWER)
INVITABLE_ROLES = (EDITOR, VIEWER)

_RANK = {VIEWER: 1, EDITOR: 2, OWNER: 3}

# What each role may do -- exposed to the UI as `access.can_*` so buttons match
# the server, but the server is always the enforcement point.
CAPABILITIES = {
    OWNER: {"view", "edit", "run", "share", "delete", "organize"},
    EDITOR: {"view", "edit", "run"},
    VIEWER: {"view"},
}


def role_for(email: str, project: Dict) -> Optional[str]:
    email = (email or "").strip().lower()
    if project.get("owner_email") == email:
        return OWNER
    uid = project.get("uid")
    return store.membership_role(uid, email) if uid else None


def access_payload(role: str, project: Dict) -> Dict:
    caps = CAPABILITIES.get(role, set())
    return {
        "role": role,
        "uid": project.get("uid"),
        "owner_email": project.get("owner_email"),
        "is_owner": role == OWNER,
        **{f"can_{c}": (c in caps) for c in ("view", "edit", "run", "share", "delete", "organize")},
    }


def require_project(email: str, ident: str, min_role: str = VIEWER) -> Tuple[Dict, str]:
    """Resolve `ident` (uid or the caller's own pid) and enforce `min_role`.
    Returns (project metadata, caller role)."""
    meta = store.resolve_project(email, ident)
    if meta is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    role = role_for(email, meta)
    if role is None:
        # Deliberately indistinguishable from a missing project.
        raise HTTPException(status_code=404, detail="Project not found.")
    if _RANK[role] < _RANK[min_role]:
        need = {EDITOR: "Editor", OWNER: "Owner"}[min_role]
        raise HTTPException(status_code=403,
                            detail=f"{need} access is required for this action "
                                   f"(you are a {role.lower()}).")
    return meta, role
