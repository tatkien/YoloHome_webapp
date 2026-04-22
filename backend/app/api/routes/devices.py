from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

from app.api.deps import get_current_user, get_admin_user, get_db
from app.db.db_utils import reset_sequence_to_min_gap
from app.models.device import Device, DeviceTypeEnum
from app.models.user import User

from app.schemas.device import DeviceRead, DeviceUpdate, DeviceCreate, DeviceControlRequest, SensorDataRead
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleUpdate, DeviceScheduleRead
from app.models.device import HardwareNode, SensorData
from app.models.device_schedule import DeviceSchedule
from app.schemas.hardware import HardwareNodeRead
from app.realtime.websocket_manager import realtime_manager
from app.core.logger import logger, add_history_record
from app.core.device_handle import DeviceHandler

router = APIRouter(prefix="/devices", tags=["devices"])

# --- Pin assignment rules ---
# These device types must be assigned to their specific dedicated pins.
DEDICATED_PIN_MAP = {
    DeviceTypeEnum.TEMP_SENSOR: "temp",
    DeviceTypeEnum.HUMIDITY_SENSOR: "humi",
    DeviceTypeEnum.LOCK: "servo",
}

# --- HELPER FUNCTIONS ---
async def _get_device_or_404(db: AsyncSession, device_id: str) -> Device:
    """Find a device by UUID or raise 404."""
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device

async def _validate_pin_assignment(
    db: AsyncSession, hardware_id: str, pin: str, device_type: DeviceTypeEnum
) -> None:
    """
    Validate pin assignment rules:
    1. The hardware node must exist and the pin must be in its pin list.
    2. temp_sensor → must use 'temp' pin; humidity_sensor → 'humi'; lock → 'servo'.
    3. All other types → any non-dedicated pin.
    4. The pin must not already be occupied by another device.
    """
    # 1. Check hardware node exists
    result = await db.execute(
        sa.select(HardwareNode).where(HardwareNode.id == hardware_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Hardware node not found"
        )

    # Check pin is in the hardware's available pins
    available_pins = node.pins or []
    if pin not in available_pins:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Pin '{pin}' is not available on hardware '{hardware_id}'. "
            f"Available pins: {available_pins}",
        )

    # 2. Dedicated pin check
    dedicated_pins = set(DEDICATED_PIN_MAP.values())  # {"temp", "humi", "servo"}

    if device_type in DEDICATED_PIN_MAP:
        required_pin = DEDICATED_PIN_MAP[device_type]
        if pin != required_pin:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Device type '{device_type.value}' must be assigned to "
                f"pin '{required_pin}', got '{pin}'",
            )
    else:
        # 3. Non-dedicated types cannot use dedicated pins
        if pin in dedicated_pins:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Pin '{pin}' is reserved for dedicated device types "
                f"(temp_sensor, humidity_sensor, lock). "
                f"Use a general-purpose pin instead.",
            )

    # 4. Check pin not already occupied
    existing = await db.execute(
        sa.select(Device).where(
            Device.hardware_id == hardware_id, Device.pin == pin
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Pin '{pin}' on hardware '{hardware_id}' is already in use",
        )


# --- HARDWARE MANAGEMENT ---

@router.get("/hardware", response_model=List[HardwareNodeRead])
async def list_hardware_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get YoloBit boards and their available pins."""
    # Load hardware nodes and their devices via a manual join
    nodes_result = await db.execute(sa.select(HardwareNode))
    nodes = nodes_result.scalars().all()

    result = []
    for node in nodes:
        devices_result = await db.execute(
            sa.select(Device).where(Device.hardware_id == node.id)
        )
        devices = devices_result.scalars().all()
        result.append(
            HardwareNodeRead(
                id=node.id,
                name=node.name,
                pins=node.pins or [],
                devices=[DeviceRead.model_validate(d) for d in devices],
            )
        )
    return result


@router.get("/hardware/{hardware_id}", response_model=HardwareNodeRead)
async def read_hardware_node(
    hardware_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get details for one hardware board."""
    result = await db.execute(
        sa.select(HardwareNode).where(HardwareNode.id == hardware_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Hardware board not found"
        )

    devices_result = await db.execute(
        sa.select(Device).where(Device.hardware_id == node.id)
    )
    devices = devices_result.scalars().all()

    return HardwareNodeRead(
        id=node.id,
        name=node.name,
        pins=node.pins or [],
        devices=[DeviceRead.model_validate(d) for d in devices],
    )


@router.delete("/hardware/{hardware_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hardware_node(
    hardware_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Delete a hardware board and all child devices."""
    result = await db.execute(
        sa.select(HardwareNode).where(HardwareNode.id == hardware_id)
    )
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Hardware board not found"
        )

    # Delete child devices manually (no cascade via relationship)
    await db.execute(
        sa.delete(Device).where(Device.hardware_id == hardware_id)
    )
    await db.delete(node)
    await db.commit()


# --- PART 1: DEVICE CRUD ---

@router.post("/", response_model=DeviceRead)
async def create_device(
    payload: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Admin creates a new device mapped to a hardware pin."""
    # Validate pin assignment
    await _validate_pin_assignment(
        db, payload.hardware_id, payload.pin, DeviceTypeEnum(payload.type.value)
    )

    device_data = payload.model_dump(mode="json")
    # Auto-generate search_keywords for Voice AI if not provided
    if not device_data.get("search_keywords"):
        name = device_data.get("name", "")
        room = device_data.get("room", "")
        dev_type = device_data.get("type", "")
        device_data["search_keywords"] = f"{name}; {room}; {dev_type}"

    new_device = Device(**device_data)
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)

    # Add history log
    await add_history_record(
        device_id=new_device.id,
        device_name=new_device.name,
        action=f"Tạo thiết bị mới (Type: {new_device.type.value}, Pin: {new_device.pin})",
        actor=str(admin.id),
        source="Web API (Create)",
    )

    return new_device


@router.get("/", response_model=List[DeviceRead])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all devices."""
    result = await db.execute(sa.select(Device).order_by(Device.created_at.desc()))
    return result.scalars().all()

@router.get("/get-camera-devices", response_model=List[DeviceRead])
async def get_camera_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get all camera devices."""
    result = await db.execute(
        sa.select(Device).where(Device.type == DeviceTypeEnum.CAMERA)
    )
    return result.scalars().all()

@router.get("/sensor-data", response_model=List[SensorDataRead])
async def get_sensor_data_history(
    device_id: Optional[str] = Query(None, description="Filter by specific device ID"),
    sensor_type: Optional[DeviceTypeEnum] = Query(None, description="Filter by sensor type (temp_sensor, humidity_sensor)"),
    limit: int = Query(50, ge=1, le=1000),
    time_range: Optional[str] = Query(None, alias="range", description="Time range (1h, 24h, 7d)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Unified endpoint to get sensor data history with optional time range filtering.
    """
    from datetime import datetime, timedelta
    
    stmt = sa.select(SensorData)
    
    if device_id:
        await _get_device_or_404(db, device_id)
        stmt = stmt.where(SensorData.device_id == device_id)
        
    if sensor_type:
        if sensor_type not in [DeviceTypeEnum.TEMP_SENSOR, DeviceTypeEnum.HUMIDITY_SENSOR]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type '{sensor_type}' is not a compatible sensor type for data history"
            )
        stmt = stmt.where(SensorData.sensor_type == sensor_type)

    if time_range:
        now = datetime.utcnow()
        if time_range == "1h":
            stmt = stmt.where(SensorData.created_at >= now - timedelta(hours=1))
        elif time_range == "24h":
            stmt = stmt.where(SensorData.created_at >= now - timedelta(hours=24))
        elif time_range == "7d":
            stmt = stmt.where(SensorData.created_at >= now - timedelta(days=7))
        # When range is provided, we might want to return more points than the default limit
        stmt = stmt.order_by(SensorData.created_at.desc()).limit(2000) 
    else:
        stmt = stmt.order_by(SensorData.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{device_id}", response_model=DeviceRead)
async def read_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get one device details."""
    return await _get_device_or_404(db, device_id)


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Cập nhật thông tin thiết bị (tên, phòng, loại...)."""
    logger.info(f"[API] Nhận yêu cầu PATCH cho thiết bị: {device_id}")
    device = await _get_device_or_404(db, device_id)

    update_data = payload.model_dump(mode="json", exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)

    # Broadcast UI update to all connected users
    user_ids = list(realtime_manager.active_connections.keys())
    if user_ids:
        ws_payload = {
            "event": "info_updated",
            "device_id": device.id,
            "data": {"name": device.name, "room": device.room},
        }
        for uid in user_ids:
            await realtime_manager.send_to_user(uid, ws_payload)

    # Add history log
    await add_history_record(
        device_id=device.id,
        device_name=device.name,
        action="Updated device configuration info",
        actor=str(admin.id),
        source="Web API (Update)",
    )

    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Delete a device."""
    device = await _get_device_or_404(db, device_id)

    # Add history log (before deletion because we need the name)
    await add_history_record(
        device_id=device.id,
        device_name=device.name,
        action="Xóa thiết bị khỏi hệ thống",
        actor=str(admin.id),
        source="Web API (Delete)",
    )

    await db.delete(device)
    await db.commit()


# --- PART 2: MQTT CONTROL ---

from app.service.command_service import device_command

@router.post("/{device_id}/command")
async def send_command(
    device_id: str,
    payload: DeviceControlRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Web client calls this API to send command via MQTT to YoloBit hardware."""
    try:
        logger.info(f"[COMMAND] Device: {device_id} | Action: {'ON' if payload.is_on else 'OFF'} | Value: {payload.value} | Actor: {user.id}")
        result = await device_command(
            db=db,
            device_id=device_id,
            is_on=payload.is_on,
            value=payload.value,
            actor=str(user.id),
            source="Web Command"
        )
        return result
    except ValueError as str_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(str_err)
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MQTT publish error: {e}",
        )


# --- PART 3: SCHEDULES ---

@router.post("/{device_id}/schedules", response_model=DeviceScheduleRead)
async def create_schedule(
    device_id: str,
    payload: DeviceScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Create a schedule for a device."""
    await _get_device_or_404(db, device_id)
    # Don't allow schedules with servo and sensor types for now
    device_type = await db.scalar(
        sa.select(Device.type).where(Device.id == device_id)
    )
    if device_type in (DeviceTypeEnum.LOCK, DeviceTypeEnum.TEMP_SENSOR, DeviceTypeEnum.HUMIDITY_SENSOR):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Scheduling is not supported for lock and sensor devices",
        )

    schedule = DeviceSchedule(
        device_id=device_id,
        action=payload.action,
        time_of_day=payload.time_of_day,
        is_active=payload.is_active,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.get("/{device_id}/schedules", response_model=List[DeviceScheduleRead])
async def list_schedules(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all schedules for a device."""
    await _get_device_or_404(db, device_id)

    result = await db.execute(
        sa.select(DeviceSchedule).where(DeviceSchedule.device_id == device_id)
    )
    return result.scalars().all()

@router.put("/schedules/{schedule_id}", response_model=DeviceScheduleRead)
async def update_schedule(
    schedule_id: str,
    payload: DeviceScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Update a device schedule."""
    schedule = await db.get(DeviceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    schedule.time_of_day = payload.time_of_day
    await db.commit()
    await db.refresh(schedule)
    return schedule

@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Delete a device schedule."""
    schedule = await db.get(DeviceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    await db.delete(schedule)
    await db.commit()