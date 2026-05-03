# YoloHome Web App

YoloHome is a smart-home platform with real-time device control, AI voice commands, automated scheduling, MQTT hardware integration, and face recognition security.

## Tech Stack

| Layer           | Technology                            |
| --------------- | ------------------------------------- |
| Frontend        | React + Bootstrap 5                   |
| Backend         | FastAPI + SQLAlchemy (async)          |
| Database        | PostgreSQL (pgvector image in Docker) |
| Messaging       | MQTT (Eclipse Mosquitto)              |
| Realtime        | WebSocket (JWT-authenticated)         |
| AI Models       | Sherpa-ONNX, Faster-Whisper, InsightFace (RetinaFace + ArcFace) |
| Task Scheduling | APScheduler                           |
| Containers      | Docker + Docker Compose               |
| Hardware Script | MicroPython (YoloBit)                 |

---

## Repository Structure

```text
YoloHome_webapp/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # Entry points: REST API and WebSocket endpoints
│   │   ├── service/            # Business Logic: AI (Voice/Face), Scheduling, Device management
│   │   ├── core/               # Infrastructure: Config, Security, Drivers (MQTT, WS, Audio Streamer)
│   │   ├── workers/            # Background Tasks: Periodic job registration (APScheduler)
│   │   ├── db/                 # Persistence: Database session and migrations
│   │   ├── models/             # Data Models: SQLAlchemy ORM definitions
│   │   └── schemas/            # Data Validation: Pydantic schemas
│   ├── alembic/                # Database migration tool configuration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/components/         # Reusable UI components
│   ├── src/hooks/              # Custom React hooks (WebSocket, Auth)
│   ├── src/pages/              # Main application pages (Dashboard, History)
│   ├── src/services/           # API communication layers
│   ├── Dockerfile
│   └── package.json
├── models/                     # Face model files + prepare script
├── yolobit_microPython/        # Hardware script for YoloBit
├── docker-compose.yml
├── mosquitto.conf              # MQTT Broker configuration
└── .env.example
```

---

## Quick Start (Docker)

1. Create local env file from template:

```bash
cp .env.example .env
```

2. Start all services:

```bash
docker compose up --build
```

3. Open:

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs
- Health check: http://localhost:8000/health

Exposed service ports:

- PostgreSQL: `5433` (container `5432`)
- Backend API: `8000`
- Frontend: `3000`
- MQTT broker: `1883`

---

## Face Model Setup (Required)

Face enrollment and recognition require model files in [models/](models/):

- `arcface_resnet100.onnx`
- `det_10g.onnx`

To prepare once:

```bash
cd models
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python prepare.py
```

If these files are missing, face-related endpoints/pages will not work.

---

## Local Development (Without Docker)

### Backend

```bash
cp .env.example .env

cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

---

## MQTT Integration

The system uses 4 specific MQTT topics for bi-directional communication with hardware nodes:

1. **Announce Topic:** `smart_home/hardware/<MAC_ADDRESS>/announce`
   - Hardware sends its capabilities and pin configurations to register with the backend.
2. **Sensor Topic:** `smart_home/hardware/<MAC_ADDRESS>/sensor`
   - Hardware continuously publishes environmental data (e.g., temperature, humidity).
3. **State Topic:** `smart_home/hardware/<MAC_ADDRESS>/state`
   - Hardware acknowledges command execution and reports its current state (e.g., LED is ON, Servo is at 90 degrees).
4. **Command Topic:** `smart_home/hardware/<MAC_ADDRESS>/command`
   - Backend sends control instructions to the hardware.

---

## AI & Voice Engine

YoloHome features a sophisticated voice control pipeline designed for low-latency and high-accuracy Vietnamese command processing.

### 1. Voice Control Pipeline
- **Voice Streamer (Core):** A low-level audio driver that uses `ffmpeg` to pull raw PCM audio from an IP Webcam/Microphone URL (`IP_WEBCAM_AUDIO_URL`) and feeds it into an internal queue.
- **Voice Service (Business Logic):** Orchestrates the full AI lifecycle:
    - **Keyword Spotting (KWS):** Powered by **Sherpa-ONNX** to detect the wake word (e.g., "Hey Yolo").
    - **Speech-to-Text (STT):** Powered by **Faster-Whisper** for Vietnamese command recognition.
    - **Intent Matching:** Uses **RapidFuzz** to map text to hardware commands.

### 2. Face Recognition
- **Detection:** **RetinaFace** is used for high-accuracy face localization even in challenging lighting.
- **Recognition:** **ArcFace (ResNet100)** generates 512-D face embeddings.
- **Database:** Embeddings are stored in **PostgreSQL** using the `pgvector` extension for efficient similarity searches.

---

## Realtime Behavior

YoloHome uses a high-performance WebSocket architecture for instant updates and reliable hardware control.

- **Secure Handshake:** Frontend connects via `WS /api/v1/ws`. Authentication is performed using **WebSocket Subprotocols** (`["token", JWT]`) to prevent sensitive tokens from appearing in server access logs.
- **Bi-directional Heartbeat:** Client sends `{ "type": "ping" }` every 30s; server maintains a 60s idle timeout.
- **Command-Response Logic:**
    - When a command is sent, the UI enters a **Pending State** (visual spinners).
    - The database is only updated once the physical hardware acknowledges success via a `state` message.
    - This ensures the Dashboard always reflects the **actual** state of your home, not just the requested state.
- **Global Broadcast:** Sensor data, device state changes, and system alerts are pushed instantly to all connected clients.

## Environment Variables

Copy [.env.example](.env.example) to `.env` and adjust as needed. Core values include:

- `DATABASE_URL`
- `SECRET_KEY`
- `WAKE_WORD`
- `IP_WEBCAM_AUDIO_URL`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`
- `SETUP_CODE`
- `MQTT_BROKER_URL`
- `MQTT_PORT`
- `ARCFACE_MODEL_PATH`
- `RETINAFACE_MODEL_PATH`
- `ADMIN_RESET_MODE`
