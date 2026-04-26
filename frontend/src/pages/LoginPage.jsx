import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import Button from 'react-bootstrap/Button';
import { Alert, Badge, ButtonGroup, Card, Col, Container, ProgressBar, Row, Spinner } from 'react-bootstrap';import { useAuth } from '../contexts/AuthContext';
import { HiEye, HiEyeOff } from 'react-icons/hi';
import api from '../services/api';

const FRAMES_PER_ATTEMPT = 3;
const MAX_ATTEMPTS = 3;
const MAX_FRAMES = FRAMES_PER_ATTEMPT * MAX_ATTEMPTS;
const WARMUP_MS = 1000;
const FRAME_INTERVAL_MS = 180;
const SPOOF_RESET_MS = 15000;
const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

const normalizeStatus = (status) => {
  const s = String(status || '').toLowerCase();
  if (s === 'recognized') return 'recognized';
  if (s.includes('spoof')) return 'spoof';
  return 'unknown';
};

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [camera, setCamera] = useState(null);
  const [cameraLoading, setCameraLoading] = useState(true);
  const [preview, setPreview] = useState(null);
  const [faceLoading, setFaceLoading] = useState(false);
  const [faceError, setFaceError] = useState('');
  const [result, setResult] = useState(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [phaseText, setPhaseText] = useState('Camera is off');
  const [currentFrame, setCurrentFrame] = useState(0);
  const [spoofDetected, setSpoofDetected] = useState(false);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const spoofResetTimerRef = useRef(null);

  const statusText = (result?.status || '').toLowerCase();
  const isRecognized = statusText === 'recognized';
  const isSpoof = statusText.includes('spoof');

  const fetchCamera = useCallback(async () => {
    try {
      setCameraLoading(true);
      const res = await api.get('/face/camera');
      setCamera(res.data.camera);
    } catch {
      setCamera(null);
    } finally {
      setCameraLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCamera();
  }, [fetchCamera]);

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;
    const ctx = canvas.getContext('2d');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);
    if (result?.bbox && result.bbox.length === 4) {
      const [x1, y1, x2, y2] = result.bbox;
      const color = isRecognized ? '#198754' : (isSpoof ? '#dc3545' : '#fd7e14');
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(2, Math.round(img.naturalWidth / 200));
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      const label = result.matched_user_name
        ? `${result.matched_user_name} (${((result.confidence || 0) * 100).toFixed(1)}%)`
        : `Face (${((result.detection_score || 0) * 100).toFixed(1)}%)`;
      const fontSize = Math.max(13, Math.round(img.naturalWidth / 42));
      ctx.font = `600 ${fontSize}px sans-serif`;
      const tw = ctx.measureText(label).width;
      const pad = 4;
      ctx.fillStyle = color;
      ctx.fillRect(x1, y1 - fontSize - pad * 2, tw + pad * 2, fontSize + pad * 2);
      ctx.fillStyle = '#fff';
      ctx.fillText(label, x1 + pad, y1 - pad);
    }
  }, [result, isRecognized, isSpoof]);

  useEffect(() => {
    drawCanvas();
  }, [preview, result, drawCanvas]);

  useEffect(() => {
    if (!spoofDetected) {
      if (spoofResetTimerRef.current) {
        window.clearTimeout(spoofResetTimerRef.current);
        spoofResetTimerRef.current = null;
      }
      return;
    }

    spoofResetTimerRef.current = window.setTimeout(() => {
      setSpoofDetected(false);
      setResult(null);
      setPhaseText(cameraOn ? 'Camera ready' : 'Camera is off');
      spoofResetTimerRef.current = null;
    }, SPOOF_RESET_MS);

    return () => {
      if (spoofResetTimerRef.current) {
        window.clearTimeout(spoofResetTimerRef.current);
        spoofResetTimerRef.current = null;
      }
    };
  }, [spoofDetected, cameraOn]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
    setPhaseText('Camera is off');
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  useEffect(() => () => {
    if (spoofResetTimerRef.current) {
      window.clearTimeout(spoofResetTimerRef.current);
      spoofResetTimerRef.current = null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    if (streamRef.current) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await new Promise((resolve) => {
        videoRef.current.onloadedmetadata = resolve;
      });
      await videoRef.current.play();
    }
    setCameraOn(true);
    setPhaseText('Camera ready');
  }, []);

  const captureFrame = useCallback(async () => {
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas || !video.videoWidth) throw new Error('Camera not ready');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.72);
    const blob = await new Promise((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Capture failed'))), 'image/jpeg', 0.72)
    );
    return { blob, dataUrl };
  }, []);

  const submitFrame = useCallback(async (blob, index) => {
    if (!camera?.id) throw new Error('No camera device configured');
    const fd = new FormData();
    fd.append('image', blob, `frame-${index}.jpg`);
    fd.append('device_id', camera.id);
    const res = await api.post('/face/recognize', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }, [camera]);

  const handleRecognize = async () => {
    if (spoofDetected || !camera) return;
    setFaceError('');
    setFaceLoading(true);
    setResult(null);
    setCurrentFrame(0);

    try {
      if (!streamRef.current) {
        setPhaseText('Opening camera...');
        await startCamera();
      }
      setPhaseText('Warming up...');
      await sleep(WARMUP_MS);

      let lastResponse = null;
      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        const attemptResponses = [];
        const attemptStatuses = [];

        for (let frame = 1; frame <= FRAMES_PER_ATTEMPT; frame++) {
          const globalFrame = (attempt - 1) * FRAMES_PER_ATTEMPT + frame;
          setCurrentFrame(globalFrame);
          setPhaseText(`Attempt ${attempt}/${MAX_ATTEMPTS}: capturing frame ${frame}/${FRAMES_PER_ATTEMPT}...`);
          const { blob, dataUrl } = await captureFrame();
          setPreview(dataUrl);

          setPhaseText(`Attempt ${attempt}/${MAX_ATTEMPTS}: sending frame ${frame}/${FRAMES_PER_ATTEMPT}...`);
          const response = await submitFrame(blob, globalFrame);
          lastResponse = response;
          attemptResponses.push(response);
          const normalizedStatus = normalizeStatus(response.status);
          attemptStatuses.push(normalizedStatus);

          // New rule: if any single frame is spoof, stop immediately.
          if (normalizedStatus === 'spoof') {
            setResult(response);
            setSpoofDetected(true);
            setPhaseText('⚠️ Spoof detected. Retry available in 15s...');
            stopCamera();
            return;
          }

          if (!(attempt === MAX_ATTEMPTS && frame === FRAMES_PER_ATTEMPT)) {
            await sleep(FRAME_INTERVAL_MS);
          }
        }

        const hasRecognized = attemptStatuses.includes('recognized');

        if (hasRecognized) {
          const recognizedResponse =
            attemptResponses.find((r) => normalizeStatus(r.status) === 'recognized')
            || attemptResponses[attemptResponses.length - 1];
          setResult(recognizedResponse);
          setPhaseText(`✅ Recognized`);
          stopCamera();
          return;
        }

        if (!hasRecognized) {
          if (attempt < MAX_ATTEMPTS) {
            continue;
          }

          const finalResponse = attemptResponses[attemptResponses.length - 1];
          setResult({
            ...(finalResponse || {}),
            status: 'unknown',
            confidence: null,
            matched_enrollment_id: null,
            matched_user_id: null,
            matched_user_name: null,
            door_unlocked: false,
          });
          setPhaseText('No match found after 3 attempts. Final result: Unknown.');
          stopCamera();
          return;
        }
      }

      setResult({
        ...(lastResponse || {}),
        status: 'unknown',
        confidence: null,
        matched_enrollment_id: null,
        matched_user_id: null,
        matched_user_name: null,
        door_unlocked: false,
      });
      setPhaseText('No match found after 3 attempts. Final result: Unknown.');
      stopCamera();
    } catch (err) {
      setFaceError(err.response?.data?.detail || err.message || 'Recognition failed');
    } finally {
      setFaceLoading(false);
      setCurrentFrame(0);
    }
  };

  const resetFace = () => {
    if (spoofResetTimerRef.current) {
      window.clearTimeout(spoofResetTimerRef.current);
      spoofResetTimerRef.current = null;
    }
    setPreview(null);
    setResult(null);
    setFaceError('');
    setSpoofDetected(false);
    setCurrentFrame(0);
    setPhaseText(cameraOn ? 'Camera ready' : 'Camera is off');
    if (cameraOn) stopCamera();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoginError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setLoginError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const frameProgress = Math.round((currentFrame / MAX_FRAMES) * 100);

  return (
    <Container fluid className="min-vh-100 bg-light d-flex align-items-center py-4">
      <Container>
        <Row className="g-4 align-items-stretch">

          <Col lg={6} className="d-flex">
            <Card className="shadow-sm border w-100 h-100">
              <Card.Header className="bg-white border-bottom d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                  <span className="fw-semibold">🔍 Face Recognition</span>
                  {camera && <Badge bg="secondary">{camera.name}</Badge>}
                </div>
                {cameraOn
                  ? <Badge bg="danger">● REC</Badge>
                  : <Badge bg="secondary">Offline</Badge>}
              </Card.Header>

              <Card.Body className="p-3 d-flex flex-column">
                {cameraLoading ? (
                  <div className="text-center py-4 text-muted">
                    <Spinner size="sm" animation="border" className="me-2" />
                    Loading camera...
                  </div>
                ) : !camera ? (
                  <Alert variant="warning" className="mb-0">
                    No camera device is configured. Please ask admin to set one camera as face login camera.
                  </Alert>
                ) : (
                  <>
                    {faceError && (
                      <Alert variant="danger" dismissible onClose={() => setFaceError('')} className="mb-3">
                        {faceError}
                      </Alert>
                    )}

                    <div className="bg-light rounded mb-3 overflow-hidden">
                      <video
                        ref={videoRef}
                        muted
                        autoPlay
                        playsInline
                        className="w-100 d-block rounded"
                      />
                      {!cameraOn && (
                        <div className="text-center text-muted py-5">
                          <div className="fs-2 mb-1">📷</div>
                          <small>Camera offline</small>
                        </div>
                      )}
                    </div>

                    <canvas ref={captureCanvasRef} className="d-none" />

                    <div className="mb-1 d-flex justify-content-between">
                      <small className="text-muted">Frame progress</small>
                      <small className="text-muted">{currentFrame}/{MAX_FRAMES}</small>
                    </div>
                    <ProgressBar
                      now={frameProgress}
                      variant="primary"
                      className="mb-3"
                      style={{ height: '4px' }}
                    />

                    <p className="text-muted small mb-3 d-flex align-items-center gap-2">
                      {faceLoading && <Spinner size="sm" animation="border" />}
                      {phaseText}
                    </p>

                    <div className="bg-light rounded overflow-hidden mb-3 d-flex align-items-center justify-content-center" style={{ minHeight: '170px' }}>
                      {preview ? (
                        <>
                          <img ref={imgRef} src={preview} alt="preview" onLoad={drawCanvas} className="d-none" />
                          <canvas ref={canvasRef} className="w-100 d-block" />
                        </>
                      ) : (
                        <div className="text-center text-muted py-4">
                          <div className="fs-3 mb-1">🖼️</div>
                          <p className="small mb-0">Recognition preview appears here</p>
                        </div>
                      )}
                    </div>

                    {result && (
                      <div className="mb-3">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                          <small className="text-muted">Result</small>
                          <Badge bg={isRecognized ? 'success' : isSpoof ? 'danger' : 'warning'} text={isRecognized || isSpoof ? 'white' : 'dark'}>
                            {isRecognized ? '✓ Recognized' : isSpoof ? '⚠ Spoof Detected' : '? Unknown'}
                          </Badge>
                        </div>

                        {result.matched_user_name && (
                          <p className="mb-1 small">
                            <span className="text-muted">Matched: </span>
                            <span className="fw-semibold">{result.matched_user_name}</span>
                          </p>
                        )}

                        {result.confidence != null && (
                          <>
                            <ProgressBar
                              now={result.confidence * 100}
                              variant={isRecognized ? 'success' : isSpoof ? 'danger' : 'warning'}
                              className="mb-2"
                              label={`${(result.confidence * 100).toFixed(1)}%`}
                            />
                            {result.door_unlocked && (
                              <Alert variant="success" className="mb-0 py-2 text-center small">
                                🔓 Door has been unlocked!
                              </Alert>
                            )}
                          </>
                        )}
                      </div>
                    )}

                    <div className="d-grid gap-2 mt-auto">
                      <Button
                        variant="primary"
                        onClick={handleRecognize}
                        disabled={faceLoading || spoofDetected}
                      >
                        {faceLoading
                          ? <><Spinner size="sm" animation="border" className="me-2" />Recognizing...</>
                          : '🔍 Recognize'}
                      </Button>

                      <ButtonGroup>
                        <Button
                          variant="outline-secondary"
                          className="w-50"
                          onClick={cameraOn ? stopCamera : startCamera}
                          disabled={faceLoading || spoofDetected || !camera}
                        >
                          {cameraOn ? '⏹ Stop Camera' : '▶ Start Camera'}
                        </Button>
                        <Button variant="outline-secondary" className="w-50" onClick={resetFace}>
                          ↺ Reset
                        </Button>
                      </ButtonGroup>
                    </div>
                  </>
                )}
              </Card.Body>
            </Card>
          </Col>

          <Col lg={6} className="d-flex">
            <div className="card border-0 shadow p-4 p-md-5 w-100 d-flex justify-content-center">

              <div className="text-center mb-4">
                <div style={{ fontSize: '2.5rem' }}>🏠</div>
                <h4 className="fw-bold mt-2 mb-1">Welcome Back</h4>
                <p className="text-muted small mb-0">Sign in to your YoloHome account</p>
              </div>

              {loginError && (
                <div className="alert alert-danger py-2 small" role="alert">
                  {loginError}
                </div>
              )}

              <form onSubmit={handleSubmit}>

                <div className="mb-3">
                  <label htmlFor="login-username" className="form-label small fw-semibold">
                    Username
                  </label>
                  <input
                    id="login-username"
                    type="text"
                    className="form-control"
                    placeholder="Enter your username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    autoFocus
                  />
                </div>

                <div className="mb-4">
                  <label htmlFor="login-password" className="form-label small fw-semibold">
                    Password
                  </label>
                  <div className="input-group">
                    <input
                      id="login-password"
                      type={showPassword ? 'text' : 'password'}
                      className="form-control"
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="btn btn-outline-secondary"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                    >
                      {showPassword ? <HiEyeOff size={16} /> : <HiEye size={16} />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn btn-primary w-100 mb-3"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status" />
                      Signing in...
                    </>
                  ) : 'Sign In'}
                </button>

                <p className="text-center small text-muted mb-0">
                  Don't have an account?{' '}
                  <Link to="/register" className="text-primary fw-semibold text-decoration-none">
                    Register
                  </Link>
                </p>

              </form>
            </div>
          </Col>

        </Row>
      </Container>
    </Container>
  );
}