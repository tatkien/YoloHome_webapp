import enum
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import validates

from app.core.config import settings
from app.db.session import Base


class DeviceTypeEnum(str, enum.Enum):
    FAN = "fan"
    LIGHT = "light"
    CAMERA = "camera"
    LOCK = "lock"
    TEMP_SENSOR = "temp_sensor"
    HUMIDITY_SENSOR = "humidity_sensor"


class HardwareNode(Base):
    __tablename__ = "hardware_nodes"

    id = sa.Column(sa.String(64), primary_key=True)
    name = sa.Column(sa.String(128), nullable=False)
    pins = sa.Column(sa.JSON)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    owner_id = sa.Column(
        sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )


class Device(Base):
    __tablename__ = "devices"

    id = sa.Column(sa.String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = sa.Column(sa.String(128), nullable=False)
    type = sa.Column(
        sa.Enum(DeviceTypeEnum, 
                name="device_type_enum",
                values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=DeviceTypeEnum.LIGHT,
        index=True,
    )
    is_on = sa.Column(sa.Boolean, default=False)
    value = sa.Column(sa.Float, default=0)
    room = sa.Column(sa.String(128))
    created_by = sa.Column(sa.String(128))
    pin = sa.Column(sa.String(32), nullable=True)
    last_seen_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    meta_data = sa.Column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    hardware_id = sa.Column(
        sa.String(64), sa.ForeignKey("hardware_nodes.id"), nullable=True
    )

    @validates("value")
    def validate_value(self, key, value):
        dev_type = self.type.lower() if isinstance(self.type, str) else self.type.value

        if dev_type == "lock":
            if not (settings.SERVO_CLOSE_ANGLE <= value <= settings.SERVO_OPEN_ANGLE):
                raise ValueError("Invalid servo lock range")
        elif dev_type == "fan":
            if not (0 <= int(value) <= 3 and float(value).is_integer()):
                raise ValueError("Fan speed must be 0, 1, 2, or 3")
        elif dev_type in ("light", "camera"):
            if not (float(value).is_integer() and value in (0, 1)):
                raise ValueError(f"{dev_type.capitalize()} value must be 0 or 1")

        return value


class DeviceLog(Base):
    """Store device activity history."""

    __tablename__ = "device_logs"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    device_id = sa.Column(
        sa.String(64), sa.ForeignKey("devices.id", ondelete="SET NULL")
    )
    device_name = sa.Column(sa.String(128), nullable=False)
    action = sa.Column(sa.String(255), nullable=False)
    actor = sa.Column(sa.String(128), nullable=True)
    source = sa.Column(sa.String(128), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True
    )