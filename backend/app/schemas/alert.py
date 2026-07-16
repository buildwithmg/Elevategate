from enum import Enum

from pydantic import BaseModel


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"


class AlertType(str, Enum):
    LOW_DISK_SPACE = "low_disk_space"
    HIGH_RAM_USAGE = "high_ram_usage"
    DEVICE_OFFLINE = "device_offline"


class Alert(BaseModel):
    severity: AlertSeverity
    type: AlertType
    device_id: int
    device_uuid: str
    hostname: str
    message: str


class AlertList(BaseModel):
    items: list[Alert]
    total: int
