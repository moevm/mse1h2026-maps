FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libglib2.0-0 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --timeout 5 --retries 2 -r /app/requirements.txt \
 || pip install --no-cache-dir --timeout 5 --retries 2 -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r /app/requirements.txt \
 || pip install --no-cache-dir --timeout 5 --retries 2 -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["python", "src/django/maps/manage.py", "runserver", "0.0.0.0:8000"]
