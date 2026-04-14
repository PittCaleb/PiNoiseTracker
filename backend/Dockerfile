FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    libasound2-dev \
    libportaudio2 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Because context is ./backend, these files are "local" to the build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listener.py .

CMD ["python", "-u", "listener.py"]
