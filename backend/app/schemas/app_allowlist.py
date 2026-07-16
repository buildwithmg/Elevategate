from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppAllowlistEntryCreate(BaseModel):
    # Null applies the entry to every device, regardless of group.
    group_id: int | None = None
    publisher: str = Field(min_length=1, max_length=500)
    filename: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=4000)


class AppAllowlistEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int | None
    group_name: str | None
    publisher: str
    filename: str
    description: str | None
    created_by: int | None
    created_at: datetime


class AppAllowlistEntryList(BaseModel):
    items: list[AppAllowlistEntryRead]
    total: int
