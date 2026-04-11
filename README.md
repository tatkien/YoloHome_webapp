# YoloHome Web App

A smart home web application built with the following tech stack:

| Layer | Technology |
|---|---|
| **Frontend** | React (JavaScript) + Bootstrap 5 |
| **Backend** | FastAPI (Python) |
| **Database** | PostgreSQL |
| **Hardware** | MicroPython (Thonny)|
| **Migrations** | Alembic |
| **Containers** | Docker + Docker Compose |

---

## Project Structure

```
YoloHome_webapp/
├── backend/                # FastAPI backend
│   ├── app/
│   │   ├── api/            # Route handlers
│   │   ├── core/           # App settings
│   │   ├── db/             # Database session
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── realtime/       # WebSocket + scheduler utilities
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── service/        # MQTT
│   │   └── tests/          # Pytest test suite
│   ├── alembic/            # Database migrations
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example        # Environment variable template
│
├── frontend/               # React + Bootstrap frontend
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
|
├── hardware/               # MicroPython (Thonny) + Yolobit
│   └── yolobit.py
│
├── models/                 # ML model weights
└── docker-compose.yml      # One-command local environment
```

---

## Quick Start with Docker Compose

```bash
docker compose up --build
```

This starts:
- **PostgreSQL** on port `5433`
- **FastAPI** backend on port `8000`  
- **React** frontend on port `3000`

Open **http://localhost:3000** in your browser.

---

## Face Recognition Model Setup (Required)

Before using face enrollment or face recognition from the web UI, download and prepare the model files in `models/`.

Runtime-required files:
- `models/arcface_resnet100.onnx`
- `models/det_10g.onnx`

Preparation-only file (used by `prepare.py` to export ArcFace ONNX):
- `models/model_weights/ms1mv3_arcface_r100_fp16.pth`

### One-time model download and export

```bash
cd models

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install model tooling dependencies
pip install -r requirements.txt

# Download weights and detector, then export ArcFace ONNX
python prepare.py
```

After this finishes, verify these files exist:

```bash
models/arcface_resnet100.onnx
models/det_10g.onnx
```

Optional check (only needed if you plan to re-run model export):

```bash
models/model_weights/ms1mv3_arcface_r100_fp16.pth
```

If runtime files are missing, face enrollment/recognition endpoints and web pages will not work correctly.

---

## Local Development (without Docker)

### Backend

```bash
# Create and activate a virtual environment
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment variables (run from repository root)
cd ..
cp .env.example .env
cd backend

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload
```

API docs are available at **http://localhost:8000/api/docs**.

Backend environment variables:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/yolohome
SECRET_KEY=replace-this-in-real-environments
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:3000
SETUP_CODE=yolohome2024
```

When using Docker Compose, set `SETUP_CODE` in the root `.env` file so admin registration works.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy and edit environment variables
cp frontend/.env.example frontend/.env

# Start the development server
npm start
```

The app opens at **http://localhost:3000**.

---

## Running Tests

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm test
```

---

## API Overview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check |
| **Auth** |
| POST | `/api/v1/auth/login` | — | Log in and receive a JWT access token |
| POST | `/api/v1/auth/register` | — | Register (setup code for first admin, invitation key for users) |
| GET | `/api/v1/auth/me` | JWT | Read the current authenticated user's profile |
| **Users** |
| GET | `/api/v1/admin/users/` | Admin | List all users |
| PUT | `/api/v1/admin/users/invitation-key` | Admin | Set or rotate the invitation key |
| **Devices** |
| GET | `/api/v1/devices/` | JWT | List the current user's own devices |
| POST | `/api/v1/devices/` | Admin | Create a device (`fan`/`light`/`camera`/`temp_sensor`/`humidity_sensor`) — default feed auto-created |
| GET | `/api/v1/devices/{id}` | Owner | Read a device |
| DELETE | `/api/v1/devices/{id}` | Admin | Delete a device (cascades feeds & commands) |
| POST | `/api/v1/devices/{id}/rotate-key` | Admin | Rotate the device hardware key |
| POST | `/api/v1/devices/{id}/heartbeat` | Device Key | Kit / gateway signals it is online (`X-Device-Key`) |
| GET | `/api/v1/devices/{id}/commands` | Owner | List commands for a device |
| POST | `/api/v1/devices/{id}/commands` | JWT | Queue a command for a device |
| GET | `/api/v1/devices/{id}/commands/pending` | Device Key | Device pulls pending commands (`X-Device-Key`) |
| PATCH | `/api/v1/devices/{id}/commands/{cid}/ack` | Device Key | Device acknowledges a command (`X-Device-Key`) |
| GET | `/api/v1/devices/{id}/schedules` | JWT | List device schedules |
| POST | `/api/v1/devices/{id}/schedules` | Admin | Create a daily schedule for a light |
| DELETE | `/api/v1/devices/{id}/schedules/{schedule_id}` | Admin | Delete a schedule |
| **Feeds** |
| GET | `/api/v1/feeds/` | JWT | List feeds belonging to the current user's devices |
| POST | `/api/v1/feeds/` | Owner | Create an extra feed for your own device |
| GET | `/api/v1/feeds/{id}` | Owner | Read a feed |
| GET | `/api/v1/feeds/{id}/values` | Owner | Read feed value history |
| POST | `/api/v1/feeds/{id}/values` | Owner | Publish a value as a user |
| POST | `/api/v1/feeds/{id}/ingest` | Device Key | Publish a value from the physical kit (`X-Device-Key`) |
| **Dashboards** |
| GET | `/api/v1/dashboards/` | JWT | List dashboards owned by the current user |
| POST | `/api/v1/dashboards/` | JWT | Create a dashboard |
| GET | `/api/v1/dashboards/{id}` | JWT | Read a dashboard with its widgets |
| POST | `/api/v1/dashboards/{id}/widgets` | JWT | Add a widget to a dashboard |
| **Face Recognition** |
| GET | `/api/v1/face/enrollments` | JWT | List enrolled faces |
| POST | `/api/v1/face/enrollments/image` | Admin | Upload one image and enroll face for a registered user_id |
| DELETE | `/api/v1/face/enrollments/{id}` | Admin | Delete an enrolled face |
| POST | `/api/v1/face/recognize` | Device Key | Camera submits image for recognition (returns matched_user_id/matched_user_name when recognized) |
| GET | `/api/v1/face/logs` | JWT | List face recognition log entries |
| **WebSockets** |
| WS | `/ws/feeds/{id}?token=...` | JWT | Subscribe to live feed value updates |
| WS | `/ws/devices/{id}?token=...` | JWT | Subscribe to device events (includes initial history) |

### IoT Backend Flow

1. Register the first admin via `POST /api/v1/auth/register` using `SETUP_CODE`.
2. As admin, set an invitation key with `PUT /api/v1/admin/users/invitation-key`.
3. Register users via `POST /api/v1/auth/register` using the invitation key.
4. Admin creates devices (`fan`, `light`, `camera`, `temp_sensor`, `humidity_sensor`), and the default feed is created automatically.
5. Devices publish telemetry via `POST /api/v1/feeds/{id}/ingest` with `X-Device-Key`.
6. Frontend subscribes to `WS /ws/devices/{id}` to receive history and real-time updates.
7. For door access, admins select a registered user from `GET /api/v1/admin/users/`, enroll via `POST /api/v1/face/enrollments/image`, and submit camera images via `POST /api/v1/face/recognize`.
