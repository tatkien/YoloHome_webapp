from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_admin_user, get_db
from app.models.device import Device
from app.models.user import User

from app.schemas.device import DeviceRead, DeviceUpdate, DeviceCreate, DeviceLogRead
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleRead
from app.models.device import HardwareNode, DeviceLog
from app.models.device_schedule import DeviceSchedule
from app.schemas.hardware import HardwareNodeRead
from app.realtime.websocket_manager import realtime_manager
from app.service.history import add_history_record
from app.core.device_handle import DeviceHandler

router = APIRouter(prefix="/devices", tags=["devices"])

# --- HELPER FUNCTIONS ---
async def _get_device_or_404(db: AsyncSession, device_id: str) -> Device:
    """Find a device by UUID or raise 404."""
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


# --- HARDWARE MANAGEMENT ---

@router.get("/hardware", response_model=List[HardwareNodeRead])
async def list_hardware_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get YoloBit boards and their available pins."""
    # Use selectinload so related child devices are loaded eagerly
    query = sa.select(HardwareNode).options(selectinload(HardwareNode.devices))
    result = await db.execute(query)
    return result.scalars().unique().all() 

@router.get("/hardware/{hardware_id}", response_model=HardwareNodeRead)
async def read_hardware_node(
    hardware_id: str, 
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get details for one hardware board."""
    query = sa.select(HardwareNode).where(HardwareNode.id == hardware_id).options(selectinload(HardwareNode.devices))
    result = await db.execute(query)
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware board not found")
    return node

@router.delete("/hardware/{hardware_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hardware_node(
    hardware_id: str, 
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete a hardware board and all child devices."""
    # 1. Find hardware board
    result = await db.execute(sa.select(HardwareNode).where(HardwareNode.id == hardware_id))
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hardware board not found")

    # 2. Delete board (child devices cascade)
    await db.delete(node)
    await db.commit()


# --- PART 1: DEVICE CRUD ---

@router.post("/", response_model=DeviceRead)
async def create_device(
    payload: DeviceCreate, # Includes name, hardware_id, pin...
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Admin creates a new device mapped to a hardware pin."""
    new_device = Device(**payload.model_dump())
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)
    return new_device

@router.get("/", response_model=List[DeviceRead])
async def list_devices(
    db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user) 
):
    """List all devices."""
    result = await db.execute(sa.select(Device).order_by(Device.createdAt.desc()))
    return result.scalars().all()

@router.get("/{device_id}", response_model=DeviceRead)
async def read_device(
    device_id: str, 
    db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user) 
):
    """Get one device details."""
    return await _get_device_or_404(db, device_id)

@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: str, 
    payload: DeviceUpdate, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_admin_user)
):
    """Update device info (name, room, type...)."""
    device = await _get_device_or_404(db, device_id)
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)
    
    # Broadcast UI update
    user_ids = await DeviceHandler._get_authorized_users(db, device.id, device.hardwareId)
    if user_ids:
        ws_payload = {
            "event": "info_updated",
            "device_id": device.id,
            "data": {
                "name": device.name,
                "room": device.room
            }
        }
        for uid in user_ids:
            await realtime_manager.send_to_user(uid, ws_payload)

    # Add history log
    await add_history_record(
        device_id=device.id,
        device_name=device.name,
        action="Updated device configuration info",
        actor=str(admin.id),
        source="Web API (Update)"
    )

    return device

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_admin_user)
):
    """Delete a device."""
    device = await _get_device_or_404(db, device_id)

    # Keep name before delete for history logging
    deleted_device_name = device.name

    await db.delete(device)
    await db.commit()

    # Add history log
    await add_history_record(
        device_id=device_id,
        device_name=deleted_device_name,
        action="Removed device from system",
        actor=str(admin.id),
        source="Web API (Delete)"
    )


# --- PART 2: MQTT CONTROL ---

class DeviceControlRequest(BaseModel):
    isOn: bool
    value: int = Field(0, ge=0, le=1023)

@router.post("/{device_id}/command")
async def send_command(
    device_id: str, 
    payload: DeviceControlRequest, 
    db: AsyncSession = Depends(get_db), 
    user: User = Depends(get_current_user) 
):
    """Web client calls this API to send command via MQTT to YoloBit hardware."""
    device = await _get_device_or_404(db, device_id)
    
    if not device.hardwareId or not device.pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Device is not linked to hardware"
        )

    # Send command via MQTT
    try:
        from app.main import mqtt_service 
        await mqtt_service.publish_command(
            hardware_id=device.hardwareId,
            pin=device.pin,
            is_on=payload.isOn,
            value=payload.value
        )

        # Add history log
        action_detail = f"Sent command: {'ON' if payload.isOn else 'OFF'} (Value: {payload.value})"
        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action=action_detail,
            actor=str(user.id), 
            source="Web Command"
        )
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"MQTT publish error: {e}")
    
    # DB state is updated after hardware sends response to 'state' topic
    return {"status": "success", "message": "Command sent to hardware"}


# --- PART 3: SCHEDULES ---

@router.post("/{device_id}/schedules", response_model=DeviceScheduleRead)
async def create_schedule(
    device_id: str, 
    payload: DeviceScheduleCreate, 
    db: AsyncSession = Depends(get_db), 
    user: User = Depends(get_current_user)
):
    """Create a schedule for a device."""
    device = await _get_device_or_404(db, device_id)
        
    schedule = DeviceSchedule( 
        device_id=device_id, 
        action=payload.action,
        time_of_day=payload.time_of_day.replace(second=0, microsecond=0),
        created_by_id=user.id
    )
    db.add(schedule)
    await db.commit()
    return schedule

@router.get("/{device_id}/history", response_model=List[DeviceLogRead])
async def get_device_history(
    device_id: str, 
    db: AsyncSession = Depends(get_db), 
    user: User = Depends(get_current_user),
    limit: int = 20
):
    """Get history logs for a specific device."""
    # Ensure device exists
    await _get_device_or_404(db, device_id)
    
    # Query logs ordered by newest first
    stmt = sa.select(DeviceLog).where(DeviceLog.device_id == device_id).order_by(DeviceLog.created_at.desc()).limit(limit)
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
    * **Client -> Server (Keepalive):** Send `{"type": "ping"}` periodically to receive `{"type": "pong"}`.

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
      "data": { "isOn": true, "value": 1023 }
    }
    ```
    """
    return {"detail": "This is a documentation page, not a live endpoint."}