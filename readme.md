# 🎙️ Pi Noise Tracker

A local, edge-computing IoT solution to monitor, record, and classify environmental noise. Built for Raspberry Pi using a USB microphone, this project uses a Dockerized Python/Flask stack to capture audio anomalies and visualize them on a real-time D3.js dashboard.

---

## ✨ Features

* **Intelligent Audio Capture:** Continuously monitors room audio using `sounddevice` and `numpy`. Triggers recordings only when noise exceeds a user-defined Decibel Full Scale (dBFS) threshold.
* **Dynamic Hardware Discovery:** Automatically scans ALSA devices on boot to find your specific USB microphone, preventing errors if USB port assignments change.
* **Automated Scheduling:** System automatically arms itself at Midnight and disarms at 8:00 AM to prevent logging standard daytime noise (configurable via the dashboard).
* **Real-Time D3.js Dashboard:** Visualizes the last 7 days of noise events on a beautiful, interactive scatterplot.
* **Smart Polling:** The frontend checks the database every 2 seconds via a lightweight micro-API. New audio events instantly animate onto the timeline without requiring a page refresh.
* **Tagging & Review System:** Click any event on the timeline to play back the `.wav` file, apply custom classification tags (e.g., "Train", "Siren", "Garbage Truck"), or delete false positives.

---

## 🏗️ System Architecture

The application is split into two decoupled Docker containers communicating via a shared SQLite database and volume mount.

1. **Backend Listener (`backend/listener.py`):** A headless daemon running on a high-priority audio thread. It handles ALSA pass-through, calculates dBFS, manages recording state buffers, and safely hands data to a worker queue for disk writes.
2. **Frontend Web API (`frontend/app.py`):** A lightweight Flask server that serves the HTML/JS dashboard, streams the `.wav` files, and provides REST endpoints for configuration and tagging.

---

## 🗂️ Project Structure

Code output
README generated successfully.

```text
noise_tracker/
├── docker-compose.yml
├── data/                       # Docker Volume (Persistent)
│   ├── noise.db                # SQLite Database
│   └── audio/                  # Saved .wav files
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── listener.py             # Audio capture engine
└── frontend/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py                  # Flask API
    └── templates/
        └── index.html          # D3.js Dashboard UI
