FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=8000 \
    UNIFIED_HOST=0.0.0.0 \
    UNIFIED_DB_PATH=/app/data/unified.db \
    UNIFIED_AUTH_DB_PATH=/app/data/auth.db \
    ALLOW_REGISTRATION=false \
    COOKIE_SECURE_ONLY=true \
    ENABLE_CODE_EXECUTION=false

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY guides ./guides
COPY unified_studio_dashboard.html ./unified_studio_dashboard.html

RUN mkdir -p /app/data /app/outputs && \
    useradd --system --uid 10001 --create-home studio && \
    chown -R studio:studio /app

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os; from urllib.request import urlopen; urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=3)"

CMD ["sh", "-c", "uvicorn server:app --app-dir /app/backend --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers"]
