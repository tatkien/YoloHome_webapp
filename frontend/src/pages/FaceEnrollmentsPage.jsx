import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Container, Table, Button, Form, Alert, Spinner, Row, Col, Modal,
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

export default function FaceEnrollmentsPage() {
  const [enrollments, setEnrollments] = useState([]);
  const [devices, setDevices] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(false);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filterDeviceId, setFilterDeviceId] = useState('');
  const [showImageModal, setShowImageModal] = useState(false);
  const [selectedEnrollment, setSelectedEnrollment] = useState(null);
  const [selectedEnrollmentImageUrl, setSelectedEnrollmentImageUrl] = useState('');
  const [selectedEnrollmentImageLoading, setSelectedEnrollmentImageLoading] = useState(false);
  const [selectedEnrollmentImageError, setSelectedEnrollmentImageError] = useState('');
  const [selectedEnrollmentImageNaturalSize, setSelectedEnrollmentImageNaturalSize] = useState(null);

  // Enroll modal
  const [showEnroll, setShowEnroll] = useState(false);
  const [enrollUserId, setEnrollUserId] = useState('');
  const [enrollFile, setEnrollFile] = useState(null);
  const [enrollPreview, setEnrollPreview] = useState(null);
  const [enrollInputMode, setEnrollInputMode] = useState('upload');
  const [cameraDevice, setCameraDevice] = useState(null);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [enrollLoading, setEnrollLoading] = useState(false);
  const [enrollError, setEnrollError] = useState('');
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

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

  const fetchUsers = useCallback(async () => {
    try {
      setUsersLoading(true);
      const res = await api.get('/admin/users/');
      setUsers(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      setDevicesLoading(true);
      const res = await api.get('/devices/');
      setDevices(res.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load devices');
    } finally {
      setDevicesLoading(false);
    }
  }, []);

  useEffect(() => { fetchEnrollments(); }, [fetchEnrollments]);
  useEffect(() => { fetchUsers(); }, [fetchUsers]);
  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  // Fetch camera device for enrollment
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/face/camera');
        setCameraDevice(res.data.camera);
      } catch {
        setCameraDevice(null);
      }
    })();
  }, []);

  useEffect(() => () => {
    if (selectedEnrollmentImageUrl) {
      URL.revokeObjectURL(selectedEnrollmentImageUrl);
    }
  }, [selectedEnrollmentImageUrl]);

  useEffect(() => {
    if (!cameraActive || enrollInputMode !== 'webcam') return;
    if (!videoRef.current || !streamRef.current) return;

    videoRef.current.srcObject = streamRef.current;
    const playPromise = videoRef.current.play();
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch(() => {
      });
    }
  }, [cameraActive, enrollInputMode]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      stopCamera();
      setEnrollInputMode('upload');
      setEnrollFile(file);
      const reader = new FileReader();
      reader.onload = (ev) => setEnrollPreview(ev.target.result);
      reader.readAsDataURL(file);
    }
  };

  const startCamera = async () => {
    try {
      setError('');
      setCameraLoading(true);
      stopCamera();
      setEnrollInputMode('webcam');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      setCameraActive(true);
    } catch (_err) {
      setError('Could not access webcam. Check browser permissions and HTTPS/localhost context.');
      setEnrollInputMode('upload');
    } finally {
      setCameraLoading(false);
    }
  };

  const captureFromWebcam = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    if (!video.videoWidth || !video.videoHeight) {
      setError('Webcam is not ready yet. Please try again.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (!blob) {
        setError('Failed to capture image from webcam.');
        return;
      }
      const capturedFile = new File([blob], `webcam-${Date.now()}.jpg`, { type: 'image/jpeg' });
      setEnrollFile(capturedFile);
      setEnrollPreview(URL.createObjectURL(blob));
      stopCamera();
    }, 'image/jpeg', 0.92);
  };

  const handleEnroll = async (e) => {
    e.preventDefault();
    setEnrollError('');
    if (!enrollUserId) {
      setEnrollError('Please select a registered user');
      return;
    }
    if (!enrollFile) {
      setEnrollError('Please select an image file');
      return;
    }
    setEnrollLoading(true);
    try {
      const formData = new FormData();
      formData.append('image', enrollFile);
      formData.append('user_id', enrollUserId);
      formData.append('device_id', cameraDevice.id);

      await api.post('/face/enrollments/image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const selectedUser = users.find((u) => String(u.id) === String(enrollUserId));
      const userLabel = selectedUser?.full_name || selectedUser?.username || `User #${enrollUserId}`;
      setSuccess(`Face enrolled for "${userLabel}"`);
      setShowEnroll(false);
      resetEnrollForm();
      fetchEnrollments();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setEnrollError(err.response?.data?.detail || 'Enrollment failed');
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

  const openEnrollmentImage = async (enrollment) => {
    if (!enrollment?.image_path) return;
    setSelectedEnrollment(enrollment);
    setSelectedEnrollmentImageError('');
    setSelectedEnrollmentImageLoading(true);
    setSelectedEnrollmentImageNaturalSize(null);
    setShowImageModal(true);

    try {
      const res = await api.get(`/face/enrollments/${enrollment.id}/image`, { responseType: 'blob' });
      const objectUrl = URL.createObjectURL(res.data);
      setSelectedEnrollmentImageUrl((currentUrl) => {
        if (currentUrl) URL.revokeObjectURL(currentUrl);
        return objectUrl;
      });
    } catch (err) {
      setSelectedEnrollmentImageError(err.response?.data?.detail || 'Failed to load enrollment image');
    } finally {
      setSelectedEnrollmentImageLoading(false);
    }
  };

  const closeEnrollmentImageModal = () => {
    setShowImageModal(false);
    setSelectedEnrollment(null);
    setSelectedEnrollmentImageError('');
    setSelectedEnrollmentImageLoading(false);
    setSelectedEnrollmentImageNaturalSize(null);
    setSelectedEnrollmentImageUrl((currentUrl) => {
      if (currentUrl) URL.revokeObjectURL(currentUrl);
      return '';
    });
  };

  const handleEnrollmentImageLoad = (event) => {
    setSelectedEnrollmentImageNaturalSize({
      width: event.currentTarget.naturalWidth,
      height: event.currentTarget.naturalHeight,
    });
  };

  const resetEnrollForm = () => {
    stopCamera();
    setEnrollUserId('');
    setEnrollFile(null);
    setEnrollPreview(null);
    setEnrollInputMode('upload');
    setCameraLoading(false);
    setEnrollError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getDeviceLabelById = (deviceId) => {
    const found = devices.find((d) => String(d.id) === String(deviceId));
    return found ? getFriendlyDeviceName(found) : 'Unknown device';
  };

  return (
    <Container className="py-4 fade-in">
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h1>Face Enrollments</h1>
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
            <Form.Label>Filter by Device</Form.Label>
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
                  <th>User</th>
                  <th>Device</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {enrollments.map((e) => (
                  <tr key={e.id}>
                    <td style={{ fontWeight: 600 }}>
                      {e.user_name || `User #${e.user_id}`}
                      {e.user_id ? (
                        <small style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>#{e.user_id}</small>
                      ) : null}
                    </td>
                    <td>
                      {e.device_id
                        ? getDeviceLabelById(e.device_id)
                        : <span style={{ color: 'var(--text-muted)' }}>Global</span>}
                    </td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td>
                      <div className="d-flex gap-2 justify-content-end">
                        <Button
                          variant="outline-dark"
                          size="sm"
                          onClick={() => openEnrollmentImage(e)}
                          disabled={!e.image_path}
                        >
                          Preview
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDelete(e.id, e.user_name || `User #${e.user_id}`)}
                        >
                          Delete
                        </Button>
                      </div>
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
            {enrollError && (
              <Alert variant="danger" dismissible onClose={() => setEnrollError('')}>
                {enrollError}
              </Alert>
            )}
            <Row>
              <Col md={6}>
                <Form.Group className="mb-3">
                  <Form.Label>Registered User</Form.Label>
                  <Form.Select
                    value={enrollUserId}
                    onChange={(e) => setEnrollUserId(e.target.value)}
                    required
                    autoFocus
                    disabled={usersLoading}
                  >
                    <option value="">Select a user</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name || u.username} (#{u.id})
                      </option>
                    ))}
                  </Form.Select>
                  {usersLoading && (
                    <small style={{ color: 'var(--text-muted)' }}>Loading users...</small>
                  )}
                </Form.Group>
                <Form.Group className="mb-3">
                  <Form.Label>Camera Device</Form.Label>
                  {cameraDevice ? (
                    <div style={{
                      background: 'var(--bg-input)', border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)', padding: '0.65rem 1rem',
                      color: 'var(--accent-green)', fontWeight: 600,
                    }}>
                      📷 Camera
                    </div>
                  ) : (
                    <div style={{
                      background: 'var(--bg-input)', border: '1px solid var(--accent-red)',
                      borderRadius: 'var(--radius-sm)', padding: '0.65rem 1rem',
                      color: 'var(--accent-red)',
                    }}>
                      No camera device found. Add a camera device first.
                    </div>
                  )}
                </Form.Group>
                <Form.Group className="mb-3">
                  <Form.Label>Face Photo</Form.Label>
                  <div className="d-flex gap-2 mb-2">
                    <Button
                      type="button"
                      variant={enrollInputMode === 'upload' ? 'primary' : 'outline-dark'}
                      onClick={() => {
                        stopCamera();
                        setEnrollInputMode('upload');
                      }}
                    >
                      Upload
                    </Button>
                    <Button
                      type="button"
                      variant={enrollInputMode === 'webcam' ? 'primary' : 'outline-dark'}
                      onClick={startCamera}
                      disabled={cameraLoading}
                    >
                      {cameraLoading ? 'Starting camera...' : 'Use Webcam'}
                    </Button>
                    {cameraActive && (
                      <Button type="button" variant="outline-dark" onClick={captureFromWebcam}>Capture</Button>
                    )}
                  </div>
                  <div
                    className={`border rounded p-4 text-center ${enrollFile ? 'border-success bg-success bg-opacity-10' : 'border-secondary bg-light'} d-flex flex-column justify-content-center align-items-center`}
                    onClick={() => {
                      stopCamera();
                      setEnrollInputMode('upload');
                      if (fileInputRef.current) {
                        fileInputRef.current.click();
                      }
                    }}
                    style={{ cursor: 'pointer', minHeight: '150px', transition: 'all 0.2s' }}
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
                        <div style={{ color: 'var(--text-secondary)' }}>
                          {enrollInputMode === 'webcam' ? 'Use Capture when webcam is ready' : 'Click to select a photo'}
                        </div>
                        <small style={{ color: 'var(--text-muted)' }}>JPEG, PNG, or WebP</small>
                      </div>
                    )}
                  </div>
                </Form.Group>
              </Col>
              <Col md={6} className="d-flex align-items-center justify-content-center">
                {enrollInputMode === 'webcam' && cameraActive ? (
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    style={{
                      width: '100%',
                      maxHeight: '280px',
                      borderRadius: 'var(--radius)',
                      border: '1px solid var(--border-color)',
                      objectFit: 'cover',
                    }}
                  />
                ) : enrollPreview ? (
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
                    height: '300px',
                    background: 'var(--bg-input)',
                    borderRadius: 'var(--radius)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-muted)',
                    overflow: 'hidden',
                    position: 'relative',
                    border: '1px solid var(--border-color, #ccc)' 
                  }}>
                    {error ? (
                      <span style={{ fontSize: '14px' }}>Camera unavailable</span>
                    ) : (
                      <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        style={{
                          width: '105%',
                          height: '300px',
                          objectFit: 'cover',
                          transform: 'scaleX(-1)', 
                          backgroundColor: '#000',
                          border: '1px solid black'
                        }}
                      />
                    )}
                  </div>
                )}
              </Col>
            </Row>
          </Modal.Body>
          <Modal.Footer>
            <Button type="button" variant="outline-dark" onClick={() => { setShowEnroll(false); resetEnrollForm(); }}>
              Cancel
            </Button>
            <Button type="submit" disabled={enrollLoading || !enrollFile || !enrollUserId || !cameraDevice}>
              {enrollLoading ? <Spinner size="sm" animation="border" /> : 'Enroll Face'}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>

      <Modal show={showImageModal} onHide={closeEnrollmentImageModal} centered size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            {selectedEnrollment ? `Enrollment #${selectedEnrollment.id} Image` : 'Enrollment Image'}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedEnrollmentImageError ? (
            <Alert variant="danger" className="mb-0">
              {selectedEnrollmentImageError}
            </Alert>
          ) : selectedEnrollmentImageLoading ? (
            <div className="text-center py-4">
              <Spinner animation="border" />
            </div>
          ) : selectedEnrollmentImageUrl ? (
            <div style={{ position: 'relative', width: '100%' }}>
              <img
                src={selectedEnrollmentImageUrl}
                alt={selectedEnrollment ? `Enrollment ${selectedEnrollment.id}` : 'Enrollment'}
                onLoad={handleEnrollmentImageLoad}
                style={{
                  width: '100%',
                  height: 'auto',
                  display: 'block',
                  borderRadius: 'var(--radius)',
                  border: '1px solid var(--border-color)',
                }}
              />
              {selectedEnrollment?.bbox && selectedEnrollmentImageNaturalSize ? (() => {
                const [x1, y1, x2, y2] = selectedEnrollment.bbox;
                const { width, height } = selectedEnrollmentImageNaturalSize;
                const left = (x1 / width) * 100;
                const top = (y1 / height) * 100;
                const boxWidth = ((x2 - x1) / width) * 100;
                const boxHeight = ((y2 - y1) / height) * 100;
                return (
                  <div
                    style={{
                      position: 'absolute',
                      left: `${left}%`,
                      top: `${top}%`,
                      width: `${boxWidth}%`,
                      height: `${boxHeight}%`,
                      border: '2px solid #ff5b5b',
                      boxShadow: '0 0 0 1px rgba(0,0,0,0.15)',
                      pointerEvents: 'none',
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        top: '-1.7rem',
                        left: 0,
                        background: '#ff5b5b',
                        color: '#fff',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '0.2rem 0.45rem',
                        borderRadius: '0.35rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      bbox
                    </div>
                  </div>
                );
              })() : null}
            </div>
          ) : (
            <div className="text-center py-4" style={{ color: 'var(--text-muted)' }}>
              No image available.
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-light" onClick={closeEnrollmentImageModal}>Close</Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
}
