# YoloHome Web App

A smart home web application built with the following tech stack:

| Layer | Technology |
|---|---|
| **Frontend** | React (JavaScript) + Bootstrap 5 |
| **Backend** | FastAPI (Python) |
| **Database** | PostgreSQL |
| **Migrations** | Alembic |
| **Containers** | Docker + Docker Compose |

---

## Project Structure

```
YoloHome_webapp/
├── frontend/               # React + Bootstrap frontend
│   ├── src/
│   │   ├── components/     # Shared UI components (Navbar, …)
│   │   ├── pages/          # Page-level components (Home, Items, …)
│   │   └── services/       # Axios API client
│   ├── .env.example        # Environment variable template
│   ├── Dockerfile
│   └── nginx.conf          # Nginx config for production container
│
├── backend/                # FastAPI backend
│   ├── app/
│   │   ├── api/routes/     # Route handlers
│   │   ├── core/           # App settings
│   │   ├── db/             # Database session
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── tests/          # Pytest test suite
│   ├── alembic/            # Database migrations
│   ├── .env.example        # Environment variable template
│   ├── Dockerfile
│   └── requirements.txt
│
└── docker-compose.yml      # One-command local environment
```

---

## Quick Start with Docker Compose

```bash
docker compose up --build
```

This starts:
- **PostgreSQL** on port `5432`
- **FastAPI** backend on port `8000`  
- **React** frontend on port `3000`

Open **http://localhost:3000** in your browser.

---

## Local Development (without Docker)

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment variables
cp .env.example .env

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
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy and edit environment variables
cp .env.example .env

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
| GET | `/api/v1/auth/me` | JWT | Read the current authenticated user's profile |
| **Users** |
| GET | `/api/v1/users/` | Admin | List all users |
| POST | `/api/v1/users/` | Admin | Create a user |
| **Devices** |
| GET | `/api/v1/devices/` | JWT | List the current user's own devices |
| POST | `/api/v1/devices/` | JWT | Create a device (`fan`/`light`/`camera`) — default feed auto-created |
| GET | `/api/v1/devices/{id}` | Owner | Read a device |
| DELETE | `/api/v1/devices/{id}` | Owner | Delete a device (cascades feeds & commands) |
| POST | `/api/v1/devices/{id}/rotate-key` | Owner | Rotate the device hardware key |
| POST | `/api/v1/devices/{id}/heartbeat` | Device Key | Kit / gateway signals it is online (`X-Device-Key`) |
| GET | `/api/v1/devices/{id}/commands` | Owner | List commands for a device |
| POST | `/api/v1/devices/{id}/commands` | JWT | Queue a command for a device |
| GET | `/api/v1/devices/{id}/commands/pending` | Device Key | Device pulls pending commands (`X-Device-Key`) |
| PATCH | `/api/v1/devices/{id}/commands/{cid}/ack` | Device Key | Device acknowledges a command (`X-Device-Key`) |
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
| POST | `/api/v1/face/enrollments` | Admin | Register a face (store feature vector + name) |
| DELETE | `/api/v1/face/enrollments/{id}` | Admin | Delete an enrolled face |
| POST | `/api/v1/face/recognize` | Device Key | Camera submits image for recognition (saves image, creates log) |
| GET | `/api/v1/face/logs` | JWT | List face recognition log entries |
| **WebSockets** |
| WS | `/ws/feeds/{id}?token=...` | JWT | Subscribe to live feed value updates |
| WS | `/ws/devices/{id}?token=...` | JWT | Subscribe to live device events |

### IoT Backend Flow

1. On first startup the server automatically creates an admin account (username: `admin`, password: `kiendeptrai`).
2. Log in with `POST /api/v1/auth/login` and use the returned bearer token for all user APIs.
3. Any user can create a device (`fan`, `light`, or `camera`) — a default feed is created automatically.
4. Store the returned device key on the physical kit and publish telemetry via `POST /api/v1/feeds/{id}/ingest`.
5. Use dashboards, feed history, and WebSocket subscriptions from authenticated frontend users.
6. For door access, enroll faces via `POST /api/v1/face/enrollments` and submit camera images via `POST /api/v1/face/recognize`.
