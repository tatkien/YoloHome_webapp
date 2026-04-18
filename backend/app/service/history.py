from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.device import DeviceLog, SensorData 
from app.models.device import DeviceTypeEnum

async def add_history_record(
    device_id: str, 
    device_name: str, 
    action: str, 
    actor: str|int, 
    source: str,
    db: AsyncSession = None
):
    """
    Shared helper to store system activity records in DeviceLog.
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1. Create a new log record
            new_log = DeviceLog(
                device_id=device_id,
                device_name=device_name,
                action=action,
                actor=actor,
                source=source
            )
            
            # 2. Persist to database
            session.add(new_log)
            await session.commit()
            
        except Exception as e:
            # 3. Roll back on database error
            await session.rollback()
            print(f"[History Service] Failed to write history for device {device_name}: {e}")

async def add_sensor_data(
    device_id: str,
    value: float,
    sensor_type: DeviceTypeEnum,
    db: AsyncSession = None
):
    """
    Store time-series sensor data in SensorData table.
    """
    async with AsyncSessionLocal() as session:
        try:
            new_data = SensorData(
                device_id=device_id,
                value=value,
                sensor_type=sensor_type
            )
            session.add(new_data)
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"[History Service] Failed to write sensor data for device {device_id}: {e}") 