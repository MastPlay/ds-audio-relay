FROM python:3.10-slim

# Устанавливаем системные зависимости для голоса и сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Обновляем pip и устанавливаем зависимости с детальным логированием
COPY requirements.txt .
RUN pip install --no-cache-dir --verbose -r requirements.txt

COPY main.py index.html .

CMD ["python", "main.py"]