from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceStatsResponse, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/stats", response_model=DeviceStatsResponse)
def get_device_stats(db: Session = Depends(get_db)):
    total = db.query(Device).count()
    active = db.query(Device).filter(Device.active == True).count()  # noqa: E712
    return DeviceStatsResponse(
        total_devices=total,
        active_devices=active,
        temperature="--",
        humidity="--",
    )


@router.get("/", response_model=List[DeviceResponse])
def list_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Device).offset(skip).limit(limit).all()


@router.post("/", response_model=DeviceResponse, status_code=201)
def create_device(device_in: DeviceCreate, db: Session = Depends(get_db)):
    device = Device(**device_in.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: int, device_in: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    for key, value in device_in.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return device


@router.patch("/{device_id}/toggle", response_model=DeviceResponse)
def toggle_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.active = not device.active
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()
