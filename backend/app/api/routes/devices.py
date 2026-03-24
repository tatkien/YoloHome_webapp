from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

# Import các thành phần hệ thống của bạn
from app.api.deps import get_current_user, get_admin_user, get_db
from app.models.device import Device
from app.models.user import User

from app.schemas.device import DeviceRead, DeviceUpdate, DeviceCreate
from app.schemas.schedule import DeviceScheduleCreate, DeviceScheduleRead
from app.models.device import HardwareNode
from app.schemas.hardware import HardwareNodeRead
# from app.main import mqtt_service 
from app.realtime.websocket_manager import realtime_manager
from app.service.history import add_history_record

router = APIRouter(prefix="/devices", tags=["devices"])

# --- HÀM HỖ TRỢ ---
async def _get_device_or_404(db: AsyncSession, device_id: str) -> Device:
    """Tìm thiết bị bằng UUID hoặc trả về lỗi 404"""
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thiết bị")
    return device


# --- PHẦN QUẢN LÝ MẠCH (HARDWARE) ---

@router.get("/hardware", response_model=List[HardwareNodeRead])
async def list_hardware_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Lấy danh sách bo mạch YoloBit và các chân (pins)"""
    # Gắn selectinload để Database gói luôn các thiết bị con đi kèm, không bị lỗi Lazy Load
    query = sa.select(HardwareNode).options(selectinload(HardwareNode.devices))
    result = await db.execute(query)
    return result.scalars().unique().all() 

@router.get("/hardware/{hardware_id}", response_model=HardwareNodeRead)
async def read_hardware_node(
    hardware_id: str, 
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user) # Đã khôi phục khoá User
):
    """Xem chi tiết 1 bo mạch"""
    query = sa.select(HardwareNode).where(HardwareNode.id == hardware_id).options(selectinload(HardwareNode.devices))
    result = await db.execute(query)
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bo mạch này")
    return node

@router.delete("/hardware/{hardware_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hardware_node(
    hardware_id: str, 
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user) # Đã khôi phục khoá Admin
):
    """XOÁ bo mạch và tự động xóa tất cả thiết bị con thuộc về mạch này"""
    # 1. Tìm bo mạch
    result = await db.execute(sa.select(HardwareNode).where(HardwareNode.id == hardware_id))
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bo mạch")

    # 2. Xóa bo mạch (Database sẽ tự lo phần xoá các thiết bị con nhờ Cascade)
    await db.delete(node)
    await db.commit()


# --- PHẦN 1: CRUD QUẢN LÝ THIẾT BỊ ---

@router.get("/", response_model=List[DeviceRead])
async def list_devices(
    db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user) # Đã khôi phục khoá User
):
    """Lấy danh sách tất cả thiết bị"""
    result = await db.execute(sa.select(Device).order_by(Device.createdAt.desc()))
    return result.scalars().all()

@router.get("/{device_id}", response_model=DeviceRead)
async def read_device(
    device_id: str, 
    db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user) # Đã khôi phục khoá User
):
    """Xem chi tiết 1 thiết bị"""
    return await _get_device_or_404(db, device_id)

@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: str, 
    payload: DeviceUpdate, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_admin_user) # Đã khôi phục khoá Admin
):
    """Cập nhật thông tin (Tên, phòng, loại...)"""
    device = await _get_device_or_404(db, device_id)
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)
    
    # Broadcast cập nhật UI
    await realtime_manager.broadcast_device_event(device_id, {"type": "device.updated"})

    # Thêm log lịch sử
    await add_history_record(
        device_id=device.id,
        device_name=device.name,
        action="Cập nhật thông tin cấu hình thiết bị",
        actor=str(admin.id), # Lấy ID thực tế
        source="Web API (Update)"
    )

    return device

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str, 
    db: AsyncSession = Depends(get_db), 
    admin: User = Depends(get_admin_user) # Đã khôi phục khoá Admin
):
    """Xóa thiết bị"""
    device = await _get_device_or_404(db, device_id)

    # Lưu lại tên trước khi xoá để ghi log
    deleted_device_name = device.name

    await db.delete(device)
    await db.commit()

    # Thêm log lịch sử
    await add_history_record(
        device_id=device_id,
        device_name=deleted_device_name,
        action="Xóa thiết bị khỏi hệ thống",
        actor=str(admin.id), # Lấy ID thực tế
        source="Web API (Delete)"
    )


# --- PHẦN 2: ĐIỀU KHIỂN QUA MQTT ---

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
    """Web gọi API này để gửi lệnh xuống mạch YoloBit qua MQTT"""
    device = await _get_device_or_404(db, device_id)
    
    if not device.hardwareId or not device.pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Thiết bị chưa liên kết phần cứng"
        )

    # Bắn lệnh qua MQTT
    try:
        from app.main import mqtt_service 
        await mqtt_service.publish_command(
            hardware_id=device.hardwareId,
            pin=device.pin,
            is_on=payload.isOn,
            value=payload.value
        )

        # Thêm log lịch sử
        action_detail = f"Gửi lệnh: {'Bật' if payload.isOn else 'Tắt'} (Giá trị: {payload.value})"
        await add_history_record(
            device_id=device.id,
            device_name=device.name,
            action=action_detail,
            actor=str(user.id), # Lấy ID thực tế
            source="Web Command"
        )
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gửi MQTT: {e}")
    
    # Đợi mạch phản hồi vào topic 'state' thì DB mới cập nhật
    return {"status": "success", "message": "Lệnh đã được gửi xuống mạch"}


# --- PHẦN 3: LỊCH TRÌNH ---

@router.post("/{device_id}/schedules", response_model=DeviceScheduleRead)
async def create_schedule(
    device_id: str, 
    payload: DeviceScheduleCreate, 
    db: AsyncSession = Depends(get_db), 
    user: User = Depends(get_current_user) # Đã khôi phục khoá User
):
    """Hẹn giờ cho thiết bị"""
    device = await _get_device_or_404(db, device_id)
        
    schedule = DeviceSchedule( # Lưu ý: Cần import DeviceSchedule nếu chưa có
        device_id=device_id, 
        action=payload.action,
        time_of_day=payload.time_of_day.replace(second=0, microsecond=0),
        created_by_id=str(user.id) # Ghi nhận ID của người đặt lịch
    )
    db.add(schedule)
    await db.commit()
    return schedule

@router.get("/docs-websocket-info", tags=["Tài liệu WebSocket (Chỉ tra cứu)"])
async def websocket_documentation_only():
    """
    ### ⚠️ LƯU Ý: ĐÂY LÀ API GIẢ (DÙNG ĐỂ TRA CỨU TÀI LIỆU)
    **không bấm "Execute" vì API này không trả về dữ liệu thực.**
    
    Hệ thống sử dụng WebSocket để cập nhật dữ liệu thời gian thực (Real-time). Dưới đây là hướng dẫn kết nối:

    ---
    ### 1. Link theo dõi dữ liệu cảm biến
    Dùng để nhận dữ liệu từ một mạch.
    * **URL:** `ws://{{host}}/api/v1/ws/hardware/{hardware_id}?token={{your_jwt_token}}`
    * **Tham số:** * `hardware_id`: ID của mạch (VD: `MOCK_BOARD`)
        * `token`: Truyền JWT Token trực tiếp vào URL sau dấu `?`
    
    ---
    ### 2. Link theo dõi trạng thái thiết bị lẻ
    Dùng để nhận dữ liệu từ 1 thiết bị.
    * **URL:** `ws://{{host}}/api/v1/ws/devices/{device_id}?token={{your_jwt_token}}`
    * **Tham số:** * `device_id`: UUID của thiết bị trong Database.

    ---
    ### 3. Giao thức tin nhắn (JSON)
    Khi đã kết nối thành công, Server và Client sẽ nói chuyện qua định dạng JSON:

    * **Server -> Client (Lúc mới nối):** `{"type": "subscription.ready", "id": "..."}`
    * **Client -> Server (Giữ mạng):** Gửi text: `"ping"` (định kỳ) để nhận lại `{"type": "pong"}`.

    **Khi có cập nhật cảm biến (Hardware Stream):**
    ```json
    {
      "event": "sensor_update",
      "hardware_id": "MOCK_BOARD",
      "data": { "temp": 28, "humi": 70 }
    }
    ```
    **Khi có thay đổi trạng thái thiết bị (Device Stream):**
    ```json
    {
      "event": "device_state_update",
      "device_id": "uuid-cua-thiet-bi",
      "data": { "value": 2, "isOn": true, "status": "success" }
    }
    ```
    ---
    **Công cụ test khuyến nghị:** [Postman] (Chọn WebSocket).
    """
    return {"detail": "Đây là trang tài liệu, không phải API thực tế."}