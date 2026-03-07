import React, { useState, useEffect } from 'react';
import { deviceService } from '../services/api';

function Dashboard() {
  const [stats, setStats] = useState({
    totalDevices: 0,
    activeDevices: 0,
    temperature: '--',
    humidity: '--',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await deviceService.getStats();
        setStats(data);
      } catch (err) {
        // Use placeholder values if backend not connected
        setStats({
          totalDevices: 0,
          activeDevices: 0,
          temperature: '--',
          humidity: '--',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="mb-4">Dashboard</h2>
      <div className="row g-4">
        <div className="col-sm-6 col-lg-3">
          <div className="card text-white bg-primary h-100 shadow-sm">
            <div className="card-body">
              <h6 className="card-title">Total Devices</h6>
              <p className="card-text display-6">{stats.totalDevices}</p>
            </div>
          </div>
        </div>
        <div className="col-sm-6 col-lg-3">
          <div className="card text-white bg-success h-100 shadow-sm">
            <div className="card-body">
              <h6 className="card-title">Active Devices</h6>
              <p className="card-text display-6">{stats.activeDevices}</p>
            </div>
          </div>
        </div>
        <div className="col-sm-6 col-lg-3">
          <div className="card text-white bg-warning h-100 shadow-sm">
            <div className="card-body">
              <h6 className="card-title">Temperature</h6>
              <p className="card-text display-6">{stats.temperature}°C</p>
            </div>
          </div>
        </div>
        <div className="col-sm-6 col-lg-3">
          <div className="card text-white bg-info h-100 shadow-sm">
            <div className="card-body">
              <h6 className="card-title">Humidity</h6>
              <p className="card-text display-6">{stats.humidity}%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
