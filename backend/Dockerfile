FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg gcc python3-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python /models/prepare.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info"]
