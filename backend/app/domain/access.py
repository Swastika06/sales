from app.models.identity import User

TCG_ROLE_CODES = frozenset({"TCG_ADMIN", "TCG_SALES", "TCG_FINANCE"})
PARTNER_ROLE_CODES = frozenset(
    {"PARTNER_ADMIN", "PARTNER_SALES", "PARTNER_PRESALES", "PARTNER_DELIVERY"}
)


def role_codes(user: User) -> set[str]:
    return {role.code for role in user.roles}


def is_tcg_user(user: User) -> bool:
    return user.is_superuser or bool(role_codes(user) & TCG_ROLE_CODES)


def is_tcg_admin(user: User) -> bool:
    return user.is_superuser or "TCG_ADMIN" in role_codes(user)


def can_view_partner(user: User, partner_id: object) -> bool:
    return is_tcg_user(user) or user.partner_id == partner_id


def can_manage_partner(user: User, partner_id: object) -> bool:
    return is_tcg_admin(user) or (
        user.partner_id == partner_id and "PARTNER_ADMIN" in role_codes(user)
    )
