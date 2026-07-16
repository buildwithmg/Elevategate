from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.audit import write_audit_log
from app.models.admin_user import AdminUser
from app.models.enums import ActorType
from app.repositories import device_group_repository
from app.schemas.device_group import DeviceGroupCreate, DeviceGroupList, DeviceGroupRead

router = APIRouter(prefix="/device-groups", tags=["device-groups"])


@router.post("", response_model=DeviceGroupRead, status_code=status.HTTP_201_CREATED)
async def create_device_group(
    body: DeviceGroupCreate,
    admin: AdminUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db),
) -> DeviceGroupRead:
    existing = await device_group_repository.get_by_name(session, body.name)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A group with this name already exists.")

    group = await device_group_repository.create(session, name=body.name, description=body.description)

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="device_group.created",
        target_type="device_group",
        target_id=str(group.id),
        metadata={"name": group.name},
    )

    await session.commit()
    await session.refresh(group)
    return DeviceGroupRead(
        id=group.id, name=group.name, description=group.description, device_count=0, created_at=group.created_at
    )


@router.get("", response_model=DeviceGroupList)
async def list_device_groups(
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> DeviceGroupList:
    groups = await device_group_repository.list_all(session)
    items = []
    for group in groups:
        device_count = await device_group_repository.count_devices_in_group(session, group.id)
        items.append(
            DeviceGroupRead(
                id=group.id,
                name=group.name,
                description=group.description,
                device_count=device_count,
                created_at=group.created_at,
            )
        )
    return DeviceGroupList(items=items, total=len(items))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_group(
    group_id: int,
    admin: AdminUser = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db),
) -> None:
    group = await device_group_repository.get_by_id(session, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device group not found.")

    group_name = group.name
    await device_group_repository.delete(session, group)

    await write_audit_log(
        session,
        actor_type=ActorType.ADMIN,
        actor_id=str(admin.id),
        action="device_group.deleted",
        target_type="device_group",
        target_id=str(group_id),
        metadata={"name": group_name},
    )

    await session.commit()
