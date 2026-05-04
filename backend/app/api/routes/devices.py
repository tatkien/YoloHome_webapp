from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_admin_user, get_db
from app.models.user import User
from app.schemas.device import DeviceType, DeviceRead, DeviceUpdate, DeviceCreate, DeviceControlRequest, SensorDataRead, DeviceLogRead, SensorHistoryRead
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleUpdate, DeviceScheduleRead
from app.schemas.hardware import HardwareNodeSummary, HardwareNodeRead
from app.core.logger import logger
from app.service.device_service import DeviceService, HardwareService
from app.service.schedule_service import ScheduleService
from app.service.voice_intent import voice_intent_service
from app.service.history_service import get_sensor_data_history as get_sensor_history_service, get_device_history as get_device_history_service

router = APIRouter(prefix="/devices", tags=["devices"])

# --- HARDWARE MANAGEMENT ---
@router.get("/hardware", response_model=List[HardwareNodeSummary])
async def list_hardware_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Lấy danh sách mạch"""
    return await HardwareService.list_hardware_nodes(db)


@router.get("/hardware/{hardware_id}", response_model=HardwareNodeRead)
async def read_hardware_node(
    hardware_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get details for one hardware board."""
    return await HardwareService.read_hardware_node(db, hardware_id)

@router.delete("/hardware/{hardware_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hardware_node(
    hardware_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Delete a hardware board and all child devices."""
    await HardwareService.delete_hardware_node(db, hardware_id)


@router.post("/", response_model=DeviceRead)
async def create_device(
    payload: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Admin creates a new device mapped to a hardware pin."""
    device = await DeviceService.create_device(db, payload, str(admin.id))
    # Load lại cache cho Voice AI
    await voice_intent_service.reload_cache(db)
    return device



@router.get("/", response_model=List[DeviceRead])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all devices."""
    return await DeviceService.list_devices(db)

@router.get("/get-camera-devices", response_model=List[DeviceRead])
async def get_camera_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get all camera devices."""
    return await DeviceService.get_camera_devices(db)

@router.get("/sensor-data", response_model=List[SensorHistoryRead])
async def get_sensor_data_history(
    device_id: Optional[str] = Query(None, description="Filter by specific device ID"),
    sensor_type: Optional[DeviceType] = Query(None, description="Filter by sensor type (temp_sensor, humidity_sensor)"),
    limit: int = Query(50, ge=1, le=1000),
    time_range: Optional[str] = Query(None, alias="range", description="Time range (1h, 24h, 7d)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Unified endpoint to get sensor data history with optional time range filtering.
    """
    return await get_sensor_history_service(db, device_id, sensor_type, limit, time_range)


@router.get("/{device_id}/history", response_model=List[DeviceLogRead])
async def get_device_history(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """Lấy nhật ký hoạt động gần nhất của 1 thiết bị."""
    return await get_device_history_service(db, device_id, limit)


@router.get("/{device_id}", response_model=DeviceRead)
async def read_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get one device details."""
    return await DeviceService.get_device(db, device_id)


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Cập nhật thông tin thiết bị (tên, phòng,...)."""
    logger.info(f"[API] Nhận yêu cầu PATCH cho thiết bị: {device_id}")
    device = await DeviceService.update_device(db, device_id, payload, str(admin.id))
    await voice_intent_service.reload_cache(db)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Delete a device."""
    await DeviceService.delete_device(db, device_id, str(admin.id))
    await voice_intent_service.reload_cache(db)

# --- CONTROL ---
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
        success = await DeviceService.send_command(
            db=db,
            device_id=device_id,
            is_on=payload.is_on,
            value=payload.value,
            actor=user.username,
            source="Web Dashboard"
        )
        return {"status": "success" if success else "failed"}
    except ValueError as str_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(str_err)
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Publish Command Error: {e}",
        )

# --- SCHEDULES ---
@router.post("/{device_id}/schedules", response_model=DeviceScheduleRead)
async def create_schedule(
    device_id: str,
    payload: DeviceScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Create a schedule for a device."""
    return await ScheduleService.create_schedule(db, device_id, payload)


@router.get("/{device_id}/schedules", response_model=List[DeviceScheduleRead])
async def list_schedules(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all schedules for a device."""
    return await ScheduleService.list_schedules(db, device_id)


@router.put("/schedules/{schedule_id}", response_model=DeviceScheduleRead)
async def update_schedule(
    schedule_id: str,
    payload: DeviceScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Update a device schedule."""
    return await ScheduleService.update_schedule(db, schedule_id, payload)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Delete a device schedule."""
    await ScheduleService.delete_schedule(db, schedule_id)
