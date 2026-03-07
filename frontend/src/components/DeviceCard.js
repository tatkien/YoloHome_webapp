import React from 'react';

function DeviceCard({ device, onToggle }) {
  return (
    <div className="card h-100 shadow-sm">
      <div className="card-body">
        <h5 className="card-title">{device.name}</h5>
        <p className="card-text text-muted">{device.type}</p>
        <div className="d-flex align-items-center justify-content-between">
          <span
            className={`badge ${device.status === 'online' ? 'bg-success' : 'bg-secondary'}`}
          >
            {device.status}
          </span>
          <div className="form-check form-switch">
            <input
              className="form-check-input"
              type="checkbox"
              role="switch"
              id={`device-${device.id}`}
              checked={device.active}
              onChange={() => onToggle && onToggle(device.id)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default DeviceCard;
