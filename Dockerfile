# Container for the EGX Research platform.
# Targets free hosting (Hugging Face Spaces, Render, Fly.io, Railway).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/egx.db ./data/egx.db

# Hugging Face Spaces serves on 7860; other hosts inject $PORT.
EXPOSE 7860
CMD ["sh", "-c", "python -m uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-7860} --app-dir backend"]
