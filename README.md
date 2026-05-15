# YoloHome Web App

YoloHome is a smart-home platform with real-time device control, scheduling, MQTT hardware integration, and face recognition.

## Tech Stack

| Layer           | Technology                            |
| --------------- | ------------------------------------- |
| Frontend        | React + Bootstrap 5                   |
| Backend         | FastAPI + SQLAlchemy (async)          |
| Database        | PostgreSQL (pgvector image in Docker) |
| Messaging       | MQTT (Eclipse Mosquitto)              |
| Realtime        | WebSocket (JWT-authenticated)         |
| Migrations      | Alembic                               |
| Containers      | Docker + Docker Compose               |
| Hardware Script | MicroPython (YoloBit)                 |

---

## Repository Structure

```
YoloHome_webapp/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # auth, users, devices, face, ws
│   │   ├── core/               # config, security, face service
│   │   ├── db/                 # async session + db utils
│   │   ├── models/             # ORM models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── realtime/           # websocket manager + scheduler loop
│   │   └── service/            # MQTT service, history
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
├── models/                     # face model files + prepare script
├── yolobit_microPython/        # hardware script for YoloBit
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

## API Overview (Current)

Base URL: `/api/v1`

### Auth

- `POST /auth/login`
- `POST /auth/register`
- `GET /auth/me`

### Users (Admin)

- `GET /admin/users/`
- `PUT /admin/users/invitation-key`
- `DELETE /admin/users/{user_id}`

### Devices + Hardware

- `GET /devices/hardware`
- `GET /devices/hardware/{hardware_id}`
- `DELETE /devices/hardware/{hardware_id}`
- `POST /devices/`
- `GET /devices/`
- `GET /devices/get-camera-devices`
- `GET /devices/{device_id}`
- `PATCH /devices/{device_id}`
- `DELETE /devices/{device_id}`
- `POST /devices/{device_id}/command`
- `GET /devices/{device_id}/history`
- `GET /devices/{sensor_type}/sensor-data`

### Device Schedules

- `POST /devices/{device_id}/schedules`
- `GET /devices/{device_id}/schedules`
- `PUT /devices/schedules/{schedule_id}`
- `DELETE /devices/schedules/{schedule_id}`

### Face Recognition

- `GET /face/camera`
- `GET /face/enrollments`
- `POST /face/enrollments/image`
- `DELETE /face/enrollments/{enrollment_id}`
- `GET /face/enrollments/{enrollment_id}/image`
- `POST /face/recognize`
- `GET /face/logs`
- `GET /face/logs/{log_id}/image`

### WebSocket

- `WS /api/v1/ws?token=<jwt>`

---

## Realtime Behavior

- Frontend opens one global WebSocket connection.
- Client sends `{ "type": "ping" }` every 30 seconds.
- Server closes idle sockets after 60 seconds if no messages are received.

## Environment Variables

Copy [.env.example](.env.example) to `.env` and adjust as needed. Core values include:

- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`
- `SETUP_CODE`
- `MQTT_BROKER_URL`
- `MQTT_PORT`
- `ARCFACE_MODEL_PATH`
- `RETINAFACE_MODEL_PATH`
