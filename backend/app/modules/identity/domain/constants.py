"""Domain-wide constants shared by the "don't lock everyone out" checks.

Previously duplicated as a private `_CONTROL_PERMISSIONS` in
`assign_role.py` and `deactivate_user.py` — a third use case
(`update_role_permissions.py`) needed the same set, which is the DRY
threshold this project uses to extract (rule: .claude/rules/00-global.md,
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

# Permissions that only a GLOBAL-scope role may hold — checked against
# `role.scope`, never against a role name/id (rule: .claude/rules/01-product-
# domain.md, "código nunca decide por nome de papel"). SUPER_ADMIN is the
# only GLOBAL role today, so this is "Master-only" in practice without
# hardcoding that name. `attendances.view_prices` is narrower than
# `pricing.read` (the pricing catalog admin screen, which FINANCE genuinely
# needs) — it's specifically about seeing a price while building an
# attendance, a decision reserved for Master.
MASTER_ONLY_PERMISSIONS: frozenset[str] = frozenset({"attendances.view_prices"})
