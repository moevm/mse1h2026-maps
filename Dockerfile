FROM python:3.11-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src/django/maps \
    HF_HOME=/cache/hf \
    TRANSFORMERS_CACHE=/cache/hf \
    UV_HTTP_TIMEOUT=120 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=60 install -y --no-install-recommends \
        gcc \
        build-essential \
        libglib2.0-0 \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN uv pip install --system --no-cache -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["python", "src/django/maps/manage.py", "runserver", "0.0.0.0:8000"]