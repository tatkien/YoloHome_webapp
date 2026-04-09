import sqlalchemy as sa
import uuid
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

DEVICE_TYPES = ("fan", "light", "camera", "lock", "temp_sensor", "humidity_sensor")


class HardwareNode(Base):
    __tablename__ = "hardware_nodes"
    id = sa.Column(sa.String(64), primary_key=True)
    name = sa.Column(sa.String(128), nullable=False)
    pins = sa.Column(sa.JSON)
    createdAt = sa.Column(sa.DateTime, server_default=sa.func.now())
    devices = relationship("Device", back_populates="node", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"
    id = sa.Column(sa.String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = sa.Column(sa.String(128), nullable=False)
    type = sa.Column(sa.String(32))
    isOn = sa.Column(sa.Boolean, default=False)
    value = sa.Column(sa.Integer, default=0)
    room = sa.Column(sa.String(128))
    createdBy = sa.Column(sa.String(128))
    hardwareId = sa.Column(sa.String(64), sa.ForeignKey("hardware_nodes.id"), nullable=True)
    node = relationship("HardwareNode", back_populates="devices")
    pin = sa.Column(sa.String(32), nullable=True) 
    last_seen_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    scheduledOnTime = sa.Column(sa.String(32))
    scheduledOffTime = sa.Column(sa.String(32))
    # search_keywords = sa.Column(sa.Text, nullable=True, index=True)
    createdAt = sa.Column(sa.DateTime, server_default=sa.func.now())


class DeviceLog(Base):
    """Ghi lịch sử thiết bị"""
    __tablename__ = "device_logs"
    id = sa.Column(sa.String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = sa.Column(sa.String(64), nullable=True) 
    device_name = sa.Column(sa.String(128), nullable=False)
    action = sa.Column(sa.String(255), nullable=False)  # Nội dung
    actor = sa.Column(sa.String(128), nullable=True)    # Ai làm: "system" hoặc "user_id"
    source = sa.Column(sa.String(128), nullable=True)   # Nguồn: Hardware, Web, Voice_Command, Face_ID
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), index=True)