import React from 'react';
import { Link } from 'react-router-dom';

function Home() {
  return (
    <div>
      <div className="py-5 text-center">
        <h1 className="display-4 fw-bold">Welcome to YoloHome</h1>
        <p className="lead text-muted">
          Smart home management powered by modern web technology.
        </p>
        <div className="d-grid gap-2 d-sm-flex justify-content-sm-center mt-4">
          <Link to="/dashboard" className="btn btn-primary btn-lg px-4 gap-3">
            Go to Dashboard
          </Link>
          <Link to="/devices" className="btn btn-outline-secondary btn-lg px-4">
            Manage Devices
          </Link>
        </div>
      </div>

      <div className="row g-4 mt-2">
        <div className="col-md-4">
          <div className="card text-center h-100 border-0 shadow-sm">
            <div className="card-body p-4">
              <div className="fs-1 mb-3">📊</div>
              <h5 className="card-title">Real-time Dashboard</h5>
              <p className="card-text text-muted">
                Monitor all your smart home devices and sensors in real time.
              </p>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card text-center h-100 border-0 shadow-sm">
            <div className="card-body p-4">
              <div className="fs-1 mb-3">🔌</div>
              <h5 className="card-title">Device Control</h5>
              <p className="card-text text-muted">
                Control lights, fans, and other IoT devices from one place.
              </p>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card text-center h-100 border-0 shadow-sm">
            <div className="card-body p-4">
              <div className="fs-1 mb-3">🔔</div>
              <h5 className="card-title">Alerts & Notifications</h5>
              <p className="card-text text-muted">
                Stay informed with instant alerts and event notifications.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;
