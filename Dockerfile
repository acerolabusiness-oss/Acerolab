FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requisitos.txt .
RUN pip install --no-cache-dir -r requisitos.txt

COPY . .

CMD ["python", "-m", "plataforma", "--publico"]
