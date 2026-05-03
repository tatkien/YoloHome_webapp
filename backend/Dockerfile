FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg gcc python3-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Sử dụng mount cache để giữ lại các file đã tải về giữa các lần build
# Giúp không phải tải lại các thư viện nặng dù requirements.txt có thay đổi
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python /models/prepare.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info"]
