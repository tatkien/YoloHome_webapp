import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Row, Col, Card, Button, Form, Modal, Alert, Spinner,
} from 'react-bootstrap';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

const DEVICE_TYPES = [
  { value: 'light', label: '💡 Light', icon: '💡' },
  { value: 'fan', label: '🌀 Fan', icon: '🌀' },
  { value: 'camera', label: '📷 Camera', icon: '📷' },
  { value: 'lock', label: '🔒 Lock (Servo)', icon: '🔒' },
  { value: 'temp_sensor', label: '🌡️ Temp Sensor', icon: '🌡️' },
  { value: 'humidity_sensor', label: '💧 Humidity Sensor', icon: '💧' },
];

// Dedicated pin → type mapping
const DEDICATED_PINS = { temp: 'temp_sensor', humi: 'humidity_sensor', servo: 'lock' };

function deviceIcon(type) {
  const dt = DEVICE_TYPES.find((d) => d.value === type);
  return dt ? dt.icon : '📦';
}

function deviceUnit(type) {
  if (type === 'temp_sensor') return '°C';
  if (type === 'humidity_sensor') return '%';
  if (type === 'fan') return ' speed';
  return '';
}

export default function DevicesPage() {
  const { isAdmin } = useAuth();
  const [devices, setDevices] = useState([]);
  const [hardware, setHardware] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create modal state
  const [showCreate, setShowCreate] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [newDevice, setNewDevice] = useState({
    name: '', type: 'light', room: '', hardware_id: '', pin: '',
  });

  // Edit modal state
  const [showEdit, setShowEdit] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editDevice, setEditDevice] = useState({
    id: '', name: '', room: '',
  });

  // Delete confirm modal state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deviceToDelete, setDeviceToDelete] = useState({ id: '', name: '' });

  // Device logs state
  const [expandedLogs, setExpandedLogs] = useState({});
  const [deviceLogs, setDeviceLogs] = useState({});
  const [logsLoading, setLogsLoading] = useState({});

  const fetchDevices = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/devices/');
      setDevices(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load devices');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHardware = useCallback(async () => {
    try {
      const res = await api.get('/devices/hardware');
      setHardware(res.data);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchDevices();
    fetchHardware();
  }, [fetchDevices, fetchHardware]);

  // Get available pins for selected hardware
  const selectedHw = hardware.find((h) => h.id === newDevice.hardware_id);
  const allPins = selectedHw?.pins || [];
  const usedPins = (selectedHw?.devices || []).map((d) => d.pin);
  const availablePins = allPins.filter((p) => !usedPins.includes(p));

  // Auto-set device type when a dedicated pin is selected
  const handlePinChange = (pin) => {
    const update = { ...newDevice, pin };
    if (DEDICATED_PINS[pin]) {
      update.type = DEDICATED_PINS[pin];
    }
    setNewDevice(update);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    setCreateLoading(true);
    try {
      await api.post('/devices/', {
        name: newDevice.name,
        type: newDevice.type,
        room: newDevice.room || null,
        hardware_id: newDevice.hardware_id,
        pin: newDevice.pin,
      });
      setSuccess(`Device "${newDevice.name}" created`);
      setNewDevice({ name: '', type: 'light', room: '', hardware_id: '', pin: '' });
      setShowCreate(false);
      fetchDevices();
      fetchHardware();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create device');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleDevChange = (id, currentName, currentRoom) => {
    setError('');
    setEditDevice({
      id,
      name: currentName || '',
      room: currentRoom || '',
    });
    setShowEdit(true);
  };

  const handleUpdateDevice = async (e) => {
    e.preventDefault();
    setError('');
    setEditLoading(true);

    try {
      await api.patch(`/devices/${editDevice.id}`, {
        name: editDevice.name.trim(),
        room: editDevice.room.trim() || null,
      });

      setSuccess(`Device "${editDevice.name.trim()}" updated`);
      setShowEdit(false);
      setEditDevice({ id: '', name: '', room: '' });
      fetchDevices();
      fetchHardware();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update device');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = async (id, name) => {
    setError('');
    setDeleteLoading(true);
    try {
      await api.delete(`/devices/${id}`);
      setSuccess(`Device "${name}" deleted`);
      fetchDevices();
      fetchHardware();
      setTimeout(() => setSuccess(''), 3000);
      setShowDeleteConfirm(false);
      setDeviceToDelete({ id: '', name: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete device');
    } finally {
      setDeleteLoading(false);
    }
  };

  const askDeleteDevice = (id, name) => {
    setError('');
    setDeviceToDelete({ id, name });
    setShowDeleteConfirm(true);
  };

  const fetchLogs = async (deviceId) => {
    if (expandedLogs[deviceId]) {
      setExpandedLogs((prev) => ({ ...prev, [deviceId]: false }));
      return;
    }
    setExpandedLogs((prev) => ({ ...prev, [deviceId]: true }));
    setLogsLoading((prev) => ({ ...prev, [deviceId]: true }));
    try {
      const res = await api.get(`/devices/${deviceId}/history?limit=10`);
      setDeviceLogs((prev) => ({ ...prev, [deviceId]: res.data }));
    } catch {
      setDeviceLogs((prev) => ({ ...prev, [deviceId]: [] }));
    } finally {
      setLogsLoading((prev) => ({ ...prev, [deviceId]: false }));
    }
  };

  const closeCreateModal = () => {
    setShowCreate(false);
    setNewDevice({ name: '', type: 'light', room: '', hardware_id: '', pin: '' });
  };

  const closeEditModal = () => {
    setShowEdit(false);
    setEditDevice({ id: '', name: '', room: '' });
  };

  const closeDeleteModal = () => {
    if (deleteLoading) return;
    setShowDeleteConfirm(false);
    setDeviceToDelete({ id: '', name: '' });
  };

  const renderDeviceValue = (d) => {
    if (d.type === 'lock') return d.is_on ? '🔓 Open' : '🔒 Locked';
    if (d.type === 'light') return d.is_on ? '💡 On' : '⚫ Off';
    if (d.type === 'camera') return d.is_on ? '🟢 Active' : '⚫ Off';
    if (d.type === 'fan') return d.is_on ? `Speed ${Math.round(d.value)}` : 'Off';
    return `${d.value}${deviceUnit(d.type)}`;
  };

  return (
    <Container className="py-4 fade-in">
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1>📡 Devices</h1>
          <p>Manage your smart home devices</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setShowCreate(true)}>+ Add Device</Button>
        )}
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {loading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : devices.length === 0 ? (
        <div className="text-center py-5" style={{ color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📡</div>
          <p>{isAdmin ? 'No devices yet. Click "Add Device" to get started.' : 'No devices configured. Ask admin to set up devices.'}</p>
        </div>
      ) : (
        <Row className="g-4">
          {devices.map((d) => (
            <Col md={6} lg={4} key={d.id}>
              <Card className="h-100">
                <Card.Body className="p-4">
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <div style={{ fontSize: '2rem' }}>{deviceIcon(d.type)}</div>
                    <span className="badge-device">{d.type}</span>
                  </div>
                  <Card.Title>{d.name}</Card.Title>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                    <div>Room: {d.room || '—'}</div>
                    <div>Pin: <code style={{ color: 'var(--accent-blue)' }}>{d.pin}</code></div>
                    <div>Hardware: <code style={{ color: 'var(--accent-purple)' }}>{d.hardware_id}</code></div>
                    <div className="d-flex align-items-center gap-1 mt-1">
                      Value: <strong style={{ color: d.is_on ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                        {renderDeviceValue(d)}
                      </strong>
                    </div>
                    {d.last_seen_at && (
                      <div>Last seen: {new Date(d.last_seen_at).toLocaleString()}</div>
                    )}
                  </div>

                  {/* Device Logs accordion */}
                  <Button variant="outline-dark" size="sm" className="w-100 mb-2"
                    onClick={() => fetchLogs(d.id)}>
                    {expandedLogs[d.id] ? '▲ Hide Logs' : '▼ Show Logs'}
                  </Button>
                  {expandedLogs[d.id] && (
                    <div className="device-logs-panel">
                      {logsLoading[d.id] ? (
                        <div className="text-center py-2"><Spinner size="sm" animation="border" /></div>
                      ) : (deviceLogs[d.id] || []).length === 0 ? (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '0.5rem' }}>
                          No logs yet
                        </div>
                      ) : (
                        <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                          {(deviceLogs[d.id] || []).map((log) => (
                            <div key={log.id} className="device-log-entry">
                              <div style={{ fontSize: '0.78rem' }}>{log.action}</div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                {log.source} • {new Date(log.created_at).toLocaleString()}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </Card.Body>
                {isAdmin && (
                  <Card.Footer style={{ background: 'transparent', borderTop: '1px solid var(--border-color)', padding: '0.75rem 1.25rem' }}>
                    <div className="d-flex justify-content-between align-items-center">
                      <small style={{ color: 'var(--text-muted)' }}>
                        {d.created_at ? new Date(d.created_at).toLocaleDateString() : ''}
                      </small>
                      <div className="d-flex align-items-center" style={{ gap: '0.4rem' }}>
                        <Button
                          variant="light"
                          size="sm"
                          style={{ minWidth: '88px' }}
                          className='border-dark'
                          onClick={() => handleDevChange(d.id, d.name, d.room)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => askDeleteDevice(d.id, d.name)}
                        >
                          Delete
                        </Button>
                      </div>
                      
                    </div>
                  </Card.Footer>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Edit Device Modal */}
      <Modal show={showEdit} onHide={closeEditModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Edit Device</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleUpdateDevice}>
          <Modal.Body>
            <Form.Group className="mb-3">
              <Form.Label>Device Name</Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. Living Room Light"
                value={editDevice.name}
                onChange={(e) => setEditDevice({ ...editDevice, name: e.target.value })}
                required
                autoFocus
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Room <small style={{ color: 'var(--text-muted)' }}>(optional)</small></Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. Living Room"
                value={editDevice.room}
                onChange={(e) => setEditDevice({ ...editDevice, room: e.target.value })}
              />
            </Form.Group>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="outline-dark" onClick={closeEditModal}>Cancel</Button>
            <Button type="submit" disabled={editLoading}>
              {editLoading ? <Spinner size="sm" animation="border" /> : 'Save Changes'}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>

      {/* Delete Confirm Modal */}
      <Modal show={showDeleteConfirm} onHide={closeDeleteModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Delete Device</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="warning" className="mb-0">
            Are you sure you want to delete <strong>{deviceToDelete.name || 'this device'}</strong>? This action cannot be undone.
          </Alert>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-dark" onClick={closeDeleteModal} disabled={deleteLoading}>Cancel</Button>
          <Button
            variant="danger"
            onClick={() => handleDelete(deviceToDelete.id, deviceToDelete.name)}
            disabled={deleteLoading}
          >
            {deleteLoading ? <Spinner size="sm" animation="border" /> : 'Delete'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Create Device Modal */}
      <Modal show={showCreate} onHide={closeCreateModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Add New Device</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleCreate}>
          <Modal.Body>
            <Form.Group className="mb-3">
              <Form.Label>Hardware Board</Form.Label>
              <Form.Select
                value={newDevice.hardware_id}
                onChange={(e) => setNewDevice({ ...newDevice, hardware_id: e.target.value, pin: '' })}
                required
              >
                <option value="">Select hardware...</option>
                {hardware.map((h) => (
                  <option key={h.id} value={h.id}>{h.name} ({h.id})</option>
                ))}
              </Form.Select>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Pin</Form.Label>
              <Form.Select
                value={newDevice.pin}
                onChange={(e) => handlePinChange(e.target.value)}
                required
                disabled={!newDevice.hardware_id}
              >
                <option value="">Select pin...</option>
                {availablePins.map((p) => (
                  <option key={p} value={p}>
                    {p} {DEDICATED_PINS[p] ? `(→ ${DEDICATED_PINS[p]})` : ''}
                  </option>
                ))}
              </Form.Select>
              {newDevice.pin && DEDICATED_PINS[newDevice.pin] && (
                <Form.Text style={{ color: 'var(--accent-yellow)' }}>
                  This pin is dedicated to {DEDICATED_PINS[newDevice.pin]} — type auto-set.
                </Form.Text>
              )}
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Device Type</Form.Label>
              <Form.Select
                value={newDevice.type}
                onChange={(e) => setNewDevice({ ...newDevice, type: e.target.value })}
                disabled={!!DEDICATED_PINS[newDevice.pin]}
              >
                {DEVICE_TYPES.map((dt) => (
                  <option key={dt.value} value={dt.value}>{dt.label}</option>
                ))}
              </Form.Select>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Device Name</Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. Living Room Light"
                value={newDevice.name}
                onChange={(e) => setNewDevice({ ...newDevice, name: e.target.value })}
                required
                autoFocus
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Room <small style={{ color: 'var(--text-muted)' }}>(optional)</small></Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. Living Room"
                value={newDevice.room}
                onChange={(e) => setNewDevice({ ...newDevice, room: e.target.value })}
              />
            </Form.Group>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="outline-dark" onClick={closeCreateModal}>Cancel</Button>
            <Button type="submit" disabled={createLoading}>
              {createLoading ? <Spinner size="sm" animation="border" /> : 'Create Device'}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </Container>
  );
}
