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

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/items/` | List all items |
| POST | `/api/v1/items/` | Create an item |
| GET | `/api/v1/items/{id}` | Get an item |
| PUT | `/api/v1/items/{id}` | Update an item |
| DELETE | `/api/v1/items/{id}` | Delete an item |
