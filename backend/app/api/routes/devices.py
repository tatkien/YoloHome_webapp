from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

from app.api.deps import get_current_user, get_admin_user, get_db
from app.db.db_utils import reset_sequence_to_min_gap
from app.models.device import Device, DeviceTypeEnum
from app.models.user import User

from app.schemas.device import DeviceRead, DeviceUpdate, DeviceCreate, DeviceLogRead, DeviceControlRequest, SensorDataRead
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleUpdate, DeviceScheduleRead
from app.models.device import HardwareNode, DeviceLog, SensorData
from app.models.device_schedule import DeviceSchedule
from app.schemas.hardware import HardwareNodeRead
from app.realtime.websocket_manager import realtime_manager
from app.service.history import add_history_record
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
                owner_id=node.owner_id,
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
        owner_id=node.owner_id,
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
    new_device = Device(**device_data)
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    return new_device


@router.get("/", response_model=List[DeviceRead])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all devices."""
    result = await db.execute(sa.select(Device).order_by(Device.created_at.desc()))
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
    """Update device info (name, room, type...)."""
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

    await db.delete(device)
    await db.commit()


# --- PART 2: MQTT CONTROL ---

@router.post("/{device_id}/command")
async def send_command(
    device_id: str,
    payload: DeviceControlRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Web client calls this API to send command via MQTT to YoloBit hardware."""
    device = await _get_device_or_404(db, device_id)

    if not device.hardware_id or not device.pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device is not linked to hardware",
        )

    # Send command via MQTT
    try:
        from app.main import mqtt_service

        await mqtt_service.publish_command(
            hardware_id=device.hardware_id,
            pin=device.pin,
            payload=payload
        )

        # Add history log
        action_detail = (
            f"Sent command: {'ON' if payload.is_on else 'OFF'} (Value: {payload.value})"
        )
        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action=action_detail,
            actor=str(f"User: {user.id}"),
            source="Web Command",
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MQTT publish error: {e}",
        )

    # DB state is updated after hardware sends response to 'state' topic
    return {"status": "success", "message": "Command sent to hardware"}


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

@router.get("/{device_id}/history", response_model=List[DeviceLogRead])
async def get_device_history(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 20,
):
    """Get history logs for a specific device."""
    # Ensure device exists
    await _get_device_or_404(db, device_id)

    # Query logs ordered by newest first
    stmt = (
        sa.select(DeviceLog)
        .where(DeviceLog.device_id == device_id)
        .order_by(DeviceLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{device_id}/sensor-data", response_model=List[SensorDataRead])
async def get_sensor_data(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 20,
):
    """Get recent sensor data for a specific device."""
    # Ensure device exists
    await _get_device_or_404(db, device_id)

    # Query sensor data ordered by newest first
    stmt = (
        sa.select(SensorData)
        .where(SensorData.device_id == device_id)
        .order_by(SensorData.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/docs-websocket-info", tags=["WebSocket Docs (Reference Only)"])
async def websocket_documentation_only():
    """
    ### NOTE: THIS IS A DOCUMENTATION-ONLY ENDPOINT
    **Do not click "Execute"; this endpoint does not return live data.**

    The system uses one shared stream per user. Connection guide:

    ---
    ### 1. Open connection
    Device/sensor events are delivered through this single URL.
    * **URL:** `ws://{{host}}/api/v1/ws?token={{your_jwt_token}}`

    ---
    ### 2. Message protocol (JSON)
    * **Server -> Client (Handshake successful):** `{"type": "connection.ready", "user_id": 1}`
    * **Client -> Server (Keepalive):** Send `{"type": "ping"}` every 30s to receive `{"type": "pong"}`.
    * **Idle timeout:** 60 seconds without any message will close the connection.

    ---
    ### 3. Incoming payload shape
    Frontend uses the `"event"` field to render updates.

    **Sensor update event:**
    ```json
    {
      "event": "sensor_update",
      "hardware_id": "MOCK_BOARD",
      "data": { "temp": 28, "humi": 70 }
    }
    ```
    **State update event (ON/OFF):**
    ```json
    {
      "event": "device_update",
      "hardware_id": "MOCK_BOARD",
      "device_id": "uuid-cua-thiet-bi",
      "data": { "is_on": true, "value": 1023 }
    }
    ```
    """
    return {"detail": "This is a documentation page, not a live endpoint."}