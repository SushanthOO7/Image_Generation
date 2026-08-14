FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY worker /app/worker
COPY model_configs /app/model_configs

CMD ["celery", "-A", "worker.app.celery_app", "worker", "--loglevel=info", "-Q", "generation:high,generation:normal,generation:low", "-c", "1"]
