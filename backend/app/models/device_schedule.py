import sqlalchemy as sa

from app.db.session import Base


class DeviceSchedule(Base):
    __tablename__ = "device_schedules"

    id = sa.Column(sa.Integer, primary_key=True)
    device_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    time_of_day = sa.Column(sa.Time, nullable=False)
    action = sa.Column(sa.String(16), nullable=False)
    is_active = sa.Column(sa.Boolean, nullable=False, default=True, server_default=sa.true())
    created_by_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    last_triggered_on = sa.Column(sa.Date, nullable=True)
