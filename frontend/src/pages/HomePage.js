import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Row, Col, Card, Alert, Spinner,
  Badge, Form, ButtonGroup, Button
} from 'react-bootstrap';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

const DEVICE_ICONS = {
  fan: '🌀', light: '💡', camera: '📷', lock: '🔒',
  temp_sensor: '🌡️', humidity_sensor: '💧',
};

const DEVICE_UNITS = {
  temp_sensor: '°C', humidity_sensor: '%', fan: '',
};

const SENSOR_TYPES = ['temp_sensor', 'humidity_sensor'];

const SENSOR_COLORS = ['#0d6efd', '#198754', '#fd7e14', '#dc3545', '#6f42c1', '#0dcaf0'];

/* Format timestamp from API for X axis label */
const formatTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
};

/* Custom tooltip for the chart */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-white border rounded shadow-sm p-2" style={{ fontSize: '0.75rem' }}>
      <p className="text-muted mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="mb-0 fw-semibold" style={{ color: p.color }}>
          {p.name}: {p.value}{p.unit || ''}
        </p>
      ))}
    </div>
  );
};

/* ── Sensor Chart Card ── */
function SensorChart({ sensor, color }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const unit = DEVICE_UNITS[sensor.type] || '';

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get(`/devices/${sensor.id}/sensor-data`, { params: { limit: 20 } });
      // API returns newest-first, reverse for chronological display
      const points = [...res.data].reverse().map((item) => ({
        time: formatTime(item.created_at),
        value: parseFloat(item.value),
        raw: item.created_at,
      }));
      setData(points);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [sensor.id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  /* Listen to WS updates and append new point */
  useEffect(() => {
    const handler = (e) => {
      const payload = e.detail;
      if (
        payload.event === 'sensor_update' &&
        payload.hardware_id === sensor.hardware_id &&
        payload.data[sensor.pin] !== undefined
      ) {
        const newPoint = {
          time: formatTime(new Date().toISOString()),
          value: parseFloat(payload.data[sensor.pin]),
          raw: new Date().toISOString(),
        };
        setData((prev) => {
          const next = [...prev, newPoint];
          return next.length > 20 ? next.slice(next.length - 20) : next;
        });
      }
    };
    window.addEventListener('yolohome:ws', handler);
    return () => window.removeEventListener('yolohome:ws', handler);
  }, [sensor.hardware_id, sensor.pin]);

  const latestValue = data.length > 0 ? data[data.length - 1].value : sensor.value;
  const minVal = data.length > 0 ? Math.min(...data.map(d => d.value)) : null;
  const maxVal = data.length > 0 ? Math.max(...data.map(d => d.value)) : null;

  return (
    <Card className="shadow-sm border h-100">
      <Card.Header className="bg-white border-bottom d-flex justify-content-between align-items-center">
        <div className="d-flex align-items-center gap-2">
          <span>{DEVICE_ICONS[sensor.type] || '📊'}</span>
          <span className="fw-semibold small">{sensor.name}</span>
          <Badge bg="light" text="dark" className="border small">{sensor.room || 'No room'}</Badge>
        </div>
        <div className="d-flex align-items-center gap-2">
          <span className="fw-bold" style={{ color, fontSize: '1.1rem' }}>
            {latestValue != null ? `${latestValue}${unit}` : '—'}
          </span>
          <Badge bg={sensor.is_on ? 'success' : 'secondary'} className="small">
            {sensor.is_on ? 'ON' : 'OFF'}
          </Badge>
        </div>
      </Card.Header>

      <Card.Body className="p-3">
        {loading ? (
          <div className="d-flex align-items-center justify-content-center py-4 text-muted">
            <Spinner size="sm" animation="border" className="me-2" />
            <small>Loading history...</small>
          </div>
        ) : data.length === 0 ? (
          <div className="text-center text-muted py-4">
            <div className="fs-3 mb-1">📉</div>
            <small>No data yet</small>
          </div>
        ) : (
          <>
            {/* Stat row */}
            <Row className="g-2 mb-3">
              <Col xs={4} className="text-center">
                <p className="text-muted mb-0" style={{ fontSize: '0.65rem' }}>MIN</p>
                <p className="fw-bold mb-0 small text-primary">{minVal}{unit}</p>
              </Col>
              <Col xs={4} className="text-center border-start border-end">
                <p className="text-muted mb-0" style={{ fontSize: '0.65rem' }}>CURRENT</p>
                <p className="fw-bold mb-0 small" style={{ color }}>{latestValue}{unit}</p>
              </Col>
              <Col xs={4} className="text-center">
                <p className="text-muted mb-0" style={{ fontSize: '0.65rem' }}>MAX</p>
                <p className="fw-bold mb-0 small text-danger">{maxVal}{unit}</p>
              </Col>
            </Row>

            {/* Line chart */}
            <ResponsiveContainer width="100%" height={140}>
              <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 10, fill: '#adb5bd' }}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#adb5bd' }}
                  tickLine={false}
                  axisLine={false}
                  domain={['auto', 'auto']}
                />
                <Tooltip content={<CustomTooltip />} />
                {latestValue != null && (
                  <ReferenceLine
                    y={latestValue}
                    stroke={color}
                    strokeDasharray="4 4"
                    strokeOpacity={0.4}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="value"
                  name={sensor.name}
                  unit={unit}
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: color }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>

            <p className="text-muted mb-0 text-end" style={{ fontSize: '0.65rem' }}>
              Last {data.length} readings · live
            </p>
          </>
        )}
      </Card.Body>
    </Card>
  );
}

/* ── Main Page ── */
export default function HomePage() {
  const { user, isAdmin } = useAuth();

  const [devices, setDevices] = useState([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDevices = useCallback(async () => {
    try {
      setDevicesLoading(true);
      const res = await api.get('/devices/');
      setDevices(res.data);
    } catch { /* silent */ } finally { setDevicesLoading(false); }
  }, []);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  useEffect(() => {
    const handleWsMessage = (e) => {
      const payload = e.detail;
      if (payload.event === 'sensor_update') {
        setDevices((prev) => prev.map(d => {
          if (d.hardware_id === payload.hardware_id && payload.data[d.pin] !== undefined)
            return { ...d, value: payload.data[d.pin] };
          return d;
        }));
      } else if (payload.event === 'device_update') {
        setDevices((prev) => prev.map(d =>
          d.id === payload.device_id ? { ...d, is_on: payload.data.is_on, value: payload.data.value } : d
        ));
      }
    };
    window.addEventListener('yolohome:ws', handleWsMessage);
    return () => window.removeEventListener('yolohome:ws', handleWsMessage);
  }, []);

  const handleDeviceCommand = async (deviceId, isOn, value) => {
    setDevices((prev) => prev.map(d => d.id === deviceId ? { ...d, is_on: isOn, value } : d));
    try {
      await api.post(`/devices/${deviceId}/command`, { is_on: isOn, value });
    } catch (err) { console.error('Failed to send command', err); fetchDevices(); }
  };

  const renderDeviceValue = (d) => {
    const unit = DEVICE_UNITS[d.type] || '';
    if (d.type === 'lock') return d.is_on ? '🔓 Open' : '🔒 Locked';
    if (d.type === 'light') return d.is_on ? '💡 On' : 'Off';
    if (d.type === 'camera') return d.is_on ? '🟢 Active' : 'Off';
    if (d.type === 'fan') return d.is_on ? `Speed ${Math.round(d.value)}` : 'Off';
    return `${d.value}${unit}`;
  };

  const sensors = devices.filter(d => SENSOR_TYPES.includes(d.type));
  const nonSensors = devices.filter(d => !SENSOR_TYPES.includes(d.type));

  return (
    <Container className="py-4 bg-white min-vh-100">

      {/* ── Header ── */}
      <Row className="align-items-center mb-4 pb-3 border-bottom">
        <Col>
          <p className="text-muted small text-uppercase fw-semibold mb-1">YoloHome · Control Center</p>
          <h1 className="h3 fw-bold mb-0">
            Welcome back, <span className="text-primary">{user?.username}</span>
          </h1>
        </Col>
      </Row>

      {/* ── Error ── */}
      {error && (
        <Alert variant="danger" dismissible onClose={() => setError('')} className="mb-4">
          {error}
        </Alert>
      )}

      {devicesLoading ? (
        <div className="text-center py-5 text-muted">
          <Spinner animation="border" />
          <p className="small mt-2 mb-0">Loading devices...</p>
        </div>
      ) : (
        <>
          {/* ── Sensor Charts ── */}
          {sensors.length > 0 && (
            <>
              <div className="d-flex align-items-center justify-content-between mb-3">
                <h5 className="fw-semibold mb-0">📈 Sensor Readings</h5>
                <Badge bg="light" text="dark" className="border">
                  {sensors.length} sensor{sensors.length !== 1 ? 's' : ''} · live
                </Badge>
              </div>
              <Row className="g-3 mb-5">
                {sensors.map((sensor, idx) => (
                  <Col xs={12} md={6} key={sensor.id}>
                    <SensorChart
                      sensor={sensor}
                      color={SENSOR_COLORS[idx % SENSOR_COLORS.length]}
                    />
                  </Col>
                ))}
              </Row>
            </>
          )}

          {/* ── Device Monitor ── */}
          <div className="d-flex align-items-center justify-content-between mb-3">
            <h5 className="fw-semibold mb-0">📡 Device Monitor</h5>
            <Badge bg="light" text="dark" className="border">
              {nonSensors.length} device{nonSensors.length !== 1 ? 's' : ''}
            </Badge>
          </div>

          {nonSensors.length === 0 ? (
            <Card className="shadow-sm border-0 text-center py-5 text-muted">
              <Card.Body>
                <div className="fs-1 mb-2">📡</div>
                <p className="mb-0 small">
                  {isAdmin
                    ? 'No devices configured. Go to Devices page to add hardware.'
                    : 'No devices configured. Ask admin to set up devices.'}
                </p>
              </Card.Body>
            </Card>
          ) : (
            <Row className="g-3">
              {nonSensors.map((d) => (
                <Col xs={6} md={4} lg={3} key={d.id}>
                  <Card className="shadow-sm border h-100">
                    <Card.Body className="p-3">

                      <div className="d-flex justify-content-between align-items-start mb-2">
                        <span className="fs-4">{DEVICE_ICONS[d.type] || '📦'}</span>
                        <Badge bg={d.is_on ? 'success' : 'secondary'}>
                          {d.is_on ? 'ON' : 'OFF'}
                        </Badge>
                      </div>

                      <p className="fw-semibold small mb-0">{d.name}</p>
                      <p className="text-muted small mb-2">{d.room || 'No room'}</p>

                      {d.type === 'light' && (
                        <Form.Check
                          type="switch"
                          id={`sw-${d.id}`}
                          label={d.is_on ? 'On' : 'Off'}
                          checked={d.is_on}
                          onChange={e => handleDeviceCommand(d.id, e.target.checked, e.target.checked ? 1 : 0)}
                          className={d.is_on ? 'text-success' : 'text-muted'}
                        />
                      )}

                      {d.type === 'fan' && (
                        <>
                          <Form.Check
                            type="switch"
                            id={`sw-${d.id}`}
                            label={d.is_on ? 'On' : 'Off'}
                            checked={d.is_on}
                            onChange={e => {
                              const on = e.target.checked;
                              handleDeviceCommand(d.id, on, on ? (d.value > 0 ? d.value : 1) : 0);
                            }}
                            className={`mb-2 ${d.is_on ? 'text-success' : 'text-muted'}`}
                          />
                          {d.is_on && (
                            <ButtonGroup size="sm" className="w-100">
                              {[1, 2, 3].map(lvl => (
                                <Button
                                  key={lvl}
                                  variant={d.value === lvl ? 'primary' : 'outline-primary'}
                                  onClick={() => handleDeviceCommand(d.id, true, lvl)}
                                >
                                  {lvl}
                                </Button>
                              ))}
                            </ButtonGroup>
                          )}
                        </>
                      )}

                      {!['light', 'fan'].includes(d.type) && (
                        <p className={`fw-bold small mb-0 ${(d.is_on || d.value > 0) ? 'text-success' : 'text-muted'}`}>
                          {renderDeviceValue(d)}
                        </p>
                      )}

                    </Card.Body>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </>
      )}

    </Container>
  );
}