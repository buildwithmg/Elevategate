from sqlalchemy import select

from app.core.security import verify_secret
from app.models.admin_user import AdminUser
from scripts.seed_admin import _seed


async def test_seed_creates_admin(db_session):
    exit_code = await _seed("bootstrap@example.com", "Bootstrap Admin", "a-strong-password-123")

    assert exit_code == 0
    result = await db_session.execute(
        select(AdminUser).where(AdminUser.email == "bootstrap@example.com")
    )
    admin = result.scalar_one()
    assert admin.role.value == "admin"
    assert admin.is_active is True
    assert verify_secret("a-strong-password-123", admin.password_hash)


async def test_seed_is_idempotent_for_existing_email(db_session):
    first = await _seed("bootstrap@example.com", "Bootstrap Admin", "a-strong-password-123")
    second = await _seed("bootstrap@example.com", "Different Name", "a-different-password-456")

    assert first == 0
    assert second == 0

    result = await db_session.execute(
        select(AdminUser).where(AdminUser.email == "bootstrap@example.com")
    )
    admins = result.scalars().all()
    assert len(admins) == 1
    assert admins[0].name == "Bootstrap Admin"  # untouched by the second call


async def test_seed_rejects_short_password(db_session):
    exit_code = await _seed("bootstrap@example.com", "Bootstrap Admin", "short")
    assert exit_code == 1

    result = await db_session.execute(
        select(AdminUser).where(AdminUser.email == "bootstrap@example.com")
    )
    assert result.scalar_one_or_none() is None


async def test_seed_rejects_invalid_email(db_session):
    exit_code = await _seed("not-an-email", "Bootstrap Admin", "a-strong-password-123")
    assert exit_code == 1
