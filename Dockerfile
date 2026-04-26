FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt .

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        build-essential \
        libpq-dev \
    && pip install --upgrade --no-cache-dir pip setuptools wheel \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libglib2.0-0 \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels /var/lib/apt/lists/*

COPY . /app

EXPOSE 8000

ENTRYPOINT ["python", "src/django/maps/manage.py", "runserver", "0.0.0.0:8000"]
