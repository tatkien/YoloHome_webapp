import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Container, Row, Col, Card, Button, Form, Alert, Badge } from 'react-bootstrap';
import { Mic, MicOff, Settings, MessageSquare, Terminal, Power } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

// Các hằng số điều khiển nhịp độ hệ thống
const CHUNK_MS = 2500;
const RECONNECT_WAIT_MS = 1500; // Khoảng nghỉ để tái kết nối ổn định
const PROCESSING_TIMEOUT_MS = 2000; 
const PREFERRED_MIME = "audio/webm;codecs=opus";

export default function VoiceControlPage() {
  const { token } = useAuth(); // Lấy yh_token từ AuthContext

  const [devices, setDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [status, setStatus] = useState("idle"); 
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState("");
  const [audioLevel, setAudioLevel] = useState(0);

  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);
  
  const stoppingRef = useRef(false);
  const processingRef = useRef(false);
  const chunkStopTimerRef = useRef(null);
  const chunkStartTimerRef = useRef(null);
  const processingTimeoutRef = useRef(null);
  const startChunkCaptureRef = useRef(() => {});

  // URL WebSocket chuẩn của YoloHome
  const buildWebSocketUrl = (authToken) => {
    const base = process.env.REACT_APP_API_URL || "http://localhost:8000";
    let u = new URL(base);
    const wsProto = u.protocol === "https:" ? "wss" : "ws";
    return `${wsProto}://${u.host}/api/v1/ws?token=${encodeURIComponent(authToken)}`;
  };

  const blobToBase64 = (blob) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = reader.result;
        resolve(result.indexOf(",") >= 0 ? result.slice(result.indexOf(",") + 1) : result);
      };
      reader.onerror = () => reject(new Error("Audio processing failed"));
      reader.readAsDataURL(blob);
    });
  };

  // Chỉ tính toán âm lượng khi đang thực sự chạy
  const monitorAudioLevel = useCallback(() => {
    if (!analyserRef.current || stoppingRef.current) return;
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
    setAudioLevel(sum / dataArray.length);
    animationFrameRef.current = requestAnimationFrame(monitorAudioLevel);
  }, []);

  const cleanup = useCallback(() => {
    if (chunkStopTimerRef.current) clearTimeout(chunkStopTimerRef.current);
    if (chunkStartTimerRef.current) clearTimeout(chunkStartTimerRef.current);
    if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    setAudioLevel(0);
    try { if (recorderRef.current?.state !== "inactive") recorderRef.current.stop(); } catch {}
    recorderRef.current = null;
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null; }
    if (wsRef.current) {
      try { if (wsRef.current.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: "voice_stop" })); } catch {}
      wsRef.current.close(); wsRef.current = null;
    }
    processingRef.current = false;
  }, []);

  const stopDetect = useCallback(() => {
    stoppingRef.current = true;
    setStatus("idle");
    cleanup();
  }, [cleanup]);

  const refreshDevices = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop());
      const all = await navigator.mediaDevices.enumerateDevices();
      const mics = all.filter(d => d.kind === "audioinput");
      setDevices(mics);
      const saved = localStorage.getItem("yh_selected_audio_device_id");
      setSelectedDeviceId(saved && mics.find(m => m.deviceId === saved) ? saved : mics[0]?.deviceId || "");
    } catch { setError("Microphone access denied."); }
  }, []);

  useEffect(() => {
    refreshDevices();
    return () => { stoppingRef.current = true; cleanup(); };
  }, [refreshDevices, cleanup]);

  const startDetect = useCallback(async () => {
    if (!token || !selectedDeviceId) return setError("Authentication failed or Mic not selected.");
    stoppingRef.current = false; setError(""); setTranscript(""); setStatus("connecting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { deviceId: { exact: selectedDeviceId }, channelCount: 1, sampleRate: 16000 }
      });
      streamRef.current = stream;

      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContext();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      audioCtxRef.current = audioCtx; analyserRef.current = analyser;
      monitorAudioLevel();

      const ws = new WebSocket(buildWebSocketUrl(token));
      wsRef.current = ws;

      const scheduleNextChunk = (delay = 0) => {
        if (stoppingRef.current || chunkStartTimerRef.current) return;
        chunkStartTimerRef.current = setTimeout(() => {
          chunkStartTimerRef.current = null;
          startChunkCaptureRef.current();
        }, delay);
      };

      startChunkCaptureRef.current = () => {
        if (stoppingRef.current || processingRef.current || wsRef.current?.readyState !== WebSocket.OPEN) return;
        let mime = MediaRecorder.isTypeSupported(PREFERRED_MIME) ? PREFERRED_MIME : "audio/webm";
        let recorder = new MediaRecorder(streamRef.current, { mimeType: mime });
        recorderRef.current = recorder;
        recorder.ondataavailable = async (e) => {
          if (stoppingRef.current || !e.data.size || wsRef.current?.readyState !== WebSocket.OPEN) return scheduleNextChunk();
          try {
            processingRef.current = true; setStatus("processing");
            const base64 = await blobToBase64(e.data);
            if (!stoppingRef.current) wsRef.current.send(JSON.stringify({ type: "voice_chunk", mime_type: mime, audio_base64: base64 }));
          } catch { processingRef.current = false; scheduleNextChunk(); }
        };
        recorder.start();
        chunkStopTimerRef.current = setTimeout(() => {
          chunkStopTimerRef.current = null;
          try { if (recorder.state !== "inactive") recorder.stop(); } catch {}
        }, CHUNK_MS);
      };

      ws.onmessage = (event) => {
        if (stoppingRef.current) return;
        const payload = JSON.parse(event.data);
        if (payload.event === "voice_status") {
          const s = payload.data.status; setStatus(s);
          processingRef.current = s === "processing";
          if (s !== "processing") scheduleNextChunk();
        } else if (payload.event === "voice_transcript") {
          setTranscript(payload.data.text);
        } else if (payload.event === "voice_error") {
          setError(payload.data.message); processingRef.current = false; scheduleNextChunk();
        }
      };

      ws.onopen = () => { if (!stoppingRef.current) ws.send(JSON.stringify({ type: "voice_start" })); };
      
      ws.onclose = () => { 
        if (!stoppingRef.current) { 
          setStatus("idle"); 
          cleanup(); 
          // 🔥 SỬ DỤNG RECONNECT_WAIT_MS TẠI ĐÂY
          setTimeout(() => {
            if (!stoppingRef.current) startDetect();
          }, RECONNECT_WAIT_MS);
        } 
      };
    } catch { setStatus("idle"); cleanup(); setError("Connection failed."); }
  }, [token, selectedDeviceId, cleanup, monitorAudioLevel]);

  // --- UI LOGIC ---
  const isRunning = status !== "idle";
  const isListening = status === "listening_command";
  
  // Hiệu ứng sóng âm chỉ kích hoạt khi âm thanh > ngưỡng 5
  const hasSound = audioLevel > 5;
  const dynamicScale = isRunning && hasSound ? 1 + (audioLevel / 160) : 1;

  // Quyết định màu sắc nút Mic theo trạng thái
  const getMicVariant = () => {
    if (status === "idle") return "outline-secondary";
    if (status === "waiting_wake_phrase") return "primary"; // Xanh biển khi Standby
    if (status === "listening_command") return "success";  // Xanh lá khi đã Wake Word
    return "secondary";
  };

  return (
    <Container className="py-4">
      {/* HEADER ĐỒNG BỘ TUYỆT ĐỐI VỚI DEVICES PAGE (h2, text-muted) */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="fw-bold mb-1">Voice Control</h2>
          <p className="text-muted mb-0">Control your smart home with voice assistant</p>
        </div>
        <Badge bg={isRunning ? (isListening ? "success" : "primary") : "secondary"} className="px-3 py-2 fw-normal rounded-pill">
          {status.toUpperCase().replace(/_/g, ' ')}
        </Badge>
      </div>

      {error && <Alert variant="danger" className="rounded-3 border-0 shadow-sm" dismissible onClose={() => setError("")}>{error}</Alert>}

      <Row className="g-4">
        {/* CỘT TRÁI: ĐIỀU KHIỂN (Cân bằng 6-6) */}
        <Col md={6}>
          <Card className="h-100 shadow-sm border-0">
            <Card.Body className="d-flex flex-column align-items-center justify-content-center text-center p-5">
              
              <div className="position-relative mb-4 d-flex justify-content-center align-items-center" style={{ width: '160px', height: '160px' }}>
                {/* SÓNG ÂM: Chỉ hiện khi hasSound = true */}
                {isRunning && hasSound && (
                  <div 
                    className="position-absolute rounded-circle"
                    style={{
                      width: '110px', height: '110px',
                      backgroundColor: isListening ? 'rgba(25, 135, 84, 0.1)' : 'rgba(13, 110, 253, 0.1)',
                      transform: `scale(${dynamicScale})`,
                      transition: 'transform 0.1s linear',
                      zIndex: 1
                    }}
                  />
                )}
                
                <Button 
                  variant={getMicVariant()}
                  className={`rounded-circle d-flex justify-content-center align-items-center ${!isRunning ? 'border-2' : 'border-0'}`}
                  onClick={isRunning ? stopDetect : startDetect}
                  style={{ width: '90px', height: '90px', zIndex: 2, transition: 'all 0.2s ease' }}
                >
                  {isRunning ? <Mic size={36} className="text-white" /> : <MicOff size={36} className="text-muted" />}
                </Button>
              </div>

              {/* Typography đồng bộ h5 */}
              <h5 className="fw-bold mb-2">
                {isRunning ? (isListening ? "Listening..." : "Waiting for Wake Word") : "Voice Detect Off"}
              </h5>
              <p className="text-muted small px-3">
                {!isRunning ? "Tap icon to connect" : (isListening ? "Say your command now" : 'Say "Hey Yolo" to activate')}
              </p>

              <Form.Group className="w-100 text-start mt-4 bg-light p-3 rounded-3 border">
                <Form.Label className="small fw-bold text-muted mb-2 d-flex align-items-center">
                  <Settings size={14} className="me-2" /> Microphone Source
                </Form.Label>
                <Form.Select 
                  size="sm"
                  value={selectedDeviceId} 
                  onChange={(e) => { setSelectedDeviceId(e.target.value); localStorage.setItem("yh_selected_audio_device_id", e.target.value); }}
                  className="border-0 bg-white shadow-none"
                  disabled={isRunning}
                >
                  {devices.map(d => <option key={d.deviceId} value={d.deviceId}>{d.label || "Microphone"}</option>)}
                </Form.Select>
              </Form.Group>
            </Card.Body>
          </Card>
        </Col>

        {/* CỘT PHẢI: TRANSCRIPT & GUIDE (Cân bằng 6-6) */}
        <Col md={6}>
          <div className="d-flex flex-column h-100 gap-4">
            
            <Card className="shadow-sm border-0 flex-grow-1">
              <Card.Body className="p-4 d-flex flex-column">
                <div className="d-flex align-items-center mb-3">
                  <MessageSquare size={18} className="text-primary me-2" />
                  <h5 className="fw-bold mb-0">Transcription</h5>
                </div>
                
                <div className="bg-light rounded-3 p-4 text-center border flex-grow-1 d-flex align-items-center justify-content-center">
                  {transcript ? (
                    <h5 className="fw-normal text-dark mb-0 fst-italic">"{transcript}"</h5>
                  ) : (
                    <span className="text-muted small">Voice output will appear here...</span>
                  )}
                </div>
              </Card.Body>
            </Card>

            <Card className="shadow-sm border-0">
              <Card.Body className="p-4">
                <div className="d-flex align-items-center mb-3">
                  <Terminal size={18} className="text-primary me-2" />
                  <h5 className="fw-bold mb-0">Guide</h5>
                </div>

                <Row className="g-3">
                  <Col xs={6}>
                    <div className="p-2">
                      <div className="fw-bold text-muted text-uppercase mb-2" style={{ fontSize: '0.75rem' }}>Keywords</div>
                      <div className="small mb-1"><Badge bg="light" text="dark" className="border me-2">Wake</Badge> "Hey Yolo"</div>
                      <div className="small"><Badge bg="light" text="dark" className="border me-2">Exit</Badge> "Goodbye"</div>
                    </div>
                  </Col>
                  <Col xs={6}>
                    <div className="p-2 border-start">
                      <div className="fw-bold text-muted text-uppercase mb-2" style={{ fontSize: '0.75rem' }}>Actions</div>
                      <div className="small mb-1"><Power size={12} className="text-success me-1" /> Light on/off</div>
                      <div className="small"><Power size={12} className="text-info me-1" /> Fan on/off</div>
                    </div>
                  </Col>
                </Row>
              </Card.Body>
            </Card>

          </div>
        </Col>
      </Row>
    </Container>
  );
}
