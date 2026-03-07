# YoloHome Webapp

A smart home management web application built with **ReactJS + Bootstrap** (frontend) and **FastAPI + PostgreSQL** (backend).

## Tech Stack

| Layer      | Technology                     |
|------------|--------------------------------|
| Frontend   | ReactJS, Bootstrap, React Router, Axios |
| Backend    | FastAPI (Python), SQLAlchemy   |
| Database   | PostgreSQL                     |
| Migration  | Alembic                        |
| Container  | Docker, Docker Compose         |

## Project Structure

```
YoloHome_webapp/
├── frontend/                  # React + Bootstrap SPA
│   ├── public/
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   │   ├── Navbar.js
│   │   │   └── DeviceCard.js
│   │   ├── pages/             # Page-level components
│   │   │   ├── Home.js
│   │   │   ├── Dashboard.js
│   │   │   └── Devices.js
│   │   ├── services/
│   │   │   └── api.js         # Axios API client
│   │   ├── App.js
│   │   └── index.js
│   ├── .env.example
│   ├── Dockerfile
│   └── package.json
│
├── backend/                   # FastAPI + PostgreSQL API
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       └── devices.py # Device endpoints
│   │   ├── core/
│   │   │   └── config.py      # App settings (pydantic-settings)
│   │   ├── db/
│   │   │   └── session.py     # SQLAlchemy engine & session
│   │   ├── models/
│   │   │   └── device.py      # ORM models
│   │   ├── schemas/
│   │   │   └── device.py      # Pydantic schemas
│   │   └── main.py            # FastAPI app entry point
│   ├── alembic/               # Database migrations
│   │   └── versions/
│   │       └── 001_create_devices_table.py
│   ├── alembic.ini
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml         # Orchestrates all services
└── README.md
```

## Quick Start

### Using Docker Compose (recommended)

```bash
# Start all services (database, backend, frontend)
docker-compose up --build
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000  
- API Docs (Swagger): http://localhost:8000/docs  

### Manual Setup

#### Prerequisites
- Node.js 20+
- Python 3.12+
- PostgreSQL 16+

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env if your backend runs on a different URL

# Start the development server
npm start
```

## API Endpoints

| Method | Path                          | Description              |
|--------|-------------------------------|--------------------------|
| GET    | /api/v1/devices               | List all devices         |
| POST   | /api/v1/devices               | Create a device          |
| GET    | /api/v1/devices/{id}          | Get a device             |
| PUT    | /api/v1/devices/{id}          | Update a device          |
| PATCH  | /api/v1/devices/{id}/toggle   | Toggle device on/off     |
| DELETE | /api/v1/devices/{id}          | Delete a device          |
| GET    | /api/v1/devices/stats         | Get device statistics    |
| GET    | /health                       | Health check             |
| GET    | /docs                         | Swagger UI               |
