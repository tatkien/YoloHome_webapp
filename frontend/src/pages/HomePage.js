import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Container,
  Row,
  Col,
  Card,
  Button,
  Alert,
  Spinner,
  Badge,
  Form,
  ButtonGroup,
} from "react-bootstrap";
import { useAuth } from "../contexts/AuthContext";
import api from "../services/api";
import VoiceDetectCard from "../components/VoiceDetectCard";

const MAX_FRAMES = 3;
const WARMUP_MS = 1000;
const FRAME_INTERVAL_MS = 180;

const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

const DEVICE_ICONS = {
  fan: "🌀",
  light: "💡",
  camera: "📷",
  lock: "🔒",
  temp_sensor: "🌡️",
  humidity_sensor: "💧",
};

const DEVICE_UNITS = {
  temp_sensor: "°C",
  humidity_sensor: "%",
  fan: " speed",
};

export default function HomePage() {
  const { user, isAdmin, token } = useAuth();

  // --- Device monitoring state ---
  const [devices, setDevices] = useState([]);
  const [devicesLoading, setDevicesLoading] = useState(true);

  // --- Camera state ---
  const [camera, setCamera] = useState(null);
  const [cameraLoading, setCameraLoading] = useState(true);

  // --- Recognition state ---
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [phaseText, setPhaseText] = useState("Camera is off");
  const [currentFrame, setCurrentFrame] = useState(0);
  const [spoofDetected, setSpoofDetected] = useState(false);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  // --- Fetch devices ---
  const fetchDevices = useCallback(async () => {
    try {
      setDevicesLoading(true);
      const res = await api.get("/devices/");
      setDevices(res.data);
    } catch {
      // silent
    } finally {
      setDevicesLoading(false);
    }
  }, []);

  // --- Fetch camera device ---
  const fetchCamera = useCallback(async () => {
    try {
      setCameraLoading(true);
      const res = await api.get("/face/camera");
      setCamera(res.data.camera);
    } catch {
      setCamera(null);
    } finally {
      setCameraLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDevices();
    fetchCamera();
  }, [fetchDevices, fetchCamera]);

  useEffect(() => {
    const handleWsMessage = (e) => {
      const payload = e.detail;
      if (payload.event === "sensor_update") {
        setDevices((prev) =>
          prev.map((d) => {
            if (
              d.hardware_id === payload.hardware_id &&
              payload.data[d.pin] !== undefined
            ) {
              return { ...d, value: payload.data[d.pin] };
            }
            return d;
          }),
        );
      } else if (payload.event === "device_update") {
        setDevices((prev) =>
          prev.map((d) => {
            if (d.id === payload.device_id) {
              return {
                ...d,
                is_on: payload.data.is_on,
                value: payload.data.value,
              };
            }
            return d;
          }),
        );
      }
    };
    window.addEventListener("yolohome:ws", handleWsMessage);
    return () => window.removeEventListener("yolohome:ws", handleWsMessage);
  }, []);

  const handleDeviceCommand = async (deviceId, isOn, value) => {
    // Optimistic UI update
    setDevices((prev) =>
      prev.map((d) => (d.id === deviceId ? { ...d, is_on: isOn, value } : d)),
    );
    try {
      await api.post(`/devices/${deviceId}/command`, {
        is_on: isOn,
        value: value,
      });
    } catch (err) {
      console.error("Failed to send command", err);
      // Revert state by fetching truth from server
      fetchDevices();
    }
  };

  // --- Recognition result helpers ---
  const statusText = (result?.status || "").toLowerCase();
  const isRecognized = statusText === "recognized";
  const isSpoof = statusText.includes("spoof");

  // --- Canvas drawing ---
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;
    const ctx = canvas.getContext("2d");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);
    if (result?.bbox && result.bbox.length === 4) {
      const [x1, y1, x2, y2] = result.bbox;
      const color = isRecognized ? "#34d399" : isSpoof ? "#f87171" : "#fbbf24";
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(2, Math.round(img.naturalWidth / 200));
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      const label = result.matched_user_name
        ? `${result.matched_user_name} (${((result.confidence || 0) * 100).toFixed(1)}%)`
        : `Face (${((result.detection_score || 0) * 100).toFixed(1)}%)`;
      const fontSize = Math.max(14, Math.round(img.naturalWidth / 40));
      ctx.font = `bold ${fontSize}px sans-serif`;
      const textWidth = ctx.measureText(label).width;
      const pad = 4;
      ctx.fillStyle = color;
      ctx.fillRect(
        x1,
        y1 - fontSize - pad * 2,
        textWidth + pad * 2,
        fontSize + pad * 2,
      );
      ctx.fillStyle = "white";
      ctx.fillText(label, x1 + pad, y1 - pad);
    }
  }, [result, isRecognized, isSpoof]);

  useEffect(() => {
    drawCanvas();
  }, [preview, result, drawCanvas]);

  // --- Camera controls ---
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
    setPhaseText("Camera is off");
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const startCamera = useCallback(async () => {
    if (streamRef.current) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: "user",
      },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await new Promise((r) => {
        videoRef.current.onloadedmetadata = r;
      });
      await videoRef.current.play();
    }
    setCameraOn(true);
    setPhaseText("Camera ready");
  }, []);

  const captureFrame = useCallback(async () => {
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas || !video.videoWidth)
      throw new Error("Camera not ready");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.72);
    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error("Capture failed"))),
        "image/jpeg",
        0.72,
      );
    });
    return { blob, dataUrl };
  }, []);

  const submitFrame = useCallback(
    async (blob, index) => {
      const fd = new FormData();
      fd.append("image", blob, `frame-${index}.jpg`);
      fd.append("device_id", camera.id);
      const res = await api.post("/face/recognize", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    [camera],
  );

  // --- Main recognition flow ---
  const handleRecognize = async (e) => {
    e.preventDefault();
    if (spoofDetected || !camera) return;
    setError("");
    setLoading(true);
    setResult(null);
    setCurrentFrame(0);

    try {
      if (!streamRef.current) {
        setPhaseText("Opening camera...");
        await startCamera();
      }
      setPhaseText(`Warming up camera...`);
      await sleep(WARMUP_MS);

      let lastResponse = null;
      for (let i = 1; i <= MAX_FRAMES; i++) {
        setCurrentFrame(i);
        setPhaseText(`Capturing frame ${i}/${MAX_FRAMES}...`);
        const { blob, dataUrl } = await captureFrame();
        setPreview(dataUrl);

        setPhaseText(`Sending frame ${i}/${MAX_FRAMES}...`);
        const response = await submitFrame(blob, i);
        lastResponse = response;

        if (response.status === "recognized") {
          setResult(response);
          setPhaseText(
            `✅ Recognized! ${response.door_unlocked ? "🔓 Door unlocked!" : ""}`,
          );
          stopCamera();
          setLoading(false);
          return;
        }

        // Spoof detected → stop immediately
        if (response.status?.toLowerCase().includes("spoof")) {
          setResult(response);
          setSpoofDetected(true);
          setPhaseText("⚠️ Spoof detected — camera stopped.");
          stopCamera();
          setLoading(false);
          return;
        }

        if (i < MAX_FRAMES) await sleep(FRAME_INTERVAL_MS);
      }

      // All frames processed, no match
      setResult(lastResponse);
      setPhaseText("No match found.");
    } catch (err) {
      setError(err.response?.data?.detail || "Recognition failed");
    } finally {
      setLoading(false);
      setCurrentFrame(0);
    }
  };

  const reset = () => {
    setPreview(null);
    setResult(null);
    setError("");
    setSpoofDetected(false);
    setPhaseText(cameraOn ? "Camera ready" : "Camera is off");
    setCurrentFrame(0);
    if (cameraOn) stopCamera();
  };

  // --- Render helpers ---
  const renderDeviceValue = (d) => {
    const unit = DEVICE_UNITS[d.type] || "";
    if (d.type === "lock") return d.is_on ? "🔓 Open" : "🔒 Locked";
    if (d.type === "light") return d.is_on ? "💡 On" : "⚫ Off";
    if (d.type === "camera") return d.is_on ? "🟢 Active" : "⚫ Off";
    if (d.type === "fan")
      return d.is_on ? `Speed ${Math.round(d.value)}` : "Off";
    return `${d.value}${unit}`;
  };

  return (
    <Container className="py-4 fade-in">
      {/* Welcome */}
      <Row className="justify-content-center text-center mb-4">
        <Col md={8}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.25rem" }}>🏠</div>
          <h1
            style={{
              fontWeight: 700,
              fontSize: "2rem",
              marginBottom: "0.25rem",
            }}
          >
            Welcome,{" "}
            <span
              style={{
                background: "var(--gradient-primary)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              {user?.username}
            </span>
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "1rem" }}>
            YoloHome Smart Dashboard
          </p>
        </Col>
      </Row>

      {error && (
        <Alert variant="danger" dismissible onClose={() => setError("")}>
          {error}
        </Alert>
      )}

      {/* Face Recognition Board */}
      {cameraLoading ? (
        <div className="text-center py-3">
          <Spinner size="sm" animation="border" />
        </div>
      ) : camera ? (
        <Row className="g-4 mb-4">
          <Col lg={6}>
            <div className="yh-card p-4">
              <div className="d-flex align-items-center justify-content-between mb-3">
                <h5 style={{ fontWeight: 700, margin: 0 }}>
                  🔍 Face Recognition
                </h5>
                <Badge bg="info" style={{ fontSize: "0.7rem" }}>
                  {camera.name}
                </Badge>
              </div>
              <form onSubmit={handleRecognize}>
                <div className="camera-preview-zone mb-3">
                  <video
                    ref={videoRef}
                    muted
                    autoPlay
                    playsInline
                    style={{
                      width: "100%",
                      maxHeight: "280px",
                      borderRadius: "var(--radius-sm)",
                      background: "var(--bg-input)",
                      objectFit: "cover",
                    }}
                  />
                  <canvas ref={captureCanvasRef} style={{ display: "none" }} />
                </div>

                <div
                  style={{
                    marginBottom: "0.5rem",
                    color: "var(--text-secondary)",
                    fontSize: "0.9rem",
                  }}
                >
                  {phaseText}
                  {currentFrame > 0
                    ? ` (frame ${currentFrame}/${MAX_FRAMES})`
                    : ""}
                </div>

                <div className="d-flex gap-2">
                  <Button
                    type="submit"
                    disabled={loading || spoofDetected}
                    className="flex-grow-1"
                  >
                    {loading ? (
                      <>
                        <Spinner size="sm" animation="border" /> Recognizing...
                      </>
                    ) : (
                      "🔍 Recognize"
                    )}
                  </Button>
                  <Button
                    variant="outline-light"
                    onClick={cameraOn ? stopCamera : startCamera}
                    type="button"
                    disabled={loading || spoofDetected}
                  >
                    {cameraOn ? "Stop" : "Start"}
                  </Button>
                  <Button variant="outline-light" onClick={reset} type="button">
                    Reset
                  </Button>
                </div>
              </form>
            </div>
          </Col>

          <Col lg={6}>
            {preview && (
              <div className="yh-card p-4 mb-3">
                <h6
                  style={{
                    fontWeight: 600,
                    marginBottom: "0.75rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  Preview
                </h6>
                <img
                  ref={imgRef}
                  src={preview}
                  alt="preview"
                  onLoad={drawCanvas}
                  style={{ display: "none" }}
                />
                <canvas
                  ref={canvasRef}
                  style={{
                    width: "100%",
                    maxHeight: "300px",
                    objectFit: "contain",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-input)",
                  }}
                />
              </div>
            )}
            {result && (
              <div
                className={`result-card ${isRecognized ? "recognized" : isSpoof ? "spoof" : "unknown"}`}
              >
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <h6 style={{ fontWeight: 700, margin: 0 }}>Result</h6>
                  <span
                    className={
                      isRecognized
                        ? "badge-recognized"
                        : isSpoof
                          ? "badge-spoof"
                          : "badge-unknown"
                    }
                  >
                    {isRecognized
                      ? "✓ Recognized"
                      : isSpoof
                        ? "⚠ Spoof"
                        : "? Unknown"}
                  </span>
                </div>
                <Row className="g-2">
                  {result.matched_user_name && (
                    <Col xs={6}>
                      <div className="stat-label">Matched</div>
                      <div
                        style={{
                          fontWeight: 700,
                          color: "var(--accent-green)",
                        }}
                      >
                        {result.matched_user_name}
                      </div>
                    </Col>
                  )}
                  {result.confidence != null && (
                    <Col xs={6}>
                      <div className="stat-label">Confidence</div>
                      <div
                        className="stat-value"
                        style={{ fontSize: "1.2rem" }}
                      >
                        {(result.confidence * 100).toFixed(1)}%
                      </div>
                    </Col>
                  )}
                  {result.door_unlocked && (
                    <Col xs={12}>
                      <Alert
                        variant="success"
                        className="mt-2 mb-0 py-2 text-center"
                        style={{ fontSize: "0.9rem" }}
                      >
                        🔓 Door has been unlocked!
                      </Alert>
                    </Col>
                  )}
                </Row>
              </div>
            )}
            {!preview && !result && (
              <div
                className="yh-card p-4 d-flex align-items-center justify-content-center"
                style={{ minHeight: "200px" }}
              >
                <div
                  className="text-center"
                  style={{ color: "var(--text-muted)" }}
                >
                  <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>
                    🖼️
                  </div>
                  <p>Click "Recognize" to start face recognition</p>
                </div>
              </div>
            )}
          </Col>
        </Row>
      ) : null}

      {/* Voice Detection */}
      <Row className="g-4 mb-2">
        <Col lg={6}>
          <VoiceDetectCard token={token} />
        </Col>
      </Row>

      {/* Device Monitoring Grid */}
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h4 style={{ fontWeight: 700, margin: 0 }}>📡 Device Monitor</h4>
        <small style={{ color: "var(--text-muted)" }}>
          {devices.length} device{devices.length !== 1 ? "s" : ""}
        </small>
      </div>

      {devicesLoading ? (
        <div className="text-center py-4">
          <Spinner animation="border" />
        </div>
      ) : devices.length === 0 ? (
        <div
          className="yh-card p-4 text-center"
          style={{ color: "var(--text-muted)" }}
        >
          <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>📡</div>
          <p>
            No devices configured yet.
            {isAdmin
              ? " Go to Devices page to add hardware."
              : " Ask admin to set up devices."}
          </p>
        </div>
      ) : (
        <Row className="g-3">
          {devices.map((d) => (
            <Col xs={6} md={4} lg={3} key={d.id}>
              <Card className="device-monitor-card h-100">
                <Card.Body className="p-3 text-center">
                  <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
                    {DEVICE_ICONS[d.type] || "📦"}
                  </div>
                  <Card.Title
                    style={{ fontSize: "0.9rem", marginBottom: "0.25rem" }}
                  >
                    {d.name}
                  </Card.Title>
                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginBottom: "0.5rem",
                    }}
                  >
                    {d.room || "No room"}
                  </div>

                  {d.type === "light" && (
                    <div className="d-flex justify-content-center align-items-center mt-3">
                      <Form.Check
                        type="switch"
                        id={`switch-${d.id}`}
                        checked={d.is_on}
                        onChange={(e) =>
                          handleDeviceCommand(
                            d.id,
                            e.target.checked,
                            e.target.checked ? 1 : 0,
                          )
                        }
                      />
                      <span
                        className="ms-2 fw-bold"
                        style={{
                          color: d.is_on
                            ? "var(--accent-green)"
                            : "var(--text-muted)",
                        }}
                      >
                        {d.is_on ? "ON" : "OFF"}
                      </span>
                    </div>
                  )}

                  {d.type === "fan" && (
                    <div className="mt-3">
                      <div className="d-flex justify-content-center align-items-center mb-2">
                        <Form.Check
                          type="switch"
                          id={`switch-${d.id}`}
                          checked={d.is_on}
                          onChange={(e) => {
                            const willBeOn = e.target.checked;
                            handleDeviceCommand(
                              d.id,
                              willBeOn,
                              willBeOn ? (d.value > 0 ? d.value : 1) : 0,
                            );
                          }}
                        />
                        <span
                          className="ms-2 fw-bold"
                          style={{
                            color: d.is_on
                              ? "var(--accent-green)"
                              : "var(--text-muted)",
                          }}
                        >
                          {d.is_on ? "ON" : "OFF"}
                        </span>
                      </div>
                      {d.is_on && (
                        <ButtonGroup size="sm" className="w-100 mt-2">
                          {[1, 2, 3].map((lvl) => (
                            <Button
                              key={lvl}
                              variant={
                                d.value === lvl ? "primary" : "outline-primary"
                              }
                              onClick={() =>
                                handleDeviceCommand(d.id, true, lvl)
                              }
                            >
                              Speed {lvl}
                            </Button>
                          ))}
                        </ButtonGroup>
                      )}
                    </div>
                  )}

                  {!["light", "fan"].includes(d.type) && (
                    <div
                      className="mt-3"
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        color:
                          d.is_on || d.value > 0
                            ? "var(--accent-green)"
                            : "var(--text-muted)",
                      }}
                    >
                      {renderDeviceValue(d)}
                    </div>
                  )}
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </Container>
  );
}
