from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.audit import write_audit_log
from app.models.admin_user import AdminUser
from app.models.enums import ActorType
from app.repositories import app_allowlist_repository, device_group_repository
from app.schemas.app_allowlist import AppAllowlistEntryCreate, AppAllowlistEntryList, AppAllowlistEntryRead

router = APIRouter(prefix="/app-allowlist", tags=["app-allowlist"])


async def _to_read(session: AsyncSession, entry) -> AppAllowlistEntryRead:
    group_name = None
    if entry.group_id is not None:
        group = await device_group_repository.get_by_id(session, entry.group_id)
        group_name = group.name if group else None
    return AppAllowlistEntryRead(
        id=entry.id,
        group_id=entry.group_id,
        group_name=group_name,
        publisher=entry.publisher,
        filename=entry.filename,
        description=entry.description,
        created_by=entry.created_by,
        created_at=entry.created_at,
    )


@router.post("", response_model=AppAllowlistEntryRead, status_code=status.HTTP_201_CREATED)
async def create_app_allowlist_entry(
    body: AppAllowlistEntryCreate,
    admin: AdminUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db),
) -> AppAllowlistEntryRead:
    if body.group_id is not None:
        group = await device_group_repository.get_by_id(session, body.group_id)
        if group is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device group not found.")

    entry = await app_allowlist_repository.create(
        session,
        group_id=body.group_id,
        publisher=body.publisher,
        filename=body.filename,
        description=body.description,
        created_by=admin.id,
    )

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="app_allowlist.created",
        target_type="app_allowlist_entry",
        target_id=str(entry.id),
        metadata={"publisher": entry.publisher, "filename": entry.filename, "group_id": entry.group_id},
    )

    await session.commit()
    await session.refresh(entry)
    return await _to_read(session, entry)


@router.get("", response_model=AppAllowlistEntryList)
async def list_app_allowlist_entries(
    group_id: int | None = Query(default=None),
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> AppAllowlistEntryList:
    entries = await app_allowlist_repository.list_all(session, group_id_filter=group_id)
    items = [await _to_read(session, entry) for entry in entries]
    return AppAllowlistEntryList(items=items, total=len(items))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_allowlist_entry(
    entry_id: int,
    admin: AdminUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db),
) -> None:
    entry = await app_allowlist_repository.get_by_id(session, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="App allowlist entry not found.")

    metadata = {"publisher": entry.publisher, "filename": entry.filename}
    await app_allowlist_repository.delete(session, entry)

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="app_allowlist.deleted",
        target_type="app_allowlist_entry",
        target_id=str(entry_id),
        metadata=metadata,
    )

    await session.commit()
