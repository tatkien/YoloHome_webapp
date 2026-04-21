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
    action: 'on', 
    time_of_day: '08:00',
    is_active: true 
  });

  const fetchAllData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      
      const devRes = await api.get('/devices/');
      const fetchedDevices = devRes.data;
      setDevices(fetchedDevices);

      let allSchedules = [];
      for (const device of fetchedDevices) {
        try {
          const schRes = await api.get(`/devices/${device.id}/schedules`);
          allSchedules = [...allSchedules, ...schRes.data];
        } catch (innerErr) {
          console.warn(`Ignored schedule fetch for ${device.id}`, innerErr);
        }
      }
      
      allSchedules.sort((a, b) => a.time_of_day.localeCompare(b.time_of_day));
      setSchedules(allSchedules);

      if (fetchedDevices.length > 0 && !newSchedule.device_id) {
        setNewSchedule(prev => ({ ...prev, device_id: fetchedDevices[0].id }));
      }

    } catch (err) {
      console.error("Fetch Error:", err);
      setError('Failed to load data.');
    } finally {
      setLoading(false);
    }
  }, [newSchedule.device_id]);

  useEffect(() => { 
    fetchAllData(); 
  }, [fetchAllData]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newSchedule.device_id) {
      setError('Please select a device first.');
      return;
    }
    
    setError('');

    const formattedTime = newSchedule.time_of_day.length === 5 
      ? `${newSchedule.time_of_day}:00` 
      : newSchedule.time_of_day;

    const isConflict = schedules.some(
      (s) => s.device_id === newSchedule.device_id && s.time_of_day === formattedTime
    );

    if (isConflict) {
      setError(`This device already has a schedule at ${formattedTime}.`);
      setShowCreate(false); 
      return;
    }

    setCreateLoading(true);
    try {
      await api.post(`/devices/${newSchedule.device_id}/schedules`, {
        action: newSchedule.action,
        time_of_day: formattedTime,
        is_active: newSchedule.is_active
      });
      
      setSuccess('Schedule created successfully!');
      fetchAllData(); 
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error creating schedule.');
    } finally {
      setShowCreate(false); 
      setCreateLoading(false);
    }
  };   

  const handleDelete = async (scheduleId) => {
    if (!window.confirm(`Are you sure you want to delete this schedule?`)) return;
    try {
      await api.delete(`/devices/schedules/${scheduleId}`);
      setSuccess(`Schedule deleted successfully`);
      fetchAllData();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to delete schedule.');
    }
  };

  const getDeviceName = (deviceId) => {
    const device = devices.find(d => d.id === deviceId);
    return device ? device.name : `Device #${deviceId}`;
  };

  const getDeviceType = (deviceId) => {
    const device = devices.find(d => d.id === deviceId);
    return device && device.device_type ? device.device_type : 'unknown';
  };

  return (
    <Container className="py-4">
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div>
          <h1>⏱️ Schedules</h1>
          <p className="text-muted">Manage daily schedules for your devices</p>
        </div>
        <Button onClick={() => setShowCreate(true)} disabled={loading}>
          + Add Schedule
        </Button>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {loading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : schedules.length === 0 ? (
        <div className="text-center py-5 text-muted">
          <h3>⏱️</h3>
          <p>No schedules found. Click "Add Schedule" to create one.</p>
        </div>
      ) : (
        <Row>
          {schedules.map((s) => (
            <Col md={6} lg={4} key={s.id} className="mb-4">
              <Card className="h-100 shadow-sm">
                <Card.Body>
                  <div className="d-flex justify-content-between mb-2">
                    <Badge bg="light" text="dark" className="border fw-normal">
                      {getDeviceType(s.device_id)}
                    </Badge>
                    <span style={{ fontSize: '1.2rem' }}>{s.action === 'on' ? '🟢' : '🔴'}</span>
                  </div>
                  <Card.Title>{getDeviceName(s.device_id)}</Card.Title>
                  <Card.Text>
                    Will <strong>{s.action.toUpperCase()}</strong> every day at <strong>{s.time_of_day}</strong>
                  </Card.Text>
                </Card.Body>
                <Card.Footer className="bg-white border-top-0 d-flex justify-content-end">
                  <Button variant="danger" size="sm" onClick={() => handleDelete(s.id)}>
                    Delete
                  </Button>
                </Card.Footer>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal show={showCreate} onHide={() => setShowCreate(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Create New Schedule</Modal.Title>
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
                {devices.length === 0 ? (
                  <option value="">-- No Devices Found --</option>
                ) : (
                  devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.device_type === 'light' ? '💡 ' : '🔌 '} 
                      {d.name} ({d.id})
                    </option>
                  ))
                )}
              </Form.Select>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Action</Form.Label>
              <Form.Select 
                value={newSchedule.action} 
                onChange={(e) => setNewSchedule({ ...newSchedule, action: e.target.value })}
              >
                <option value="on">Turn On</option>
                <option value="off">Turn Off</option>
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
            <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={createLoading || devices.length === 0}>
              {createLoading ? <Spinner size="sm" animation="border" /> : 'Save Schedule'}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </Container>
  );
}