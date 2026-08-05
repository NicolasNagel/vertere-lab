"""Fixed catalog of roles and permissions seeded by
`alembic/versions/0002_seed_identity_catalog.py`.

UUIDs are deterministic constants (not `uuid4()` at migration time) so other
migrations, seeds and tests can reference a specific role/permission without
re-querying by name. See docs/07-nucleo-v1.md §2.1/§2.2 for the source list.

`CLINIC_ADMIN`/`VETERINARIAN`/`CLINIC_STAFF` are cataloged with **zero**
permissions on purpose: they have no `Clinic`/`ClinicMembership` to give them
scope yet (Fase 2). `roles.manage` is an addition beyond docs/07-nucleo-v1.md
§2.2 — `roles.assign` in that list means "assign a role to a user", not "edit
a role's permission set", so a separate permission is needed for the latter.
"""

from __future__ import annotations

from uuid import UUID

ROLE_SUPER_ADMIN = UUID("00000000-0000-0000-0000-000000000001")
ROLE_LAB_ADMIN = UUID("00000000-0000-0000-0000-000000000002")
ROLE_RECEPTION = UUID("00000000-0000-0000-0000-000000000003")
ROLE_FINANCE = UUID("00000000-0000-0000-0000-000000000004")
ROLE_TECHNICAL = UUID("00000000-0000-0000-0000-000000000005")
ROLE_TECHNICAL_MANAGER = UUID("00000000-0000-0000-0000-000000000006")
ROLE_CLINIC_ADMIN = UUID("00000000-0000-0000-0000-000000000007")
ROLE_VETERINARIAN = UUID("00000000-0000-0000-0000-000000000008")
ROLE_CLINIC_STAFF = UUID("00000000-0000-0000-0000-000000000009")

PERMISSION_CODES: tuple[str, ...] = (
    "users.read",
    "users.create",
    "users.update",
    "users.deactivate",
    "users.activate",
    "roles.read",
    "roles.assign",
    "roles.manage",
    "permissions.read",
    "clinics.read",
    "clinics.manage",
    "veterinarians.read",
    "veterinarians.manage",
    "owners.read",
    "owners.manage",
    "patients.read",
    "patients.manage",
    "catalog.read",
    "catalog.manage",
    "pricing.read",
    "pricing.manage",
    "attendances.read",
    "attendances.create",
    "attendances.update",
    "attendances.cancel",
    "attendances.override_price",
    "closures.read",
    "closures.preview",
    "closures.close",
    "closures.adjust",
    "closures.reopen",
    "audit.read",
    "imports.execute",
    # Master-only (see domain/constants.py MASTER_ONLY_PERMISSIONS) — deciding
    # whether staff other than Master can see prices while building an
    # attendance is reserved for Master, unlike `pricing.read` (the pricing
    # catalog admin screen), which FINANCE genuinely needs.
    "attendances.view_prices",
)

_ALL_PERMISSIONS = frozenset(PERMISSION_CODES)

# `0002_seed_identity_catalog.py` inserted every permission with
# `description=""` and is frozen (nunca editar migration já aplicada) — the
# friendly pt-BR text lives here instead and is applied by
# `alembic/versions/0033_add_permission_descriptions.py`, which UPDATEs by
# `code` and therefore fixes both a fresh database (0002 then 0033) and one
# that already ran 0002 with the empty description. Every key here must have
# a matching code in `PERMISSION_CODES` — the migration asserts that.
PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "users.read": "Ver usuários",
    "users.create": "Criar usuários",
    "users.update": "Editar dados de usuários",
    "users.deactivate": "Desativar usuários",
    "users.activate": "Reativar usuários",
    "roles.read": "Ver perfis de permissão",
    "roles.assign": "Atribuir perfil a um usuário",
    "roles.manage": "Editar as permissões de um perfil",
    "permissions.read": "Ver permissões disponíveis",
    "clinics.read": "Ver clínicas",
    "clinics.manage": "Cadastrar e editar clínicas",
    "veterinarians.read": "Ver veterinários",
    "veterinarians.manage": "Cadastrar e editar veterinários",
    "owners.read": "Ver proprietários",
    "owners.manage": "Cadastrar e editar proprietários",
    "patients.read": "Ver pacientes",
    "patients.manage": "Cadastrar e editar pacientes",
    "catalog.read": "Ver catálogo de exames",
    "catalog.manage": "Cadastrar e editar exames do catálogo",
    "pricing.read": "Ver preços",
    "pricing.manage": "Editar preços",
    "attendances.read": "Ver atendimentos",
    "attendances.create": "Abrir atendimentos",
    "attendances.update": "Editar atendimentos",
    "attendances.cancel": "Cancelar atendimentos",
    "attendances.override_price": "Alterar valor de um exame manualmente",
    "closures.read": "Ver fechamentos",
    "closures.preview": "Gerar prévia de fechamento",
    "closures.close": "Fechar competência",
    "closures.adjust": "Registrar ajuste financeiro",
    "closures.reopen": "Reabrir fechamento",
    "audit.read": "Ver trilha de auditoria",
    "imports.execute": "Executar importação da planilha",
    "attendances.view_prices": "Ver preço ao montar atendimento",
}

ROLE_DEFINITIONS: tuple[tuple[UUID, str, str, str, frozenset[str]], ...] = (
    (
        ROLE_SUPER_ADMIN,
        "SUPER_ADMIN",
        "GLOBAL",
        "Manutenção excepcional da plataforma.",
        _ALL_PERMISSIONS,
    ),
    (
        ROLE_LAB_ADMIN,
        "LAB_ADMIN",
        "LAB",
        "Usuários, permissões e configurações do laboratório.",
        # `roles.manage` (redefinir o que um perfil concede) fica exclusivo do
        # SUPER_ADMIN — LAB_ADMIN mantém `roles.read`/`roles.assign` (ver e
        # atribuir perfil a um usuário) mas não edita a regra do perfil em si.
        # Ver alembic/versions/0032_restrict_roles_manage_to_super_admin.py.
        # `attendances.view_prices` também fica de fora — é master-only (ver
        # domain/constants.py MASTER_ONLY_PERMISSIONS); LAB_ADMIN é escopo LAB,
        # não GLOBAL, então não pode carregá-la.
        _ALL_PERMISSIONS - {"roles.manage", "attendances.view_prices"},
    ),
    (
        ROLE_RECEPTION,
        "RECEPTION",
        "LAB",
        "Cadastros e atendimentos.",
        frozenset(
            {
                "clinics.read",
                "veterinarians.read",
                "veterinarians.manage",
                "owners.read",
                "owners.manage",
                "patients.read",
                "patients.manage",
                "catalog.read",
                "pricing.read",
                "attendances.read",
                "attendances.create",
                "attendances.update",
                "attendances.cancel",
            }
        ),
    ),
    (
        ROLE_FINANCE,
        "FINANCE",
        "LAB",
        "Preços, prévias, fechamentos e ajustes.",
        frozenset(
            {
                "clinics.read",
                "catalog.read",
                "catalog.manage",
                "pricing.read",
                "pricing.manage",
                "attendances.read",
                "attendances.override_price",
                "closures.read",
                "closures.preview",
                "closures.close",
                "closures.adjust",
                "closures.reopen",
                "audit.read",
            }
        ),
    ),
    (
        ROLE_TECHNICAL,
        "TECHNICAL",
        "LAB",
        "Operação técnica futura.",
        frozenset({"attendances.read", "patients.read", "catalog.read"}),
    ),
    (
        ROLE_TECHNICAL_MANAGER,
        "TECHNICAL_MANAGER",
        "LAB",
        "Revisão e laudos futuros.",
        frozenset({"attendances.read", "patients.read", "catalog.read", "catalog.manage"}),
    ),
    (
        ROLE_CLINIC_ADMIN,
        "CLINIC_ADMIN",
        "CLINIC",
        "Usuários e visão da própria clínica.",
        frozenset(),
    ),
    (
        ROLE_VETERINARIAN,
        "VETERINARIAN",
        "CLINIC",
        "Solicitações e laudos próprios/permitidos.",
        frozenset(),
    ),
    (ROLE_CLINIC_STAFF, "CLINIC_STAFF", "CLINIC", "Consulta limitada.", frozenset()),
)
