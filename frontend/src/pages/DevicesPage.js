import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Row, Col, Card, Button, Form, Modal, Alert, Spinner, Badge,
} from 'react-bootstrap';
import api from '../services/api';

const DEVICE_TYPES = [
  { value: 'light', label: '💡 Light', icon: '💡' },
  { value: 'fan', label: '🌀 Fan', icon: '🌀' },
  { value: 'camera', label: '📷 Camera', icon: '📷' },
  { value: 'temp_sensor', label: '🌡️ Temp Sensor', icon: '🌡️' },
  { value: 'humidity_sensor', label: '💧 Humidity Sensor', icon: '💧' },
];

function deviceIcon(type) {
  const dt = DEVICE_TYPES.find((d) => d.value === type);
  return dt ? dt.icon : '📦';
}

export default function DevicesPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [newDevice, setNewDevice] = useState({ name: '', device_type: 'light', description: '' });
  const [createdKey, setCreatedKey] = useState(null);

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

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    setCreateLoading(true);
    try {
      const res = await api.post('/devices/', {
        name: newDevice.name,
        device_type: newDevice.device_type,
        description: newDevice.description || null,
      });
      setCreatedKey(res.data.device_key);
      setSuccess(`Device "${newDevice.name}" created`);
      setNewDevice({ name: '', device_type: 'light', description: '' });
      fetchDevices();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create device');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete device "${name}" and all its data?`)) return;
    setError('');
    try {
      await api.delete(`/devices/${id}`);
      setSuccess(`Device "${name}" deleted`);
      fetchDevices();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete device');
    }
  };

  const closeCreateModal = () => {
    setShowCreate(false);
    setCreatedKey(null);
    setNewDevice({ name: '', device_type: 'light', description: '' });
  };

  return (
    <Container className="py-4 fade-in">
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1>📡 Devices</h1>
          <p>Manage your smart home devices</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ Add Device</Button>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {loading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : devices.length === 0 ? (
        <div className="text-center py-5" style={{ color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📡</div>
          <p>No devices yet. Click "Add Device" to get started.</p>
        </div>
      ) : (
        <Row className="g-4">
          {devices.map((d) => (
            <Col md={6} lg={4} key={d.id}>
              <Card className="h-100">
                <Card.Body className="p-4">
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <div style={{ fontSize: '2rem' }}>{deviceIcon(d.device_type)}</div>
                    <span className="badge-device">{d.device_type}</span>
                  </div>
                  <Card.Title>{d.name}</Card.Title>
                  <Card.Text style={{ fontSize: '0.85rem' }}>{d.description || 'No description'}</Card.Text>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                    <div>Slug: <code style={{ color: 'var(--accent-blue)' }}>{d.slug}</code></div>
                    <div>Owner: #{d.owner_id}</div>
                    <div className="d-flex align-items-center gap-1 mt-1">
                      Status: {d.is_active
                        ? <Badge bg="success" style={{ fontSize: '0.7rem' }}>Active</Badge>
                        : <Badge bg="secondary" style={{ fontSize: '0.7rem' }}>Inactive</Badge>
                      }
                    </div>
                    {d.last_seen_at && (
                      <div>Last seen: {new Date(d.last_seen_at).toLocaleString()}</div>
                    )}
                  </div>
                </Card.Body>
                <Card.Footer style={{ background: 'transparent', borderTop: '1px solid var(--border-color)', padding: '0.75rem 1.25rem' }}>
                  <div className="d-flex justify-content-between align-items-center">
                    <small style={{ color: 'var(--text-muted)' }}>
                      {new Date(d.created_at).toLocaleDateString()}
                    </small>
                    <Button variant="danger" size="sm" onClick={() => handleDelete(d.id, d.name)}>
                      Delete
                    </Button>
                  </div>
                </Card.Footer>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Create Device Modal */}
      <Modal show={showCreate} onHide={closeCreateModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Add New Device</Modal.Title>
        </Modal.Header>
        {createdKey ? (
          <>
            <Modal.Body>
              <Alert variant="warning" className="mb-3">
                ⚠️ <strong>Save this device key now!</strong> It will only be shown once.
              </Alert>
              <div style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--accent-yellow)',
                borderRadius: 'var(--radius-sm)',
                padding: '1rem',
                fontFamily: 'monospace',
                fontSize: '0.9rem',
                wordBreak: 'break-all',
                color: 'var(--accent-yellow)',
              }}>
                {createdKey}
              </div>
            </Modal.Body>
            <Modal.Footer>
              <Button onClick={closeCreateModal}>Done</Button>
            </Modal.Footer>
          </>
        ) : (
          <Form onSubmit={handleCreate}>
            <Modal.Body>
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
                <Form.Label>Device Type</Form.Label>
                <Form.Select
                  value={newDevice.device_type}
                  onChange={(e) => setNewDevice({ ...newDevice, device_type: e.target.value })}
                >
                  {DEVICE_TYPES.map((dt) => (
                    <option key={dt.value} value={dt.value}>{dt.label}</option>
                  ))}
                </Form.Select>
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Description <small style={{ color: 'var(--text-muted)' }}>(optional)</small></Form.Label>
                <Form.Control
                  as="textarea"
                  rows={2}
                  placeholder="Brief description"
                  value={newDevice.description}
                  onChange={(e) => setNewDevice({ ...newDevice, description: e.target.value })}
                />
              </Form.Group>
            </Modal.Body>
            <Modal.Footer>
              <Button variant="outline-light" onClick={closeCreateModal}>Cancel</Button>
              <Button type="submit" disabled={createLoading}>
                {createLoading ? <Spinner size="sm" animation="border" /> : 'Create Device'}
              </Button>
            </Modal.Footer>
          </Form>
        )}
      </Modal>
    </Container>
  );
}
