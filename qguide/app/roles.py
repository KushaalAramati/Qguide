"""
Application roles and the permission checks that depend on them.

Roles are stored on the user row (`users.role`) and are ONLY assignable through
server-side mechanisms: the ADMIN_EMAILS environment allowlist (bootstrap) or an
authenticated admin calling the admin API. No user-facing endpoint ever accepts a
role from the client for their own account -- see `routes.update_profile`.

Adding a role later means adding it to ROLES and giving it a permission set.
"""
from __future__ import annotations

import os
from typing import Set

USER = "USER"
RESEARCHER = "RESEARCHER"
ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
ADMIN = "ADMIN"

ROLES = (USER, RESEARCHER, ORGANIZATION_ADMIN, ADMIN)

#: Roles that may be handed out through the admin API.
ASSIGNABLE_ROLES = ROLES

# --------------------------------------------------------------------------- #
# Permissions                                                                   #
# --------------------------------------------------------------------------- #
P_RUN_DESIGN = "run_design"
P_CREATE_PROJECT = "create_project"
P_RESEARCH_TOOLS = "research_tools"
P_MANAGE_ORG = "manage_org"
P_ADMIN_CONSOLE = "admin_console"
P_MANAGE_USERS = "manage_users"
P_MANAGE_ROLES = "manage_roles"

_BASE: Set[str] = {P_RUN_DESIGN, P_CREATE_PROJECT}

PERMISSIONS = {
    USER: set(_BASE),
    RESEARCHER: _BASE | {P_RESEARCH_TOOLS},
    ORGANIZATION_ADMIN: _BASE | {P_RESEARCH_TOOLS, P_MANAGE_ORG},
    ADMIN: _BASE | {P_RESEARCH_TOOLS, P_MANAGE_ORG, P_ADMIN_CONSOLE,
                    P_MANAGE_USERS, P_MANAGE_ROLES},
}


def normalize(role: str | None) -> str:
    r = (role or "").strip().upper()
    return r if r in ROLES else USER


def has_permission(role: str | None, permission: str) -> bool:
    return permission in PERMISSIONS.get(normalize(role), set())


def is_admin_role(role: str | None) -> bool:
    return normalize(role) == ADMIN


def bootstrap_admin_emails() -> Set[str]:
    """Emails promoted to ADMIN automatically (environment-configured admins)."""
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def permissions_for(role: str | None) -> list:
    return sorted(PERMISSIONS.get(normalize(role), set()))
