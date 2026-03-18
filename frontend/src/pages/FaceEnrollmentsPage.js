import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Container, Table, Button, Form, Alert, Spinner, Row, Col, Modal,
} from 'react-bootstrap';
import api from '../services/api';

export default function FaceEnrollmentsPage() {
  const [enrollments, setEnrollments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filterDeviceId, setFilterDeviceId] = useState('');

  // Enroll modal
  const [showEnroll, setShowEnroll] = useState(false);
  const [enrollName, setEnrollName] = useState('');
  const [enrollDeviceId, setEnrollDeviceId] = useState('');
  const [enrollFile, setEnrollFile] = useState(null);
  const [enrollPreview, setEnrollPreview] = useState(null);
  const [enrollLoading, setEnrollLoading] = useState(false);
  const fileInputRef = useRef(null);

  const fetchEnrollments = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (filterDeviceId) params.device_id = filterDeviceId;
      const res = await api.get('/face/enrollments', { params });
      setEnrollments(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load enrollments');
    } finally {
      setLoading(false);
    }
  }, [filterDeviceId]);

  useEffect(() => { fetchEnrollments(); }, [fetchEnrollments]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setEnrollFile(file);
      const reader = new FileReader();
      reader.onload = (ev) => setEnrollPreview(ev.target.result);
      reader.readAsDataURL(file);
    }
  };

  const handleEnroll = async (e) => {
    e.preventDefault();
    if (!enrollFile) {
      setError('Please select an image file');
      return;
    }
    setError('');
    setEnrollLoading(true);
    try {
      const formData = new FormData();
      formData.append('image', enrollFile);
      formData.append('name', enrollName);
      if (enrollDeviceId) formData.append('device_id', enrollDeviceId);

      await api.post('/face/enrollments/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSuccess(`Face enrolled for "${enrollName}"`);
      setShowEnroll(false);
      resetEnrollForm();
      fetchEnrollments();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Enrollment failed');
    } finally {
      setEnrollLoading(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete enrollment for "${name}"?`)) return;
    setError('');
    try {
      await api.delete(`/face/enrollments/${id}`);
      setSuccess(`Enrollment "${name}" deleted`);
      fetchEnrollments();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete');
    }
  };

  const resetEnrollForm = () => {
    setEnrollName('');
    setEnrollDeviceId('');
    setEnrollFile(null);
    setEnrollPreview(null);
  };

  return (
    <Container className="py-4 fade-in">
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1>🧑 Face Enrollments</h1>
          <p>Register known faces for recognition</p>
        </div>
        <Button onClick={() => setShowEnroll(true)}>+ Enroll Face</Button>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {/* Filter */}
      <div className="yh-card p-3 mb-4">
        <Row className="align-items-end">
          <Col md={4}>
            <Form.Label>Filter by Device ID</Form.Label>
            <Form.Control
              type="number"
              placeholder="All devices"
              value={filterDeviceId}
              onChange={(e) => setFilterDeviceId(e.target.value)}
            />
          </Col>
          <Col md={2}>
            <Button variant="outline-light" onClick={() => setFilterDeviceId('')} className="w-100">
              Clear
            </Button>
          </Col>
        </Row>
      </div>

      {/* Table */}
      <div className="yh-card p-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 style={{ fontWeight: 600, margin: 0 }}>Enrolled Faces</h5>
          <span className="badge-device">{enrollments.length} enrolled</span>
        </div>

        {loading ? (
          <div className="text-center py-4"><Spinner animation="border" /></div>
        ) : enrollments.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>No enrollments found. Click "Enroll Face" to register a face.</p>
        ) : (
          <div className="table-responsive">
            <Table hover>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Device</th>
                  <th>Vector Dim</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {enrollments.map((e) => (
                  <tr key={e.id}>
                    <td>{e.id}</td>
                    <td style={{ fontWeight: 600 }}>{e.name}</td>
                    <td>{e.device_id ?? <span style={{ color: 'var(--text-muted)' }}>Global</span>}</td>
                    <td>
                      <span className="badge-device">{e.feature_vector?.length || 0}d</span>
                    </td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td>
                      <Button variant="danger" size="sm" onClick={() => handleDelete(e.id, e.name)}>
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </div>

      {/* Enroll Modal */}
      <Modal show={showEnroll} onHide={() => { setShowEnroll(false); resetEnrollForm(); }} centered size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Enroll New Face</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleEnroll}>
          <Modal.Body>
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Person's Name</Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="e.g. Alice"
                    value={enrollName}
                    onChange={(e) => setEnrollName(e.target.value)}
                    required
                    autoFocus
                  />
                </Form.Group>
                <Form.Group className="mb-3">
                  <Form.Label>Device ID <small style={{ color: 'var(--text-muted)' }}>(optional)</small></Form.Label>
                  <Form.Control
                    type="number"
                    placeholder="Scope to a specific device"
                    value={enrollDeviceId}
                    onChange={(e) => setEnrollDeviceId(e.target.value)}
                  />
                </Form.Group>
                <Form.Group className="mb-3">
                  <Form.Label>Face Photo</Form.Label>
                  <div
                    className={`file-upload-zone ${enrollFile ? 'has-file' : ''}`}
                    onClick={() => fileInputRef.current.click()}
                  >
                    <input
                      type="file"
                      ref={fileInputRef}
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                      style={{ display: 'none' }}
                    />
                    {enrollFile ? (
                      <div>
                        <div style={{ color: 'var(--accent-green)', fontWeight: 600 }}>✓ {enrollFile.name}</div>
                        <small style={{ color: 'var(--text-muted)' }}>
                          {(enrollFile.size / 1024).toFixed(1)} KB — click to change
                        </small>
                      </div>
                    ) : (
                      <div>
                        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📷</div>
                        <div style={{ color: 'var(--text-secondary)' }}>Click to select a photo</div>
                        <small style={{ color: 'var(--text-muted)' }}>JPEG, PNG, or WebP</small>
                      </div>
                    )}
                  </div>
                </Form.Group>
              </Col>
              <Col md={6} className="d-flex align-items-center justify-content-center">
                {enrollPreview ? (
                  <img
                    src={enrollPreview}
                    alt="Preview"
                    style={{
                      maxWidth: '100%',
                      maxHeight: '280px',
                      borderRadius: 'var(--radius)',
                      border: '1px solid var(--border-color)',
                    }}
                  />
                ) : (
                  <div style={{
                    width: '100%',
                    height: '200px',
                    background: 'var(--bg-input)',
                    borderRadius: 'var(--radius)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-muted)',
                  }}>
                    Image preview
                  </div>
                )}
              </Col>
            </Row>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="outline-light" onClick={() => { setShowEnroll(false); resetEnrollForm(); }}>
              Cancel
            </Button>
            <Button type="submit" disabled={enrollLoading || !enrollFile}>
              {enrollLoading ? <Spinner size="sm" animation="border" /> : 'Enroll Face'}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </Container>
  );
}
