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
| AI Models       | OpenWakeWord, Whisper, RetinaFace, ArcFace |
| Task Scheduling | APScheduler                           |
| Containers      | Docker + Docker Compose               |
| Hardware Script | MicroPython (YoloBit)                 |

---

## Repository Structure

```text
YoloHome_webapp/
├── backend/
│   ├── app/
│   │   ├── ai/                 # Face recognition, voice logic, and NLP intent
│   │   ├── api/routes/         # Auth, users, devices, face, ws
│   │   ├── core/               # Config, security, logger
│   │   ├── db/                 # Async session, utils, init_db
│   │   ├── models/             # ORM models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── service/            # Core business logic (device, command, history, ws, mqtt)
│   │   └── workers/            # Background tasks (scheduler, voice_stream)
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/components/
│   ├── src/pages/
│   ├── src/contexts/
│   ├── src/services/
│   ├── Dockerfile
│   └── package.json
├── models/                     # Face model files + prepare script
├── yolobit_microPython/        # Hardware script for YoloBit
├── docker-compose.yml
├── mosquitto.conf
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

## Realtime Behavior

- Frontend opens one global WebSocket connection via `WS /api/v1/ws?token=<jwt>`.
- Client sends `{ "type": "ping" }` every 30 seconds.
- Server closes idle sockets after 60 seconds if no messages are received.
- Real-time updates (sensor data, device state changes, scheduled triggers) are pushed through this connection.

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
