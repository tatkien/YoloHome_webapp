import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Container, Table, Form, Alert, Spinner, Row, Col, Button, Modal,
} from 'react-bootstrap';
import api from '../services/api';

export default function FaceLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
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

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

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

  // Stats
  const recognized = logs.filter((l) => l.status === 'recognized').length;
  const spoof = logs.filter((l) => (l.status || '').toLowerCase().includes('spoof')).length;
  const unknown = logs.filter((l) => l.status === 'unknown').length;

  return (
    <Container className="py-4 fade-in">
      <div className="page-header">
        <h1>📋 Recognition Logs</h1>
        <p>View face recognition attempt history</p>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}

      {/* Stats */}
      <Row className="g-3 mb-4">
        <Col md={3}>
          <div className="yh-card p-3 text-center">
            <div className="stat-value">{logs.length}</div>
            <div className="stat-label">Total Logs</div>
          </div>
        </Col>
        <Col md={3}>
          <div className="yh-card p-3 text-center">
            <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--accent-green)' }}>{recognized}</div>
            <div className="stat-label">Recognized</div>
          </div>
        </Col>
        <Col md={3}>
          <div className="yh-card p-3 text-center">
            <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--accent-red)' }}>{spoof}</div>
            <div className="stat-label">Spoof</div>
          </div>
        </Col>
        <Col md={3}>
          <div className="yh-card p-3 text-center">
            <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--accent-yellow)' }}>{unknown}</div>
            <div className="stat-label">Unknown</div>
          </div>
        </Col>
      </Row>

      {/* Filters */}
      <div className="yh-card p-3 mb-4">
        <Row className="align-items-end g-3">
          <Col md={3}>
            <Form.Label>Device ID</Form.Label>
            <Form.Control
              type="number"
              placeholder="All devices"
              value={filterDeviceId}
              onChange={(e) => setFilterDeviceId(e.target.value)}
            />
          </Col>
          <Col md={3}>
            <Form.Label>Limit</Form.Label>
            <Form.Select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </Form.Select>
          </Col>
          <Col md={2}>
            <Button variant="outline-light" onClick={() => { setFilterDeviceId(''); setLimit(100); }} className="w-100">
              Clear
            </Button>
          </Col>
          <Col md={2}>
            <Button onClick={fetchLogs} className="w-100">Refresh</Button>
          </Col>
        </Row>
      </div>

      {/* Logs Table */}
      <div className="yh-card p-4">
        {loading ? (
          <div className="text-center py-4"><Spinner animation="border" /></div>
        ) : logs.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>No recognition logs found.</p>
        ) : (
          <div className="table-responsive">
            <Table hover>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Image</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Matched Enrollment</th>
                  <th>Matched User</th>
                  <th>Device</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.id}</td>
                    <td>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline-light"
                        onClick={() => handleShowImage(log)}
                      >
                        Show Image
                      </Button>
                    </td>
                    <td>
                      <span className={(log.status || '').toLowerCase() === 'recognized'
                        ? 'badge-recognized'
                        : ((log.status || '').toLowerCase().includes('spoof') ? 'badge-spoof' : 'badge-unknown')}
                      >
                        {log.status}
                      </span>
                    </td>
                    <td>
                      {log.confidence != null ? (
                        <span style={{
                          fontWeight: 600,
                          color: log.confidence >= 0.7 ? 'var(--accent-green)'
                            : log.confidence >= 0.4 ? 'var(--accent-yellow)'
                            : 'var(--accent-red)',
                        }}>
                          {(log.confidence * 100).toFixed(2)}%
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td>
                      {log.matched_enrollment_id
                        ? <span style={{ fontWeight: 600 }}>#{log.matched_enrollment_id}</span>
                        : <span style={{ color: 'var(--text-muted)' }}>—</span>
                      }
                    </td>
                    <td>
                      {log.matched_user_id ? (
                        <span style={{ fontWeight: 600 }}>
                          {log.matched_user_name || `User #${log.matched_user_id}`}
                          <small style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>#{log.matched_user_id}</small>
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td>{log.device_id ?? <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </div>

      <Modal show={Boolean(previewLogId)} onHide={closePreview} centered size="lg">
        <Modal.Header closeButton>
          <Modal.Title>{previewLogId ? `Recognition Log #${previewLogId}` : 'Recognition Log'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {previewLoading ? (
            <div className="text-center py-4"><Spinner animation="border" /></div>
          ) : (previewLogId && previewImageUrl) ? (
            <img
              src={previewImageUrl}
              alt={`Recognition log ${previewLogId}`}
              style={{ width: '100%', borderRadius: '10px' }}
            />
          ) : (
            <p style={{ color: 'var(--text-muted)', margin: 0 }}>Image unavailable.</p>
          )}
        </Modal.Body>
      </Modal>
    </Container>
  );
}
