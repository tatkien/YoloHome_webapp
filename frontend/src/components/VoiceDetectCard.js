import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Alert, Badge, Button, Card, Form } from "react-bootstrap";

const CHUNK_MS = 2500;
const RECONNECT_WAIT_MS = 1500;
const PROCESSING_TIMEOUT_MS = 2000;
const PREFERRED_MIME = "audio/webm;codecs=opus";

function buildWebSocketUrl(token) {
  const base = process.env.REACT_APP_API_URL || "http://localhost:8000";
  let u;
  try {
    u = new URL(base);
  } catch {
    return null;
  }
  const wsProto = u.protocol === "https:" ? "wss" : "ws";
  return `${wsProto}://${u.host}/api/v1/ws?token=${encodeURIComponent(token)}`;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Invalid blob conversion result"));
        return;
      }
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : result);
    };
    reader.onerror = () => reject(new Error("Failed to read audio chunk"));
    reader.readAsDataURL(blob);
  });
}

export default function VoiceDetectCard({ token }) {
  const [devices, setDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [status, setStatus] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [intent, setIntent] = useState("");
  const [voiceLog, setVoiceLog] = useState("-");
  const [error, setError] = useState("");

  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const stoppingRef = useRef(false);
  const processingRef = useRef(false);
  const chunkStopTimerRef = useRef(null);
  const chunkStartTimerRef = useRef(null);
  const processingTimeoutRef = useRef(null);
  const startChunkCaptureRef = useRef(() => {});
  const statusRef = useRef("idle");
  const lastReadyStatusRef = useRef("waiting_wake_phrase");

  const statusBadge = useMemo(() => {
    if (status === "recording") return <Badge bg="success">Recording</Badge>;
    if (status === "processing")
      return <Badge bg="primary">Processing...</Badge>;
    if (status === "waiting_wake_phrase")
      return <Badge bg="warning">Waiting "hey yolo"</Badge>;
    if (status === "listening_command")
      return <Badge bg="info">Listening Command</Badge>;
    if (status === "connecting")
      return <Badge bg="secondary">Connecting...</Badge>;
    return <Badge bg="dark">Idle</Badge>;
  }, [status]);

  const cleanup = useCallback(() => {
    if (chunkStopTimerRef.current) {
      clearTimeout(chunkStopTimerRef.current);
      chunkStopTimerRef.current = null;
    }
    if (chunkStartTimerRef.current) {
      clearTimeout(chunkStartTimerRef.current);
      chunkStartTimerRef.current = null;
    }
    if (processingTimeoutRef.current) {
      clearTimeout(processingTimeoutRef.current);
      processingTimeoutRef.current = null;
    }

    try {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    } catch {
      // ignore
    }
    recorderRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "voice_stop" }));
        }
      } catch {
        // ignore
      }
      try {
        wsRef.current.close();
      } catch {
        // ignore
      }
      wsRef.current = null;
    }
    processingRef.current = false;
  }, []);

  const refreshDevices = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });
      stream.getTracks().forEach((t) => t.stop());

      const all = await navigator.mediaDevices.enumerateDevices();
      const mics = all.filter((d) => d.kind === "audioinput");
      setDevices(mics);

      const saved = localStorage.getItem("yh_selected_audio_device_id");
      const initial =
        saved && mics.find((m) => m.deviceId === saved)
          ? saved
          : mics[0]?.deviceId || "";
      setSelectedDeviceId(initial);
      if (initial) {
        localStorage.setItem("yh_selected_audio_device_id", initial);
      }
    } catch {
      setError(
        "Cannot access microphone devices. Please grant microphone permission.",
      );
    }
  }, []);

  useEffect(() => {
    statusRef.current = status;
    if (status === "waiting_wake_phrase" || status === "listening_command") {
      lastReadyStatusRef.current = status;
    }
  }, [status]);

  useEffect(() => {
    refreshDevices();
    return () => {
      stoppingRef.current = true;
      cleanup();
    };
  }, [refreshDevices, cleanup]);

  const stopDetect = useCallback(() => {
    stoppingRef.current = true;
    setStatus("idle");
    cleanup();
  }, [cleanup]);

  const startDetect = useCallback(async () => {
    if (!token) {
      setError("You must be logged in to use voice detection.");
      return;
    }
    if (!selectedDeviceId) {
      setError("Please choose a microphone first.");
      return;
    }

    stoppingRef.current = false;
    setError("");
    setIntent("");
    setTranscript("");
    setVoiceLog("-");
    setStatus("connecting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: { exact: selectedDeviceId },
          channelCount: 1,
          sampleRate: 16000,
        },
        video: false,
      });
      streamRef.current = stream;

      const url = buildWebSocketUrl(token);
      if (!url) {
        throw new Error("Invalid backend URL for websocket");
      }

      const ws = new WebSocket(url);
      wsRef.current = ws;

      const scheduleNextChunkCapture = (delayMs = 0) => {
        if (stoppingRef.current) return;
        if (chunkStartTimerRef.current) return;
        chunkStartTimerRef.current = setTimeout(() => {
          chunkStartTimerRef.current = null;
          startChunkCaptureRef.current();
        }, delayMs);
      };

      const armProcessingTimeout = () => {
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }
        processingTimeoutRef.current = setTimeout(() => {
          processingTimeoutRef.current = null;
          if (stoppingRef.current) return;
          if (!processingRef.current) return;
          processingRef.current = false;
          setVoiceLog("Xu ly qua 2 giay. Bo qua chunk va tiep tuc nghe.");
          setError("Voice processing timeout (2s). Listening again...");
          setStatus((prev) => {
            if (prev !== "processing") return prev;
            return lastReadyStatusRef.current;
          });
          scheduleNextChunkCapture();
        }, PROCESSING_TIMEOUT_MS);
      };

      startChunkCaptureRef.current = () => {
        if (stoppingRef.current) return;
        if (processingRef.current) return;
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)
          return;
        if (!streamRef.current) return;
        if (recorderRef.current && recorderRef.current.state !== "inactive")
          return;

        const mimeType = MediaRecorder.isTypeSupported(PREFERRED_MIME)
          ? PREFERRED_MIME
          : "audio/webm";

        let recorder;
        try {
          recorder = new MediaRecorder(streamRef.current, { mimeType });
        } catch {
          setError("Unable to capture microphone audio.");
          scheduleNextChunkCapture(CHUNK_MS);
          return;
        }

        recorderRef.current = recorder;

        recorder.ondataavailable = async (e) => {
          if (!e.data || e.data.size === 0) {
            scheduleNextChunkCapture();
            return;
          }
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            scheduleNextChunkCapture();
            return;
          }

          try {
            processingRef.current = true;
            if (
              statusRef.current === "waiting_wake_phrase" ||
              statusRef.current === "listening_command"
            ) {
              lastReadyStatusRef.current = statusRef.current;
            }
            setStatus("processing");
            setVoiceLog("Da nhan duoc voice, dang xu ly...");
            armProcessingTimeout();
            const base64 = await blobToBase64(e.data);
            wsRef.current.send(
              JSON.stringify({
                type: "voice_chunk",
                mime_type: mimeType,
                audio_base64: base64,
              }),
            );
          } catch {
            processingRef.current = false;
            setError("Failed to send audio chunk. Retrying...");
            scheduleNextChunkCapture();
          }
        };

        recorder.onstop = () => {
          if (recorderRef.current === recorder) {
            recorderRef.current = null;
          }
        };

        recorder.start();
        chunkStopTimerRef.current = setTimeout(() => {
          chunkStopTimerRef.current = null;
          try {
            if (recorder.state !== "inactive") recorder.stop();
          } catch {
            // ignore
          }
        }, CHUNK_MS);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === "voice_status") {
            const nextStatus = payload?.data?.status || "recording";
            if (nextStatus === "processing") {
              processingRef.current = true;
              armProcessingTimeout();
            } else {
              processingRef.current = false;
              if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current);
                processingTimeoutRef.current = null;
              }
              scheduleNextChunkCapture();
            }
            setStatus(nextStatus);
          } else if (payload.event === "voice_transcript") {
            setTranscript(payload?.data?.text || "");
          } else if (payload.event === "voice_intent") {
            setIntent(payload?.data?.intent || "");
          } else if (payload.event === "voice_log") {
            setVoiceLog(payload?.data?.message || "-");
          } else if (payload.event === "voice_error") {
            setError(payload?.data?.message || "Voice processing error");
            processingRef.current = false;
            if (processingTimeoutRef.current) {
              clearTimeout(processingTimeoutRef.current);
              processingTimeoutRef.current = null;
            }
            scheduleNextChunkCapture();
          }
        } catch {
          // ignore non-json payload
        }
      };

      ws.onopen = () => {
        if (stoppingRef.current) return;
        processingRef.current = false;
        setStatus("connecting");
        ws.send(JSON.stringify({ type: "voice_start" }));
      };

      ws.onerror = () => {
        if (stoppingRef.current) return;
        setError("WebSocket voice connection failed.");
      };

      ws.onclose = async () => {
        if (stoppingRef.current) return;
        processingRef.current = false;
        if (processingTimeoutRef.current) {
          clearTimeout(processingTimeoutRef.current);
          processingTimeoutRef.current = null;
        }
        setStatus("idle");
        cleanup();
        await new Promise((r) => setTimeout(r, RECONNECT_WAIT_MS));
      };
    } catch (e) {
      setStatus("idle");
      cleanup();
      setError(e?.message || "Unable to start voice detection.");
    }
  }, [token, selectedDeviceId, cleanup]);

  return (
    <Card className="yh-card p-4 mb-4">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 style={{ margin: 0, fontWeight: 700 }}>🎤 Voice Detect</h5>
        {statusBadge}
      </div>

      {error && (
        <Alert
          variant="warning"
          className="py-2 mb-3"
          onClose={() => setError("")}
          dismissible
        >
          {error}
        </Alert>
      )}

      <Form.Group className="mb-3">
        <Form.Label>Select Microphone</Form.Label>
        <Form.Select
          value={selectedDeviceId}
          onChange={(e) => {
            const val = e.target.value;
            setSelectedDeviceId(val);
            localStorage.setItem("yh_selected_audio_device_id", val);
          }}
          disabled={status !== "idle"}
        >
          {devices.length === 0 ? (
            <option value="">No microphone found</option>
          ) : (
            devices.map((d, idx) => (
              <option key={d.deviceId || `mic-${idx}`} value={d.deviceId}>
                {d.label || `Microphone ${idx + 1}`}
              </option>
            ))
          )}
        </Form.Select>
      </Form.Group>

      <div className="d-flex gap-2 mb-3">
        <Button
          variant={status === "idle" ? "primary" : "danger"}
          onClick={status === "idle" ? startDetect : stopDetect}
          disabled={status === "idle" && devices.length === 0}
        >
          {status === "idle" ? "Start Voice Detect" : "Stop Voice Detect"}
        </Button>
        <Button
          variant="outline-light"
          onClick={refreshDevices}
          disabled={status !== "idle"}
        >
          Refresh Mic
        </Button>
      </div>

      <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
        <div>
          <strong>Wake phrase:</strong> hey yolo
        </div>
        <div>
          <strong>Transcript:</strong> {transcript || "-"}
        </div>
        <div>
          <strong>Voice log:</strong> {voiceLog || "-"}
        </div>
        <div>
          <strong>Last intent:</strong> {intent || "-"}
        </div>
      </div>
    </Card>
  );
}
