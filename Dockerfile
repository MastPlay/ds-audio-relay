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