import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Container, Row, Col, Form, Button, Alert, Spinner } from 'react-bootstrap';
import api from '../services/api';

export default function FaceRecognizePage() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [deviceId, setDeviceId] = useState('');
  const [deviceKey, setDeviceKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  // Draw image + optional bbox overlay on canvas
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;

    const ctx = canvas.getContext('2d');
    // Match canvas internal size to natural image size
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;

    // Draw the image
    ctx.drawImage(img, 0, 0);

    // Draw bounding box if available
    if (result?.bbox && result.bbox.length === 4) {
      const [x1, y1, x2, y2] = result.bbox;
      ctx.strokeStyle = 'red';
      ctx.lineWidth = Math.max(2, Math.round(img.naturalWidth / 200));
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Label
      const label = result.matched_name
        ? `${result.matched_name} (${((result.confidence || 0) * 100).toFixed(1)}%)`
        : `Face (${((result.detection_score || 0) * 100).toFixed(1)}%)`;
      const fontSize = Math.max(14, Math.round(img.naturalWidth / 40));
      ctx.font = `bold ${fontSize}px sans-serif`;
      const textWidth = ctx.measureText(label).width;
      const padding = 4;
      // Background for label
      ctx.fillStyle = 'red';
      ctx.fillRect(x1, y1 - fontSize - padding * 2, textWidth + padding * 2, fontSize + padding * 2);
      ctx.fillStyle = 'white';
      ctx.fillText(label, x1 + padding, y1 - padding);
    }
  }, [result]);

  useEffect(() => {
    drawCanvas();
  }, [preview, result, drawCanvas]);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) {
      setFile(f);
      setResult(null);
      const reader = new FileReader();
      reader.onload = (ev) => setPreview(ev.target.result);
      reader.readAsDataURL(f);
    }
  };

  const handleRecognize = async (e) => {
    e.preventDefault();
    if (!file) return;
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('image', file);
      if (deviceId) formData.append('device_id', deviceId);

      const headers = { 'Content-Type': 'multipart/form-data' };
      if (deviceKey) headers['X-Device-Key'] = deviceKey;

      const res = await api.post('/face/recognize', formData, { headers });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Recognition failed');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError('');
  };

  return (
    <Container className="py-4 fade-in">
      <div className="page-header">
        <h1>🔍 Face Recognition</h1>
        <p>Upload an image to identify a person against enrolled faces</p>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}

      <Row className="g-4">
        {/* Upload panel */}
        <Col lg={6}>
          <div className="yh-card p-4">
            <h5 style={{ fontWeight: 600, marginBottom: '1rem' }}>Upload Image</h5>
            <Form onSubmit={handleRecognize}>
              <div
                className={`file-upload-zone mb-3 ${file ? 'has-file' : ''}`}
                onClick={() => fileInputRef.current.click()}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />
                {file ? (
                  <div>
                    <div style={{ color: 'var(--accent-green)', fontWeight: 600 }}>✓ {file.name}</div>
                    <small style={{ color: 'var(--text-muted)' }}>
                      {(file.size / 1024).toFixed(1)} KB — click to change
                    </small>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>📸</div>
                    <div style={{ color: 'var(--text-secondary)' }}>Click to select image</div>
                    <small style={{ color: 'var(--text-muted)' }}>JPEG, PNG, or WebP</small>
                  </div>
                )}
              </div>

              <Row className="mb-3">
                <Col>
                  <Form.Label>Device ID <small style={{ color: 'var(--text-muted)' }}>(optional)</small></Form.Label>
                  <Form.Control
                    type="number"
                    placeholder="Device ID"
                    value={deviceId}
                    onChange={(e) => setDeviceId(e.target.value)}
                  />
                </Col>
                <Col>
                  <Form.Label>X-Device-Key <small style={{ color: 'var(--text-muted)' }}>(optional)</small></Form.Label>
                  <Form.Control
                    type="text"
                    placeholder="Device key"
                    value={deviceKey}
                    onChange={(e) => setDeviceKey(e.target.value)}
                  />
                </Col>
              </Row>

              <div className="d-flex gap-2">
                <Button type="submit" disabled={loading || !file} className="flex-grow-1">
                  {loading ? <><Spinner size="sm" animation="border" /> Recognizing...</> : '🔍 Recognize'}
                </Button>
                <Button variant="outline-light" onClick={reset}>Reset</Button>
              </div>
            </Form>
          </div>
        </Col>

        {/* Preview + Result panel */}
        <Col lg={6}>
          {/* Image preview */}
          {preview && (
            <div className="yh-card p-4 mb-4">
              <h6 style={{ fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>Image Preview</h6>
              {/* Hidden image used as canvas source */}
              <img
                ref={imgRef}
                src={preview}
                alt="Upload preview"
                onLoad={drawCanvas}
                style={{ display: 'none' }}
              />
              <canvas
                ref={canvasRef}
                style={{
                  width: '100%',
                  maxHeight: '400px',
                  objectFit: 'contain',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-input)',
                }}
              />
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={`result-card ${result.status}`}>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 style={{ fontWeight: 700, margin: 0 }}>Recognition Result</h5>
                <span className={result.status === 'recognized' ? 'badge-recognized' : 'badge-unknown'}>
                  {result.status === 'recognized' ? '✓ Recognized' : '? Unknown'}
                </span>
              </div>

              <Row className="g-3">
                <Col xs={6}>
                  <div className="stat-label">Status</div>
                  <div style={{ fontWeight: 600, fontSize: '1.1rem', color: result.status === 'recognized' ? 'var(--accent-green)' : 'var(--accent-yellow)' }}>
                    {result.status.toUpperCase()}
                  </div>
                </Col>
                <Col xs={6}>
                  <div className="stat-label">Log ID</div>
                  <div style={{ fontWeight: 600 }}>#{result.log_id}</div>
                </Col>

                {result.matched_name && (
                  <Col xs={6}>
                    <div className="stat-label">Matched Person</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--accent-green)' }}>
                      {result.matched_name}
                    </div>
                  </Col>
                )}

                {result.confidence != null && (
                  <Col xs={6}>
                    <div className="stat-label">Confidence</div>
                    <div className="stat-value">{(result.confidence * 100).toFixed(2)}%</div>
                  </Col>
                )}

                {result.matched_enrollment_id && (
                  <Col xs={6}>
                    <div className="stat-label">Enrollment ID</div>
                    <div style={{ fontWeight: 600 }}>#{result.matched_enrollment_id}</div>
                  </Col>
                )}

                {result.detection_score != null && (
                  <Col xs={6}>
                    <div className="stat-label">Detection Score</div>
                    <div style={{ fontWeight: 600 }}>{result.detection_score}</div>
                  </Col>
                )}

                {result.bbox && (
                  <Col xs={12}>
                    <div className="stat-label">Bounding Box</div>
                    <code style={{ color: 'var(--accent-blue)', fontSize: '0.85rem' }}>
                      [{result.bbox.map((v) => v.toFixed(1)).join(', ')}]
                    </code>
                  </Col>
                )}
              </Row>
            </div>
          )}

          {!preview && !result && (
            <div className="yh-card p-4 d-flex align-items-center justify-content-center" style={{ minHeight: '200px' }}>
              <div className="text-center" style={{ color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🖼️</div>
                <p>Upload an image to see the preview and recognition result here</p>
              </div>
            </div>
          )}
        </Col>
      </Row>
    </Container>
  );
}
