from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_group import DeviceGroup


async def create(session: AsyncSession, *, name: str, description: str | None) -> DeviceGroup:
    group = DeviceGroup(name=name, description=description)
    session.add(group)
    await session.flush()
    return group


async def get_by_id(session: AsyncSession, group_id: int) -> DeviceGroup | None:
    result = await session.execute(select(DeviceGroup).where(DeviceGroup.id == group_id))
    return result.scalar_one_or_none()


async def get_by_name(session: AsyncSession, name: str) -> DeviceGroup | None:
    result = await session.execute(select(DeviceGroup).where(DeviceGroup.name == name))
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[DeviceGroup]:
    result = await session.execute(select(DeviceGroup).order_by(DeviceGroup.name))
    return list(result.scalars().all())


async def count_devices_in_group(session: AsyncSession, group_id: int) -> int:
    from app.models.device import Device

    result = await session.execute(
        select(func.count()).select_from(Device).where(Device.group_id == group_id)
    )
    return result.scalar_one()


async def delete(session: AsyncSession, group: DeviceGroup) -> None:
    await session.delete(group)
