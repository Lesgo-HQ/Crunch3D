FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libcom-err2 \
    libp11-kit0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/model

EXPOSE 8000

CMD ["sh", "-c", "uvicorn model.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
