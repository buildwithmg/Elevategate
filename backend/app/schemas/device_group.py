from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class DeviceGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    device_count: int
    created_at: datetime


class DeviceGroupList(BaseModel):
    items: list[DeviceGroupRead]
    total: int


class DeviceAssignGroupRequest(BaseModel):
    # Null unassigns the device from any group.
    group_id: int | None = None
