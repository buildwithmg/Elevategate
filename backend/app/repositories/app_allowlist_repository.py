from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_allowlist_entry import AppAllowlistEntry


async def create(
    session: AsyncSession,
    *,
    group_id: int | None,
    publisher: str,
    filename: str,
    description: str | None,
    created_by: int | None,
) -> AppAllowlistEntry:
    entry = AppAllowlistEntry(
        group_id=group_id,
        publisher=publisher,
        filename=filename,
        description=description,
        created_by=created_by,
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_by_id(session: AsyncSession, entry_id: int) -> AppAllowlistEntry | None:
    result = await session.execute(select(AppAllowlistEntry).where(AppAllowlistEntry.id == entry_id))
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession, *, group_id_filter: int | None = None) -> list[AppAllowlistEntry]:
    query = select(AppAllowlistEntry).order_by(AppAllowlistEntry.created_at.desc())
    if group_id_filter is not None:
        query = query.where(AppAllowlistEntry.group_id == group_id_filter)
    result = await session.execute(query)
    return list(result.scalars().all())


async def find_match(
    session: AsyncSession, *, device_group_id: int | None, publisher: str, filename: str
) -> AppAllowlistEntry | None:
    """
    An entry matches if its (publisher, filename) is an exact, case-sensitive match AND it either
    applies globally (group_id IS NULL) or to this specific device's group. Exact string matching
    is deliberate for a first version - an admin creating an entry is expected to copy the
    publisher/filename text as submitted; this can be relaxed (case-insensitive, wildcard) later
    if that turns out to be too strict in practice.
    """
    query = select(AppAllowlistEntry).where(
        AppAllowlistEntry.publisher == publisher,
        AppAllowlistEntry.filename == filename,
    )
    if device_group_id is None:
        query = query.where(AppAllowlistEntry.group_id.is_(None))
    else:
        query = query.where(
            or_(AppAllowlistEntry.group_id.is_(None), AppAllowlistEntry.group_id == device_group_id)
        )
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none()


async def delete(session: AsyncSession, entry: AppAllowlistEntry) -> None:
    await session.delete(entry)
