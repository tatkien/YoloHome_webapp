from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.device import Device
from app.core.logger import add_history_record
from app.schemas.device import DeviceControlRequest

async def device_command(
    db: AsyncSession,
    device_id: str, 
    is_on: bool, 
    value: float, 
    actor: str, 
    source: str
) -> dict:
    """Hàm dùng chung để bắn lệnh thiết bị qua MQTT"""
    
    # 1. Lọc thông tin thiết bị
    stmt = select(Device).where(Device.id == device_id)
    res = await db.execute(stmt)
    device = res.scalar_one_or_none()
    
    if not device:
        raise ValueError("Không tìm thấy thiết bị")
        
    if not device.hardware_id or not device.pin:
        raise ValueError("Thiết bị chưa liên kết phần cứng")

    # 2. Giao tiếp MQTT
    from app.main import mqtt_service 
    
    payload = DeviceControlRequest(is_on=is_on, value=value)
    await mqtt_service.publish_command(
        hardware_id=device.hardware_id,
        pin=device.pin,
        payload=payload
    )

    # 3. Lưu log hành động
    action_detail = f"Gửi lệnh: {'Bật' if is_on else 'Tắt'} (Giá trị: {value})"
    await add_history_record(
        device_id=device.id,
        device_name=device.name,
        action=action_detail,
        actor=actor, 
        source=source
    )
    
    return {"status": "success", "message": "Lệnh đã được gửi xuống máy chủ phần cứng"}
