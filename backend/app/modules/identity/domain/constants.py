"""Domain-wide constants shared by the "don't lock everyone out" checks.

Previously duplicated as a private `_CONTROL_PERMISSIONS` in
`assign_role.py` and `deactivate_user.py` — a third use case
(`update_role_permissions.py`) needed the same set, which is the DRY
threshold this project uses to extract (rule: .claude/rules/globals.md,
"duplicou 2x+, extraia").
"""

from __future__ import annotations

# Losing any one of these permissions *organization-wide* (not just for one
# user) leaves nobody able to administer identity itself — no one left who
# can change a role, deactivate an account, or edit a permission profile to
# fix the mistake. `roles.manage` was missing from the original two-use-case
# version of this set, which is exactly how an admin could strip it from
# their own profile via `update_role_permissions` with zero protection
# (found in manual adversarial testing, ADR-007).
CONTROL_PERMISSIONS: frozenset[str] = frozenset(
    {"users.update", "roles.assign", "users.deactivate", "roles.manage"}
)
