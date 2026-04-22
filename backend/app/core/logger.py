import os
import time
import logging
from fastapi import Request
from logging.handlers import TimedRotatingFileHandler
from app.core.config import settings

# Đảm bảo thư mục logs tồn tại
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# logger chính
logger = logging.getLogger("yolohome")
logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

if not logger.handlers:
    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)

    # 2. File Handler
    # Chia file theo từng ngày, giữ 7 file 7 ngày gần nhất
    log_file_path = os.path.join(LOG_DIR, "yolohome.log")
    file_handler = TimedRotatingFileHandler(
        filename=log_file_path, 
        when="midnight", 
        interval=1, 
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

async def logging_middleware(request: Request, call_next):
    """
    Lightweight middleware to log API requests and status codes.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    
    logger.info(
        f"[API] {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {formatted_process_time}ms"
    )
    return response

async def add_history_record(
    device_id: str, 
    device_name: str, 
    action: str, 
    actor: str|int, 
    source: str,
    db = None
):
    """
    Helper to log system activity records to yolohome.log.
    """
    log_msg = f"[HISTORY] Device: {device_name} ({device_id}) | Action: {action} | Actor: {actor} | Source: {source}"
    logger.info(log_msg)
