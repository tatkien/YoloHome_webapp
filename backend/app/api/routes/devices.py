import re
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.security import generate_device_key, hash_secret, verify_secret
from app.db.session import get_db
from app.models.command import Command
from app.models.device import Device
from app.models.feed import Feed
from app.models.user import User
from app.realtime.manager import realtime_manager
from app.schemas.command import CommandAcknowledge, CommandCreate, CommandRead
from app.schemas.device import DeviceCreate, DeviceRead, DeviceWithKey

router = APIRouter(prefix="/devices", tags=["devices"])

# Default feed auto-created for each device type
_DEFAULT_FEED: dict[str, dict] = {
    "light":  {"name": "Light State",    "key": "light-state",    "data_type": "text"},
    "fan":    {"name": "Fan Speed",       "key": "fan-speed",      "data_type": "number"},
    "camera": {"name": "Face Detection",  "key": "face-detection", "data_type": "text"},
}


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


async def _get_device_or_404(db: AsyncSession, device_id: int) -> Device:
    result = await db.execute(sa.select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


async def _get_owned_device(db: AsyncSession, device_id: int, user: User) -> Device:
    """Fetch a device and verify the requesting user owns it."""
    device = await _get_device_or_404(db, device_id)
    if device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return device


async def _authenticate_device(db: AsyncSession, device_id: int, device_key: str | None) -> Device:
    if not device_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Device-Key header is required",
        )
    device = await _get_device_or_404(db, device_id)
    if not device.is_active or not verify_secret(device_key, device.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials",
        )
    return device


def _device_with_key(device: Device, raw_key: str) -> DeviceWithKey:
    return DeviceWithKey(**DeviceRead.model_validate(device).model_dump(), device_key=raw_key)


# ---------------------------------------------------------------------------
# Device CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[DeviceRead])
async def list_devices(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all devices in the home.

    Returns all devices sorted by creation date (newest first).

    Auth: JWT required.
    """
    result = await db.execute(
        sa.select(Device)
        .order_by(Device.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=DeviceWithKey, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new device.

    Accepted device types: ``light``, ``fan``, ``camera``.
    A URL-safe slug is derived from the device name and must be globally unique.
    A default feed is automatically created for the device type:
    - light  → "Light State"   (text)
    - fan    → "Fan Speed"     (number)
    - camera → "Face Detection" (text)

    The plaintext ``device_key`` is included in the response exactly once and
    is never stored — flash it to the hardware immediately.

    Auth: JWT required. Admin only.

    Raises:
        400: Device name produces an empty slug.
        409: A device with a conflicting slug already exists.
    """
    slug = _slugify(payload.name)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device name produces an empty slug",
        )

    existing = await db.execute(
        sa.select(Device).where(Device.slug == slug)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A device with a similar name already exists",
        )

    raw_key = generate_device_key()
    device = Device(
        name=payload.name,
        slug=slug,
        device_type=payload.device_type,
        description=payload.description,
        key_hash=hash_secret(raw_key),
        owner_id=current_user.id,
        is_active=payload.is_active,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)

    # Auto-create the default feed for this device type
    feed_spec = _DEFAULT_FEED[payload.device_type]
    db.add(Feed(
        device_id=device.id,
        name=feed_spec["name"],
        key=feed_spec["key"],
        data_type=feed_spec["data_type"],
    ))
    await db.commit()

    return _device_with_key(device, raw_key)


@router.get("/{device_id}", response_model=DeviceRead)
async def read_device(
    device_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single device by ID.

    Auth: JWT required.

    Raises:
        404: Device not found.
    """
    return await _get_device_or_404(db, device_id)


@router.post("/{device_id}/rotate-key", response_model=DeviceWithKey)
async def rotate_device_key(
    device_id: int,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the hardware authentication key for a device.

    Generates a new random key, immediately invalidating the previous one.
    The physical device will receive ``401`` on all subsequent requests until
    it is reconfigured with the new key.

    The plaintext key is returned once in the response and never stored —
    copy it before closing the response.

    Auth: JWT required. Admin only.

    Raises:
        404: Device not found.
    """
    device = await _get_device_or_404(db, device_id)
    raw_key = generate_device_key()
    device.key_hash = hash_secret(raw_key)
    await db.commit()
    await db.refresh(device)
    return _device_with_key(device, raw_key)


@router.post("/{device_id}/heartbeat", status_code=status.HTTP_200_OK)
async def device_heartbeat(
    device_id: int,
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Record a liveness ping from the physical device.

    Called by the hardware kit or gateway on a fixed interval to signal it is
    online. Updates ``last_seen_at`` on the device record and broadcasts a
    ``device.connected`` WebSocket event to all subscribers of this device.

    Auth: X-Device-Key header required (hardware authentication).

    Raises:
        401: Missing or invalid X-Device-Key, or device is inactive.
        404: Device not found.
    """
    device = await _authenticate_device(db, device_id, x_device_key)
    now = datetime.now(timezone.utc)
    device.last_seen_at = now
    await db.commit()

    await realtime_manager.broadcast_device_event(
        device_id,
        {"type": "device.connected", "device_id": device_id, "timestamp": now.isoformat()},
    )
    return {"status": "ok", "device_id": device_id, "timestamp": now.isoformat()}


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a device and all its associated data.

    Cascade rules on the database model handle removal of related feeds,
    commands, and feed values.

    Auth: JWT required. Admin only.

    Raises:
        404: Device not found.
    """
    device = await _get_device_or_404(db, device_id)
    await db.delete(device)
    await db.commit()


@router.get("/{device_id}/commands", response_model=list[CommandRead])
async def list_device_commands(
    device_id: int,
    command_status: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all commands issued to a device, with optional status filtering.

    Use the ``?status=`` query parameter to filter by command lifecycle state:
    ``pending``, ``delivered``, or ``acknowledged``.
    Results are ordered by creation time (newest first).

    This is a read-only endpoint with no side effects — commands are not
    mutated or consumed by this call.

    Auth: JWT required.

    Raises:
        404: Device not found.
    """
    await _get_device_or_404(db, device_id)
    query = sa.select(Command).where(Command.device_id == device_id)
    if command_status:
        query = query.where(Command.status == command_status)
    result = await db.execute(query.order_by(Command.created_at.desc()))
    return result.scalars().all()


@router.post("/{device_id}/commands", response_model=CommandRead, status_code=status.HTTP_201_CREATED)
async def create_command(
    device_id: int,
    payload: CommandCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a command to a device.

    Creates a new command in ``pending`` status and broadcasts a
    ``command.created`` WebSocket event so the dashboard can reflect the
    change immediately.

    If ``feed_id`` is provided it must belong to the target device; this ties
    the command to a specific feed (e.g. set fan speed on the fan-speed feed).
    Omit ``feed_id`` to send a generic device-level command.

    The physical device picks up the command via ``GET /commands/pending``.

    Auth: JWT required.

    Raises:
        400: ``feed_id`` does not belong to the specified device.
        404: Device not found.
    """
    await _get_device_or_404(db, device_id)
    if payload.feed_id is not None:
        result = await db.execute(
            sa.select(Feed).where(
                Feed.id == payload.feed_id,
                Feed.device_id == device_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feed does not belong to the selected device",
            )

    command = Command(
        device_id=device_id,
        feed_id=payload.feed_id,
        created_by_id=current_user.id,
        payload=payload.payload,
        status="pending",
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)

    command_message = CommandRead.model_validate(command).model_dump(mode="json")
    await realtime_manager.broadcast_device_event(
        device_id,
        {"type": "command.created", "device_id": device_id, "command": command_message},
    )
    return command


@router.get("/{device_id}/commands/pending", response_model=list[CommandRead])
async def list_pending_commands(
    device_id: int,
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Fetch and consume all pending commands for a device.

    Intended to be polled by the physical hardware. On each call:
    - All ``pending`` commands are returned (oldest first).
    - Their status is immediately transitioned to ``delivered``.
    - ``device.last_seen_at`` is updated (acts as an implicit heartbeat).
    - A ``command.delivered`` WebSocket event is broadcast for each command.

    Commands are consumed — repeated calls will not return the same commands
    again unless new ones have been issued.

    Auth: X-Device-Key header required (hardware authentication).

    Raises:
        401: Missing or invalid X-Device-Key, or device is inactive.
        404: Device not found.
    """
    device = await _authenticate_device(db, device_id, x_device_key)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        sa.select(Command)
        .where(Command.device_id == device_id, Command.status == "pending")
        .order_by(Command.created_at.asc())
    )
    commands = result.scalars().all()
    for command in commands:
        command.status = "delivered"
        command.delivered_at = now

    device.last_seen_at = now
    await db.commit()

    for command in commands:
        command_message = CommandRead.model_validate(command).model_dump(mode="json")
        await realtime_manager.broadcast_device_event(
            device_id,
            {"type": "command.delivered", "device_id": device_id, "command": command_message},
        )
    return commands


@router.patch("/{device_id}/commands/{command_id}/ack", response_model=CommandRead)
async def acknowledge_command(
    device_id: int,
    command_id: int,
    payload: CommandAcknowledge,
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge that a device has executed a command.

    Called by the physical hardware after it has processed a delivered command.
    Transitions the command status to ``acknowledged``, records the execution
    result, updates ``device.last_seen_at``, and broadcasts a
    ``command.acknowledged`` WebSocket event.

    Auth: X-Device-Key header required (hardware authentication).

    Raises:
        401: Missing or invalid X-Device-Key, or device is inactive.
        404: Device or command not found.
    """
    device = await _authenticate_device(db, device_id, x_device_key)
    result = await db.execute(
        sa.select(Command).where(Command.id == command_id, Command.device_id == device_id)
    )
    command = result.scalar_one_or_none()
    if command is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    now = datetime.now(timezone.utc)
    command.status = "acknowledged"
    command.result = payload.result
    command.acknowledged_at = now
    device.last_seen_at = now
    await db.commit()
    await db.refresh(command)

    command_message = CommandRead.model_validate(command).model_dump(mode="json")
    await realtime_manager.broadcast_device_event(
        device_id,
        {"type": "command.acknowledged", "device_id": device_id, "command": command_message},
    )
    return command