from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.device import Device, DeviceLog, SensorData
from app.schemas.device import DeviceType, SensorHistoryRead
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
) -> List[SensorHistoryRead]:
    """Lấy lịch sử dữ liệu cảm biến (có hỗ trợ gom nhóm theo thời gian)"""
    # Xác định mốc gom nhóm, khoảng gom
    now = datetime.utcnow()
    interval = 0
    start_time = None

    if time_range == "1h":
        start_time = now - timedelta(hours=1)
    elif time_range == "24h":
        start_time = now - timedelta(hours=24)
        interval = 300  # 5 phút
    elif time_range == "7d":
        start_time = now - timedelta(days=7)
        interval = 1800  # 30 phút

    # Query
    if interval > 0:
        logger.info(f"[History] Đang gom nhóm: device={device_id}, interval={interval}s, range={time_range}")
        time_bucket = sa.func.to_timestamp(
            sa.func.floor(sa.func.extract('epoch', SensorData.created_at) / interval) * interval
        ).label("created_at")

        stmt = sa.select(
            SensorData.device_id,
            sa.func.avg(SensorData.value).label("value"),
            sa.func.min(SensorData.value).label("min_value"),
            sa.func.max(SensorData.value).label("max_value"),
            SensorData.sensor_type,
            time_bucket
        ).group_by(
            SensorData.device_id,
            SensorData.sensor_type,
            sa.text("created_at")
        ).order_by(sa.text("created_at DESC"))
    else:
        logger.info(f"[History] Lấy dữ liệu thô: device={device_id}, range={time_range}")
        stmt = sa.select(SensorData).order_by(SensorData.created_at.desc())

    # Filter
    if device_id:
        stmt = stmt.where(SensorData.device_id == device_id)
    if sensor_type:
        stmt = stmt.where(SensorData.sensor_type == sensor_type)
    if start_time:
        stmt = stmt.where(SensorData.created_at >= start_time)

    # Thực thi
    if interval > 0:
        stmt = stmt.limit(2000)
        result = await db.execute(stmt)
        return [
            {
                "device_id": row.device_id,
                "value": round(float(row.value), 2),
                "min_value": round(float(row.min_value), 2),
                "max_value": round(float(row.max_value), 2),
                "sensor_type": row.sensor_type,
                "created_at": row.created_at
            }
            for row in result.all()
        ]
    else:
        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return [
            {
                "device_id": row.device_id,
                "value": row.value,
                "min_value": row.value,
                "max_value": row.value,
                "sensor_type": row.sensor_type,
                "created_at": row.created_at
            }
            for row in result.scalars().all()
        ]
