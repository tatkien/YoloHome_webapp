from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

from app.db.session import AsyncSessionLocal
from app.models.device import Device, DeviceLog, SensorData
from app.schemas.device import DeviceType
from app.core.logger import logger

async def add_history_record(
    device_id: str, 
    device_name: str, 
    action: str, 
    actor: str|int, 
    source: str
):
    """
    Ghi nhật ký hành động thiết bị vào log file và bảng device_logs trong DB
    """
    log_msg = f"[HISTORY] Device: {device_name} ({device_id}) | Action: {action} | Actor: {actor} | Source: {source}"
    logger.info(log_msg)

    # Lọc không ghi vào dữ liệu cảm biến
    if action.startswith("[Sensor]"):
        return

    # Ghi vào bảng device_logs
    async with AsyncSessionLocal() as session:
        try:
            new_log = DeviceLog(
                device_id=device_id,
                device_name=device_name,
                action=action,
                actor=str(actor),
                source=source,
            )
            session.add(new_log)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"[History Service] Lỗi DB cho thiết bị {device_name}: {e}")

async def get_device_history(db: AsyncSession, device_id: str, limit: int = 20) -> List[DeviceLog]:
    """Lấy lịch sử hoạt động của thiết bị"""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")

    stmt = (
        sa.select(DeviceLog)
        .where(DeviceLog.device_id == device_id)
        .order_by(DeviceLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_sensor_data_history(
    db: AsyncSession,
    device_id: Optional[str] = None,
    sensor_type: Optional[DeviceType] = None,
    limit: int = 50,
    time_range: Optional[str] = None
) -> List[SensorData]:
    """Lấy lịch sử dữ liệu cảm biến"""
    stmt = sa.select(SensorData)
    
    if device_id:
        device = await db.get(Device, device_id)
        if not device:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Device not found")
        stmt = stmt.where(SensorData.device_id == device_id)
        
    if sensor_type:
        if sensor_type not in [DeviceType.TEMP, DeviceType.HUMI]:
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
        stmt = stmt.order_by(SensorData.created_at.desc()).limit(2000) 
    else:
        stmt = stmt.order_by(SensorData.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()
