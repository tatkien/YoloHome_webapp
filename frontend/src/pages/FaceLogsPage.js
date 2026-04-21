import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Container, Table, Form, Alert, Spinner, Row, Col, Button, Modal, Card, Badge
} from 'react-bootstrap';
import api from '../services/api';

const DEVICE_TYPE_LABELS = {
  camera: 'Camera',
  temp_sensor: 'Temperature',
  humidity_sensor: 'Humidity',
  light: 'Light',
  fan: 'Fan',
  lock: 'Lock',
};

const getFriendlyDeviceName = (device) => {
  if (!device) return 'Device';

  if (device.type && DEVICE_TYPE_LABELS[device.type]) {
    return DEVICE_TYPE_LABELS[device.type];
  }

  const raw = `${device.name || ''}`.toLowerCase();
  if (raw.includes('camera')) return 'Camera';
  if (raw.includes('temp')) return 'Temperature';
  if (raw.includes('humi')) return 'Humidity';
  if (raw.includes('light')) return 'Light';
  if (raw.includes('fan')) return 'Fan';
  if (raw.includes('lock')) return 'Lock';

  return device.name || 'Device';
};

export default function FaceLogsPage() {
  const [logs, setLogs] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterDeviceId, setFilterDeviceId] = useState('');
  const [limit, setLimit] = useState(100);
  const [previewLogId, setPreviewLogId] = useState(null);
  const [previewImageUrl, setPreviewImageUrl] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewImageUrlRef = useRef('');

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const params = { limit };
      if (filterDeviceId) params.device_id = filterDeviceId;
      const res = await api.get('/face/logs', { params });
      setLogs(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  }, [filterDeviceId, limit]);

  const fetchDevices = useCallback(async () => {
    try {
      setDevicesLoading(true);
      const res = await api.get('/devices/get-camera-devices/');
      setDevices(res.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load devices');
    } finally {
      setDevicesLoading(false);
    }
  }, []);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const revokePreviewUrl = useCallback(() => {
    if (previewImageUrlRef.current) {
      URL.revokeObjectURL(previewImageUrlRef.current);
      previewImageUrlRef.current = '';
    }
  }, []);

  useEffect(() => () => {
    revokePreviewUrl();
  }, [revokePreviewUrl]);

  const handleShowImage = async (log) => {
    setError('');
    setPreviewLoading(true);
    setPreviewLogId(log.id);
    revokePreviewUrl();
    setPreviewImageUrl('');

    try {
      const endpoint = `/face/logs/${log.id}/image`;
      const res = await api.get(endpoint, { responseType: 'blob' });
      const objectUrl = URL.createObjectURL(res.data);
      previewImageUrlRef.current = objectUrl;
      setPreviewImageUrl(objectUrl);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load image');
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewLogId(null);
    setPreviewImageUrl('');
    setPreviewLoading(false);
    revokePreviewUrl();
  };

  // Helper for status badges
  const getStatusBadge = (status = '') => {
    const s = status.toLowerCase();
    if (s === 'recognized') return <Badge bg="success">Recognized</Badge>;
    if (s.includes('spoof')) return <Badge bg="danger">Spoof</Badge>;
    return <Badge bg="warning" text="dark">Unknown</Badge>;
  };

  // Stats calculation
  const recognized = logs.filter((l) => l.status === 'recognized').length;
  const spoof = logs.filter((l) => (l.status || '').toLowerCase().includes('spoof')).length;
  const unknown = logs.filter((l) => l.status === 'unknown').length;

  return (
    <Container className="py-4">
      {/* Header */}
      <div className="mb-4">
        <h1 className="h3 mb-1">Recognition Logs</h1>
        <p className="text-muted">View face recognition attempt history</p>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}

      {/* Stats Cards */}
      <Row className="g-3 mb-4">
        {[
          { label: 'Total Logs', value: logs.length, color: 'dark' },
          { label: 'Recognized', value: recognized, color: 'success' },
          { label: 'Spoof', value: spoof, color: 'danger' },
          { label: 'Unknown', value: unknown, color: 'warning' },
        ].map((stat, idx) => (
          <Col md={3} key={idx}>
            <Card className="text-center border-0 shadow-sm">
              <Card.Body>
                <div className={`h2 fw-bold text-${stat.color}`}>{stat.value}</div>
                <div className="small text-muted text-uppercase fw-semibold">{stat.label}</div>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Filters Card */}
      <Card className="border-0 shadow-sm mb-4">
        <Card.Body>
          <Form>
            <Row className="align-items-end g-3">
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Device</Form.Label>
                  <Form.Select
                    value={filterDeviceId}
                    onChange={(e) => setFilterDeviceId(e.target.value)}
                    disabled={devicesLoading}
                  >
                    <option value="">All devices</option>
                    {devices.map((d) => (
                      <option key={d.id} value={d.id}>
                        {getFriendlyDeviceName(d)}
                      </option>
                    ))}
                  </Form.Select>
                </Form.Group>
              </Col>
              <Col md={3}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Limit</Form.Label>
                  <Form.Select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </Form.Select>
                </Form.Group>
              </Col>
            </Row>
          </Form>
        </Card.Body>
      </Card>

      {/* Main Table Card */}
      <Card className="border-0 shadow-sm">
        <Card.Body className="p-0">
          {loading ? (
            <div className="text-center py-5"><Spinner animation="border" variant="primary" /></div>
          ) : logs.length === 0 ? (
            <div className="text-center py-5 text-muted">No recognition logs found.</div>
          ) : (
            <Table hover responsive className="mb-0 align-middle">
              <thead className="bg-light text-muted small text-uppercase">
                <tr>
                  <th className="px-4">ID</th>
                  <th>Image</th>
                  <th>Status</th>
                  <th>Matched Enrollment</th>
                  <th>Matched User</th>
                  <th>Device</th>
                  <th className="px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-4 text-muted">#{log.id}</td>
                    <td>
                      <Button
                        size="sm"
                        variant="outline-primary"
                        onClick={() => handleShowImage(log)}
                      >
                        Preview
                      </Button>
                    </td>
                    <td>{getStatusBadge(log.status)}</td>
                    <td>
                      {log.matched_enrollment_id ? (
                        <span className="fw-bold text-primary">#{log.matched_enrollment_id}</span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      {log.matched_user_id ? (
                        <div>
                          <div className="fw-bold">{log.matched_user_name || 'User'}</div>
                          <div className="small text-muted">ID: {log.matched_user_id}</div>
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      <Badge bg="light" text="dark" className="border" style={{marginRight: '12px'}}>
                        {getFriendlyDeviceName(devices.find((d) => String(d.id) === String(log.device_id))) || 'Unknown'}
                      </Badge>
                    </td>
                    <td className="px-4 text-muted small">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      {/* Image Modal */}
      <Modal show={Boolean(previewLogId)} onHide={closePreview} centered size="lg">
        <Modal.Header closeButton className="border-0 pb-0">
          <Modal.Title className="h5">Log #{previewLogId}</Modal.Title>
        </Modal.Header>
        <Modal.Body className="text-center p-4">
          {previewLoading ? (
            <Spinner animation="border" variant="primary" />
          ) : (previewLogId && previewImageUrl) ? (
            <img
              src={previewImageUrl}
              alt="Recognition log"
              className="img-fluid rounded shadow-sm"
              style={{ maxHeight: '70vh' }}
            />
          ) : (
            <p className="text-muted mb-0">Image unavailable.</p>
          )}
        </Modal.Body>
      </Modal>
    </Container>
  );
}