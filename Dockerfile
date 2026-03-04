FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libsodium-dev \
    && ldconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py index.html .

CMD ["python", "main.py"]