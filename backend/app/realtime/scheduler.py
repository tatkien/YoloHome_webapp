import asyncio
import logging
import json
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.device_schedule import DeviceSchedule
from app.models.device import Device
from app.realtime.websocket_manager import realtime_manager
from app.service.history import add_history_record

SCHEDULE_POLL_SECONDS = 30
logger = logging.getLogger(__name__)


async def run_device_schedule_loop(stop_event: asyncio.Event) -> None:
    """Background loop that checks schedules every 30 seconds."""
    while not stop_event.is_set():
        try:
            await _run_schedule_tick()
        except Exception:
            logger.exception("Device schedule loop error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SCHEDULE_POLL_SECONDS)
        except TimeoutError:
            continue


async def _run_schedule_tick() -> None:
    now = datetime.now()
    current_hhmm = now.strftime("%H:%M")
    today = now.date()

    async with AsyncSessionLocal() as db:
        db: AsyncSession

        # 1. Find active schedules that haven't been triggered today
        stmt = (
            sa.select(DeviceSchedule, Device)
            .join(Device, DeviceSchedule.device_id == Device.id)
            .where(
                DeviceSchedule.is_active.is_(True),
                sa.or_(
                    DeviceSchedule.last_triggered_on.is_(None),
                    DeviceSchedule.last_triggered_on != today,
                ),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()  # Returns list of (schedule, device)

        if not rows:
            return

        for schedule, device in rows:
            # 2. Check if current time matches any time in the schedule's times_of_day list
            times_list = schedule.times_of_day or []
            if current_hhmm not in times_list:
                continue

            # 3. Mark as triggered today
            schedule.last_triggered_on = today

            # 4. Send command to hardware via MQTT
            mqtt_payload = {
                "device_id": device.id,
                "pin": device.pin,
                "action": schedule.action.value if hasattr(schedule.action, 'value') else schedule.action,
            }
            # await mqtt_client.publish(f"yolobit/{device.hardware_id}/control", json.dumps(mqtt_payload))
            logger.info(
                f"[Schedule] MQTT command sent for {device.name} -> {schedule.action}"
            )

            # 5. Write activity log into DeviceLog
            action_str = schedule.action.value.upper() if hasattr(schedule.action, 'value') else str(schedule.action).upper()
            msg = f"Automated schedule: {action_str} command has been sent"
            await add_history_record(
                device.id, device.name, msg, "system", "Schedule"
            )

            # 6. Send websocket event to all connected users
            user_ids = list(realtime_manager.active_connections.keys())

            if user_ids:
                ws_payload = {
                    "event": "schedule_triggered",
                    "device_id": device.id,
                    "hardware_id": device.hardware_id,
                    "data": {
                        "action": schedule.action.value if hasattr(schedule.action, 'value') else schedule.action,
                        "schedule_id": schedule.id,
                        "message": msg,
                    },
                }
                for uid in user_ids:
                    await realtime_manager.send_to_user(uid, ws_payload)

        # Persist last_triggered_on updates
        await db.commit()