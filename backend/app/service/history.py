from app.db.session import AsyncSessionLocal
from app.models.device import DeviceLog 

async def add_history_record(
    device_id: str, 
    device_name: str, 
    action: str, 
    actor: str, 
    source: str
):
    """
    Hàm dùng chung để ghi lại mọi biến động của hệ thống vào bảng DeviceLog.
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1. Khởi tạo đối tượng log mới
            new_log = DeviceLog(
                device_id=device_id,
                device_name=device_name,
                action=action,
                actor=actor,
                source=source
            )
            
            # 2. Thêm vào session và lưu xuống Database
            session.add(new_log)
            await session.commit()
            
        except Exception as e:
            # 3. Rollback nếu có lỗi Database để tránh treo hệ thống
            await session.rollback()
            print(f"[History Service] Lỗi khi ghi lịch sử cho thiết bị {device_name}: {e}")