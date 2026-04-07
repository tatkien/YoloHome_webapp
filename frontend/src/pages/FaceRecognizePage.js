import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Container, Row, Col, Form, Button, Alert, Spinner } from 'react-bootstrap';
import api from '../services/api';

const MAX_FRAMES_PER_ATTEMPT = 3;
const WARMUP_MS = 1000;
const FRAME_INTERVAL_MS = 180;
const MAX_FAILED_ATTEMPTS = 3;
const ATTEMPT_RETRY_MS = 1000;

const sleep = (ms) => new Promise((resolve) => {
  window.setTimeout(resolve, ms);
});

export default function FaceRecognizePage() {
  const [preview, setPreview] = useState(null);
  const [deviceId, setDeviceId] = useState('');
  const [deviceKey, setDeviceKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [phaseText, setPhaseText] = useState('Camera is off');
  const [currentFrame, setCurrentFrame] = useState(0);
  const [cameraPermissionDenied, setCameraPermissionDenied] = useState(false);

  const isLocked = failedAttempts >= MAX_FAILED_ATTEMPTS;

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  const statusText = (result?.status || '').toLowerCase();
  const isRecognized = statusText === 'recognized';
  const isSpoof = statusText.includes('spoof');
  const resultStatusClass = isRecognized ? 'recognized' : (isSpoof ? 'spoof' : 'unknown');
  const resultBadgeClass = isRecognized ? 'badge-recognized' : (isSpoof ? 'badge-spoof' : 'badge-unknown');
  const resultBadgeText = isRecognized ? '✓ Recognized' : (isSpoof ? '⚠ Spoof' : '? Unknown');

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
      const label = result.matched_user_name
        ? `${result.matched_user_name} (${((result.confidence || 0) * 100).toFixed(1)}%)`
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

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraOn(false);
    setPhaseText('Camera is off');
  }, []);

  useEffect(() => () => {
    stopCamera();
  }, [stopCamera]);

  const startCamera = useCallback(async () => {
    if (streamRef.current) {
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user',
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await new Promise((resolve) => {
          videoRef.current.onloadedmetadata = () => {
            resolve();
          };
        });
        await videoRef.current.play();
      }
      setCameraPermissionDenied(false);
      setCameraOn(true);
      setPhaseText('Camera ready');
    } catch (err) {
      setCameraPermissionDenied(true);
      setError('Camera access was denied. Please allow camera permission and try again.');
      throw err;
    }
  }, []);

  const captureCurrentFrame = useCallback(async () => {
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      throw new Error('Camera frame is not ready yet');
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.72);
    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((b) => {
        if (!b) {
          reject(new Error('Unable to capture camera frame'));
          return;
        }
        resolve(b);
      }, 'image/jpeg', 0.72);
    });

    return { blob, dataUrl };
  }, []);

  const submitFrame = useCallback(async (blob, index) => {
    const formData = new FormData();
    formData.append('image', blob, `frame-${index}.jpg`);
    if (deviceId) formData.append('device_id', deviceId);

    const headers = { 'Content-Type': 'multipart/form-data' };
    if (deviceKey) headers['X-Device-Key'] = deviceKey;

    const res = await api.post('/face/recognize', formData, { headers });
    return res.data;
  }, [deviceId, deviceKey]);

  const handleRecognize = async (e) => {
    e.preventDefault();
    if (isLocked) {
      setError('Maximum failed tries reached. Camera has been stopped for this session.');
      return;
    }

    setError('');
    setLoading(true);
    setResult(null);
    setCurrentFrame(0);

    try {
      if (!streamRef.current) {
        setPhaseText('Opening camera...');
        await startCamera();
      }

      setPhaseText(`Warming up camera for ${WARMUP_MS / 1000}s...`);
      await sleep(WARMUP_MS);

      let consecutiveFails = failedAttempts;
      let attemptNo = 0;
      let recognized = null;

      while (!recognized && consecutiveFails < MAX_FAILED_ATTEMPTS) {
        attemptNo += 1;
        let lastResponse = null;

        for (let i = 1; i <= MAX_FRAMES_PER_ATTEMPT; i += 1) {
          setCurrentFrame(i);
          setPhaseText(`Attempt ${attemptNo}: capturing frame ${i}/${MAX_FRAMES_PER_ATTEMPT}...`);
          const { blob, dataUrl } = await captureCurrentFrame();
          setPreview(dataUrl);

          setPhaseText(`Attempt ${attemptNo}: sending frame ${i}/${MAX_FRAMES_PER_ATTEMPT}...`);
          const response = await submitFrame(blob, i);
          lastResponse = response;

          if (response.status === 'recognized') {
            recognized = response;
            setPhaseText(`Recognized on attempt ${attemptNo}, frame ${i}. Early stop applied.`);
            break;
          }

          if (i < MAX_FRAMES_PER_ATTEMPT) {
            await sleep(FRAME_INTERVAL_MS);
          }
        }

        if (recognized) {
          setResult(recognized);
          setFailedAttempts(0);
          stopCamera();
          setPhaseText('Recognized. Camera turned off.');
          break;
        }

        consecutiveFails += 1;
        setResult(lastResponse);
        setFailedAttempts(consecutiveFails);

        if (consecutiveFails >= MAX_FAILED_ATTEMPTS) {
          setPhaseText('No match after maximum failed attempts. Camera turned off.');
          stopCamera();
          setError('Maximum failed tries reached. Camera has been turned off.');
          break;
        }

        setPhaseText(`Attempt ${attemptNo} failed. Waiting ${ATTEMPT_RETRY_MS / 1000}s before retry...`);
        await sleep(ATTEMPT_RETRY_MS);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Recognition failed');
    } finally {
      setLoading(false);
      setCurrentFrame(0);
    }
  };

  const reset = () => {
    setPreview(null);
    setResult(null);
    setError('');
    setPhaseText(cameraOn ? 'Camera ready' : 'Camera is off');
    setFailedAttempts(0);
    setCurrentFrame(0);
    if (cameraOn) {
      stopCamera();
    }
  };

  return (
    <Container className="py-4 fade-in">
      <div className="page-header">
        <h1>Face Recognition</h1>
        <p>Click recognize to open webcam, warm up 1 second, and evaluate up to 3 frames</p>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}

      <Row className="g-4">
        {/* Camera panel */}
        <Col lg={6}>
          <div className="yh-card p-4">
            <h5 style={{ fontWeight: 600, marginBottom: '1rem' }}>Live Camera Demo</h5>
            <Form onSubmit={handleRecognize}>
              <div className="file-upload-zone mb-3" >
                <video
                  ref={videoRef}
                  muted
                  autoPlay
                  playsInline
                  style={{
                    width: '100%',
                    height: '300px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-input)',
                    objectFit: 'cover',
                    border: "3px solid black"
                  }}
                />
                <canvas ref={captureCanvasRef} style={{ display: 'none' }} />
              </div>

              <div style={{ marginBottom: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                {phaseText}
                {currentFrame > 0 ? ` (frame ${currentFrame}/${MAX_FRAMES_PER_ATTEMPT})` : ''}
              </div>

              <div style={{ marginBottom: '1rem', color: isLocked ? 'var(--accent-red)' : 'var(--text-muted)', fontSize: '0.85rem' }}>
                Failed attempts: {failedAttempts}/{MAX_FAILED_ATTEMPTS}
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
                <Button type="submit" disabled={loading || isLocked} className="flex-grow-1">
                  {loading ? <><Spinner size="sm" animation="border" /> Recognizing...</> : '🔍 Recognize (Webcam)'}
                </Button>
                <Button
                  variant="outline-dark"
                  onClick={cameraOn ? stopCamera : startCamera}
                  type="button"
                  disabled={loading || isLocked}
                >
                  {cameraOn ? 'Stop Camera' : 'Start Camera'}
                </Button>
                <Button variant="outline-dark" onClick={reset}>Reset</Button>
              </div>

              {cameraPermissionDenied && (
                <div style={{ marginTop: '0.75rem', color: 'var(--accent-yellow)', fontSize: '0.85rem' }}>
                  Browser blocked camera access. Allow permission and retry.
                </div>
              )}
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
                  maxHeight: '350px',
                  objectFit: 'contain',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-input)',
                }}
              />
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={`result-card ${resultStatusClass}`}>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 style={{ fontWeight: 700, margin: 0 }}>Recognition Result</h5>
                <span className={resultBadgeClass}>
                  {resultBadgeText}
                </span>
              </div>

              <Row className="g-3">
                <Col xs={6}>
                  <div className="stat-label">Status</div>
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: '1.1rem',
                      color: isRecognized
                        ? 'var(--accent-green)'
                        : (isSpoof ? 'var(--accent-red)' : 'var(--accent-yellow)'),
                    }}
                  >
                    {result.status.toUpperCase()}
                  </div>
                </Col>
                <Col xs={6}>
                  <div className="stat-label">Log ID</div>
                  <div style={{ fontWeight: 600 }}>#{result.log_id}</div>
                </Col>

                {result.matched_user_name && (
                  <Col xs={6}>
                    <div className="stat-label">Matched User</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--accent-green)' }}>
                      {result.matched_user_name}
                    </div>
                  </Col>
                )}

                {result.matched_user_id && (
                  <Col xs={6}>
                    <div className="stat-label">Matched User ID</div>
                    <div style={{ fontWeight: 600 }}>#{result.matched_user_id}</div>
                  </Col>
                )}

                {result.matched_enrollment_id && (
                  <Col xs={6}>
                    <div className="stat-label">Enrollment ID</div>
                    <div style={{ fontWeight: 600 }}>#{result.matched_enrollment_id}</div>
                  </Col>
                )}

                {isSpoof && result.anti_spoof_score != null && (
                  <Col xs={6}>
                    <div className="stat-label">Anti-Spoof Score</div>
                    <div style={{ fontWeight: 700, color: 'var(--accent-red)' }}>
                      {(result.anti_spoof_score * 100).toFixed(2)}%
                    </div>
                  </Col>
                )}
              </Row>
            </div>
          )}

          {!preview && !result && (
            <div className="yh-card p-4 d-flex align-items-center justify-content-center" style={{ minHeight: '300px', border: '3px dashed black',marginTop: '64px' }}>
              <div className="text-center" style={{ color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🖼️</div>
                <p>Model recognition area</p>
              </div>
            </div>
          )}
        </Col>
      </Row>
    </Container>
  );
}
