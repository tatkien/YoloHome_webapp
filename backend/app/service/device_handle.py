import uuid
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.device import Device, HardwareNode, SensorData
from app.schemas.device import DeviceType
from app.schemas.mqtt import MqttAnnounceSchema, MqttStateSchema
from app.service.ws_service import realtime_manager
from app.core.logger import logger
from app.service.history_service import add_history_record


class DeviceHandler:
    @staticmethod
    async def _get_authorized_users() -> list[int]:
        """Lấy hết danh sách ID người dùng đang kết nối Websocket."""
        return list(realtime_manager.active_connections.keys())

    @staticmethod
    async def process_announce(hardware_id: str, payload: dict):
        """Handle hardware announce message."""
        data = MqttAnnounceSchema(**payload)
        async with AsyncSessionLocal() as session:
            session: AsyncSession
            stmt = select(HardwareNode).where(HardwareNode.id == hardware_id)
            res = await session.execute(stmt)
            node = res.scalar_one_or_none()

            pin_list_for_db = [p.model_dump() for p in data.pins]

            if node:
                node.name = data.name
                node.pins = pin_list_for_db
            else:
                # New hardware node, create in DB
                new_node = HardwareNode(id=hardware_id, name=data.name, pins=pin_list_for_db)
                session.add(new_node)
            await session.commit()
            logger.info(f"[Handler] Đã cập nhật phần cứng: {hardware_id}")

            for p_config in data.pins:
                if p_config.type == DeviceType.UNKNOWN:
                    logger.info(f"[Handler] Bỏ qua tự tạo thiết bị cho chân {p_config.pin} (Type: unknown)")
                    continue 

                dev_stmt = select(Device).where(Device.hardware_id == hardware_id, Device.pin == p_config.pin)
                dev_res = await session.execute(dev_stmt)
                device = dev_res.scalar_one_or_none()

                if not device:
                    # Tự tạo thiết bị nếu type khác unknown
                    new_device = Device(
                        id=str(uuid.uuid4()),
                        name=f"{p_config.type.value.upper()} ({p_config.pin})",
                        type=p_config.type,
                        hardware_id=hardware_id,
                        pin=p_config.pin,
                        is_on=False,
                        value=0
                    )
                    session.add(new_device)
                    logger.info(f"[Handler] Auto-created {p_config.type} on {p_config.pin}")
                else:
                    # Cập nhật type thiết bị nếu đã tồn tại
                    device.type = p_config.type
        
            await session.commit()

    @staticmethod
    async def process_state(hardware_id: str, payload: dict):
        """Handle state feedback (servo/light/fan)."""
        data = MqttStateSchema(**payload)
        # Check if status is not "success", if so, log and skip DB update
        if data.status.lower() != "success":
            logger.warning(
                f"[Handler] Nhận trạng thái lỗi từ phần cứng {hardware_id} "
                f"cho pin {data.pin}: {data.status}"
            )
            return

        logger.debug(f"[Handler] Đang xử lý trạng thái cho {hardware_id} pin {data.pin}")

        async with AsyncSessionLocal() as session:
            session: AsyncSession

            try:
                stmt = select(Device).where(
                    Device.hardware_id == hardware_id, Device.pin == data.pin
                )
                res = await session.execute(stmt)
                device = res.scalar_one_or_none()

                if device:
                    new_value = data.value
                    new_is_on = data.is_on

                    if device.is_on != new_is_on or device.value != new_value:
                        device.is_on = new_is_on
                        device.value = new_value  # @validates on Device handles range checks

                        logger.info(f"[Handler] Đã đồng bộ thiết bị {data.pin} trên phần cứng {hardware_id}")
                        msg = f"Updated: {'ON' if new_is_on else 'OFF'}, Value: {new_value}"
                        await add_history_record(
                            device.id, device.name, f"[Feedback] {msg}", "system", "Hardware",
                        )
                        await session.commit()

                        # Gửi Websocket khi mạch phản hồi thay đổi trạng thái
                        user_ids = await DeviceHandler._get_authorized_users()
                        if user_ids:
                            ws_payload = {
                                "event": "device_update",
                                "device_id": device.id,
                                "hardware_id": hardware_id,
                                "data": {"is_on": data.is_on, "value": data.value},
                            }
                            for uid in user_ids:
                                await realtime_manager.send_to_user(uid, ws_payload)

                    else:
                        logger.debug(f"[Handler] Bỏ qua state của chân {data.pin} vì thiết bị chưa được setup")

            except Exception as e:
                await session.rollback()
                logger.error(f"[Handler] Lỗi xử lý state: {e}")

    @staticmethod
    async def process_sensor(hardware_id: str, payload: dict):
        """Handle sensor payloads (temperature/humidity)."""
        async with AsyncSessionLocal() as session:
            session: AsyncSession

            try:
                for pin_name, val in payload.items():
                    stmt = select(Device).where(
                        Device.hardware_id == hardware_id, Device.pin == pin_name
                    )
                    res = await session.execute(stmt)
                    device = res.scalar_one_or_none()

                    if not device:
                        logger.debug(f"[Handler] Bỏ qua chân cảm biến lạ: {pin_name}")
                        continue

                    # Cập nhật giá trị cảm biến
                    device.value = val
                    device.is_on = True
                    
                    # Lưu vào bảng sensor_data
                    new_sensor_data = SensorData(
                        device_id=device.id,
                        value=val,
                        sensor_type=device.type 
                    )
                    session.add(new_sensor_data)       
                await session.commit()
                        
                # Gửi Websocket
                # Hiện không phân quyền mặc định trả về tất cả
                user_ids = await DeviceHandler._get_authorized_users()
                if user_ids:
                    ws_payload = {
                        "event": "sensor_update",
                        "hardware_id": hardware_id,
                        "data": payload,
                    }
                    for uid in user_ids:
                        await realtime_manager.send_to_user(uid, ws_payload)

            except Exception as e:
                await session.rollback()
                logger.error(f"[Handler] Lỗi cập nhật cảm biến: {e}")
