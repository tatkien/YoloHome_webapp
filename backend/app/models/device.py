import uuid
import sqlalchemy as sa
from app.db.session import Base
from sqlalchemy.orm import relationship

class HardwareNode(Base):
    __tablename__ = "hardware_nodes"

    id = sa.Column(sa.String(64), primary_key=True)
    name = sa.Column(sa.String(128), nullable=False)
    pins = sa.Column(sa.JSON)
    created_at = sa.Column( 
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True 
    )
    
    devices = relationship("Device", back_populates="hardware_node", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id = sa.Column(sa.String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = sa.Column(sa.String(128), nullable=False)
    type = sa.Column(sa.String(32), default="unknown", index=True)
    is_on = sa.Column(sa.Boolean, default=False)
    value = sa.Column(sa.Float, default=0)
    room = sa.Column(sa.String(128))
    created_by = sa.Column(sa.String(128))
    pin = sa.Column(sa.String(32), nullable=True)

    last_seen_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    meta_data = sa.Column(sa.JSON, nullable=True)
    search_keywords = sa.Column(sa.Text, nullable=True, index=True)
    created_at = sa.Column( 
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True 
    )
    hardware_id = sa.Column(
        sa.String(64), sa.ForeignKey("hardware_nodes.id", ondelete="CASCADE"), nullable=True
    )

    __table_args__ = (
        sa.UniqueConstraint('hardware_id', 'pin', name='_hardware_pin_uc'),
    )

    logs = relationship("DeviceLog", back_populates="device", cascade="all, delete-orphan")
    sensor_data = relationship("SensorData", back_populates="device")
    hardware_node = relationship("HardwareNode", back_populates="devices")


class DeviceLog(Base):
    """Store device activity history."""
    __tablename__ = "device_logs"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    device_id = sa.Column(
        sa.String(64), sa.ForeignKey("devices.id", ondelete="CASCADE")
    )
    device_name = sa.Column(sa.String(128), nullable=False)
    action = sa.Column(sa.String(255), nullable=False)
    actor = sa.Column(sa.String(128), nullable=True)
    source = sa.Column(sa.String(128), nullable=True)
    created_at = sa.Column( 
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True 
    )

    device = relationship("Device", back_populates="logs")


class SensorData(Base):
    """Store time-series data for sensors."""
    __tablename__ = "sensor_data"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    device_id = sa.Column(
        sa.String(64), sa.ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    value = sa.Column(sa.Float, nullable=False)
    sensor_type = sa.Column(sa.String(32), nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True
    )

    device = relationship("Device", back_populates="sensor_data")