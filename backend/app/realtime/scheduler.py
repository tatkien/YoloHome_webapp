import asyncio
import logging
from datetime import datetime

import sqlalchemy as sa

from app.db.session import AsyncSessionLocal
from app.models.device_schedule import DeviceSchedule
from app.realtime.websocket_manager import realtime_manager

SCHEDULE_POLL_SECONDS = 30

logger = logging.getLogger(__name__)


async def run_device_schedule_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await _run_schedule_tick()
        except Exception:
            logger.exception("Device schedule loop failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SCHEDULE_POLL_SECONDS)
        except TimeoutError:
            continue


async def _run_schedule_tick() -> None:
    now = datetime.now()
    target_time = now.time().replace(second=0, microsecond=0)
    today = now.date()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa.select(DeviceSchedule).where(
                DeviceSchedule.is_active.is_(True),
                DeviceSchedule.time_of_day == target_time,
                sa.or_(
                    DeviceSchedule.last_triggered_on.is_(None),
                    DeviceSchedule.last_triggered_on != today,
                ),
            )
        )
        schedules = result.scalars().all()
        if not schedules:
            return

        scheduled_commands: list[tuple[DeviceSchedule, Command]] = []
        for schedule in schedules:
            command = Command(
                device_id=schedule.device_id,
                created_by_id=schedule.created_by_id,
                payload={"state": schedule.action},
                status="pending",
            )
            db.add(command)
            schedule.last_triggered_on = today
            scheduled_commands.append((schedule, command))

        await db.commit()

        for schedule, command in scheduled_commands:
            await db.refresh(command)
            message = CommandRead.model_validate(command).model_dump(mode="json")
            await realtime_manager.broadcast_device_event(
                command.device_id,
                {
                    "type": "command.created",
                    "device_id": command.device_id,
                    "command": message,
                    "source": "schedule",
                    "schedule_id": schedule.id,
                },
            )
