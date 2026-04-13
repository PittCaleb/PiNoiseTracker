FROM python:3.11-slim

# Install ALSA dependencies required for sounddevice
RUN apt-get update && apt-get install -y libportaudio2 libasound2-dev alsa-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY listener.py .

CMD ["python", "-u", "listener.py"]
