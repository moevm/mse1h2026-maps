FROM python:3.11-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 install -y --no-install-recommends \
        gcc \
        build-essential \
        libpq-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN python -m venv /opt/venv

RUN uv pip install --python /opt/venv/bin/python --no-cache \
    --index-strategy unsafe-best-match \
    -r /app/requirements.txt


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src/django/maps \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/cache/hf \
    TRANSFORMERS_CACHE=/cache/hf

WORKDIR /app

RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

COPY . /app

EXPOSE 8000

CMD ["python", "src/django/maps/manage.py", "runserver", "0.0.0.0:8000"]