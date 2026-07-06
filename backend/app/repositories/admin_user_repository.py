from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser
from app.models.enums import AdminRole


async def get_by_email(session: AsyncSession, email: str) -> AdminUser | None:
    result = await session.execute(select(AdminUser).where(AdminUser.email == email))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, admin_id: int) -> AdminUser | None:
    result = await session.execute(select(AdminUser).where(AdminUser.id == admin_id))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession, *, email: str, name: str, password_hash: str, role: AdminRole
) -> AdminUser:
    admin = AdminUser(email=email, name=name, password_hash=password_hash, role=role, is_active=True)
    session.add(admin)
    await session.flush()
    return admin


async def count_all(session: AsyncSession) -> int:
    from sqlalchemy import func

    result = await session.execute(select(func.count()).select_from(AdminUser))
    return result.scalar_one()
