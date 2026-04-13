import enum

import sqlalchemy as sa

from app.db.session import Base


class ScheduleActionEnum(str, enum.Enum):
    ON = "on"
    OFF = "off"


class DeviceSchedule(Base):
    __tablename__ = "device_schedules"

    id = sa.Column(sa.Integer, primary_key=True)
    device_id = sa.Column(
        sa.String(64),
        sa.ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    times_of_day = sa.Column(sa.JSON, nullable=False)  # ["07:00", "18:30"]
    action = sa.Column(
        sa.Enum(ScheduleActionEnum, name="schedule_action_enum"), nullable=False
    )
    is_active = sa.Column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    last_triggered_on = sa.Column(sa.Date, nullable=True)