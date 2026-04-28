from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.device import Device
from app.schemas.device import DeviceControlRequest
from app.core.config import settings
from app.service.history_service import add_history_record

async def device_command(
    db: AsyncSession,
    device_id: str, 
    is_on: Optional[bool], 
    value: Optional[float], 
    actor: str, 
    source: str
) -> dict:
    """Hàm dùng chung để gửi lệnh điều khiển thiết bị qua MQTT"""
    
    # 1. Lấy thông tin thiết bị
    stmt = select(Device).where(Device.id == device_id)
    res = await db.execute(stmt)
    device = res.scalar_one_or_none()
    
    if not device:
        raise ValueError("Không tìm thấy thiết bị")
        
    if not device.hardware_id or not device.pin:
        raise ValueError("Thiết bị chưa liên kết phần cứng")
    
    # 2. Validate Schema
    try:
        DeviceControlRequest(is_on=is_on, value=value)
    except Exception as e:
        raise ValueError(f"Dữ liệu không hợp lệ: {str(e)}")
    
    # 3. Kiểm tra dải giá trị (theo cấu hình của từng loại thiết bị)
    meta = device.meta_data or {}
    if value is not None:
        if "range" in meta:
            v_min, v_max = meta["range"]
            if not (v_min <= value <= v_max):
                raise ValueError(f"Giá trị {value} ngoài dải [{v_min}-{v_max}]")
        elif "allowed_values" in meta:
            if value not in meta["allowed_values"]:
                raise ValueError(f"Giá trị {value} không nằm trong danh sách cho phép")    
    
    # 4. Khởi tạo trạng thái cuối cùng 
    dev_type = device.type.lower()
    default_config = settings.DEFAULT_DEVICE_METADATA.get(dev_type, {})
    default_v = default_config.get("default_value", 1.0)
    
    # Xác định final_is_on và final_value
    if is_on is False:
        final_is_on = False
        final_value = 0.0
    elif is_on is True and value is None:
        final_is_on = True
        final_value = meta.get("default_value", default_v)
    elif value is not None and value > 0 and is_on is None:
        final_is_on = True
        final_value = value
    elif is_on is not None and value is not None:
        final_is_on = is_on
        final_value = value
    else:
        final_is_on = device.is_on
        final_value = device.value

    # Nếu thiết bị bật mà giá trị bằng 0 thì dùng giá trị mặc định
    if final_is_on and final_value == 0:
        final_value = meta.get("default_value", default_v)

    # 5. Giao tiếp MQTT
    from app.main import mqtt_service 
    
    mqtt_payload = {
        "is_on": final_is_on,
        "value": int(final_value) if dev_type in ["fan", "light", "lock"] else final_value
    }

    await mqtt_service.publish_command(
        hardware_id=device.hardware_id,
        pin=device.pin,
        payload=mqtt_payload
    )

    # 6. Lưu log nhật ký thiết bị
    action_detail = f"Gửi lệnh: {'Bật' if final_is_on else 'Tắt'} (Giá trị: {final_value})"
    await add_history_record(
        device_id=device.id,
        device_name=device.name,
        action=action_detail,
        actor=actor, 
        source=source
    )
    
    # Lưu thay đổi vào db
    await db.commit()
    return {"status": "success", "message": f"Đã gửi lệnh tới {device.name}"}
