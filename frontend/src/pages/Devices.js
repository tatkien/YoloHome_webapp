import React, { useState, useEffect } from 'react';
import DeviceCard from '../components/DeviceCard';
import { deviceService } from '../services/api';

function Devices() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const data = await deviceService.getDevices();
        setDevices(data);
      } catch (err) {
        setError('Could not connect to the backend. Please ensure the API server is running.');
      } finally {
        setLoading(false);
      }
    };

    fetchDevices();
  }, []);

  const handleToggle = async (deviceId) => {
    try {
      await deviceService.toggleDevice(deviceId);
      setDevices((prev) =>
        prev.map((d) =>
          d.id === deviceId ? { ...d, active: !d.active } : d
        )
      );
    } catch (err) {
      console.error('Failed to toggle device', err);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2>Devices</h2>
        <button className="btn btn-primary">+ Add Device</button>
      </div>

      {devices.length === 0 ? (
        <div className="text-center py-5 text-muted">
          <p className="fs-5">No devices found.</p>
          <p>Connect your first device to get started.</p>
        </div>
      ) : (
        <div className="row g-4">
          {devices.map((device) => (
            <div key={device.id} className="col-sm-6 col-lg-4">
              <DeviceCard device={device} onToggle={handleToggle} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Devices;
