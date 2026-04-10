import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Row, Col, Card, Button, Form, Modal, Alert, Spinner, Badge,
} from 'react-bootstrap';
import api from '../services/api';

export default function DeviceSchedulesPage() {
  const [schedules, setSchedules] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  
  const [newSchedule, setNewSchedule] = useState({ 
    device_id: '', 
    action: 'turn_on', 
    time_of_day: '08:00' 
  });

  const fetchSchedules = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/schedules/');
      setSchedules(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load schedules');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const res = await api.get('/devices/');
      setDevices(res.data);
      if (res.data.length > 0) {
        setNewSchedule(prev => ({ ...prev, device_id: res.data[0].id }));
      }
    } catch (err) {
      console.error("Failed to fetch devices for select box", err);
    }
  }, []);

  useEffect(() => { 
    fetchSchedules(); 
    fetchDevices();
  }, [fetchSchedules, fetchDevices]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    setCreateLoading(true);
    try {
      const formattedTime = newSchedule.time_of_day.length === 5 
        ? `${newSchedule.time_of_day}:00` 
        : newSchedule.time_of_day;

      await api.post('/schedules/', {
        device_id: newSchedule.device_id,
        action: newSchedule.action,
        time_of_day: formattedTime,
      });
      setSuccess('Daily schedule created successfully!');
      closeCreateModal();
      fetchSchedules();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create schedule');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm(`Are you sure you want to delete this schedule?`)) return;
    setError('');
    try {
      await api.delete(`/schedules/${id}`);
      setSuccess(`Schedule deleted`);
      fetchSchedules();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete schedule');
    }
  };

  const closeCreateModal = () => {
    setShowCreate(false);
    if (devices.length > 0) {
      setNewSchedule({ device_id: devices[0].id, action: 'turn_on', time_of_day: '08:00' });
    }
  };

  const getDeviceName = (deviceId) => {
    const device = devices.find(d => d.id === deviceId);
    return device ? device.name : `Device #${deviceId}`;
  };

  return (
    <Container className="py-4 fade-in">
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1>⏱️ Schedules</h1>
          <p>Manage daily recurring schedules for devices</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ Add Schedule</Button>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {loading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : schedules.length === 0 ? (
        <div className="text-center py-5" style={{ color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⏱️</div>
          <p>No schedules yet. Click "Add Schedule" to get started.</p>
        </div>
      ) : (
        <Row className="g-4">
          {schedules.map((s) => (
            <Col md={6} lg={4} key={s.id}>
              <Card className="h-100">
                <Card.Body className="p-4">
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <div style={{ fontSize: '1.5rem' }}>
                      {s.action === 'turn_on' ? '🟢' : '🔴'}
                    </div>
                    <Badge bg={s.is_active ? "primary" : "secondary"}>
                      {s.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <Card.Title>{getDeviceName(s.device_id)}</Card.Title>
                  <Card.Text style={{ fontSize: '0.9rem' }}>
                    Action: <strong>{s.action === 'turn_on' ? 'Turn On' : 'Turn Off'}</strong>
                  </Card.Text>
                  <div style={{ fontSize: '0.9rem', color: 'var(--accent-blue)', fontWeight: 'bold' }}>
                    Repeats: Daily at {s.time_of_day}
                  </div>
                  {s.last_triggered_on && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                      Last triggered: {s.last_triggered_on}
                    </div>
                  )}
                </Card.Body>
                <Card.Footer style={{ background: 'transparent', borderTop: '1px solid var(--border-color)', padding: '0.75rem 1.25rem' }}>
                  <div className="d-flex justify-content-end align-items-center">
                    <Button variant="danger" size="sm" onClick={() => handleDelete(s.id)}>
                      Delete
                    </Button>
                  </div>
                </Card.Footer>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Create Schedule Modal */}
      <Modal show={showCreate} onHide={closeCreateModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Add New Daily Schedule</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleCreate}>
          <Modal.Body>
            <Form.Group className="mb-3">
              <Form.Label>Select Device</Form.Label>
              <Form.Select
                value={newSchedule.device_id}
                onChange={(e) => setNewSchedule({ ...newSchedule, device_id: e.target.value })}
                required
              >
                {devices.length === 0 && <option value="">No devices...</option>}
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>{d.name} ({d.device_type})</option>
                ))}
              </Form.Select>
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label>Action</Form.Label>
              <Form.Select
                value={newSchedule.action}
                onChange={(e) => setNewSchedule({ ...newSchedule, action: e.target.value })}
              >
                <option value="turn_on">Turn On</option>
                <option value="turn_off">Turn Off</option>
              </Form.Select>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Time (Daily)</Form.Label>
              <Form.Control
                type="time"
                value={newSchedule.time_of_day}
                onChange={(e) => setNewSchedule({ ...newSchedule, time_of_day: e.target.value })}
                required
              />
            </Form.Group>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="outline-light" onClick={closeCreateModal}>Cancel</Button>
            <Button type="submit" disabled={createLoading || devices.length === 0}>
              {createLoading ? <Spinner size="sm" animation="border" /> : 'Save Schedule'}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </Container>
  );
}