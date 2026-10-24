FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATE_DIR=/var/data SAMPLE_DB=/app/data/sample.db
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./backend/
COPY data/ ./data/
RUN python data/seed.py --path /app/data/sample.db && chmod 444 /app/data/sample.db \
    && useradd --uid 10001 --create-home appuser && mkdir -p /var/data && chown appuser /var/data
COPY --from=frontend /build/dist ./frontend/dist
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live',timeout=3)"
CMD ["python","-m","uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-proxy-headers"]
