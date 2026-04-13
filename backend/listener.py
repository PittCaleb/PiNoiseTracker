import sounddevice as sd
import numpy as np
import sqlite3
import wave
import time
import os
import queue
from datetime import datetime

DB_PATH = '/app/data/noise.db'
AUDIO_DIR = '/app/data/audio/'
SAMPLE_RATE = 44100
CHANNELS = 1

os.makedirs(AUDIO_DIR, exist_ok=True)

def find_camera_mic(search_string="PC-LM1E"):
    print(f"Scanning for audio devices containing: '{search_string}'...")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0 and search_string in dev['name']:
            print(f"--> Found microphone: '{dev['name']}' at hardware index {i}")
            return i
    print("\nERROR: Could not find the specified microphone. Available devices:")
    print(devices)
    raise ValueError(f"Microphone matching '{search_string}' not found.")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS noise_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME,
                    duration REAL,
                    max_dbfs REAL,
                    avg_dbfs REAL,
                    file_path TEXT,
                    tag TEXT DEFAULT 'unknown'
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value REAL
                )''')
    c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('threshold_dbfs', -20.0)")
    c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('listener_active', 1.0)")
    conn.commit()
    return conn

def get_config(conn):
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='threshold_dbfs'")
    threshold = c.fetchone()[0]
    c.execute("SELECT value FROM config WHERE key='listener_active'")
    active_row = c.fetchone()
    is_active = bool(active_row[0]) if active_row else True
    return threshold, is_active

def set_active_state(conn, state_bool):
    c = conn.cursor()
    c.execute("UPDATE config SET value = ? WHERE key = 'listener_active'", (1.0 if state_bool else 0.0,))
    conn.commit()

def calculate_dbfs(indata):
    rms = np.sqrt(np.mean(indata**2))
    if rms > 0:
        return 20 * np.log10(rms)
    return -100 

def main():
    conn = init_db()
    print("Database initialized.")
    device_id = find_camera_mic()
    
    threshold, is_active_config = get_config(conn)
    last_checked_hour = datetime.now().hour
    
    is_recording = False
    audio_buffer = []
    start_time = None
    max_db = -100
    db_sum = 0
    chunk_count = 0
    cooldown_frames = 0
    
    COOLDOWN_LIMIT = int(SAMPLE_RATE / 1024 * 3) 
    save_queue = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        nonlocal is_recording, audio_buffer, start_time, max_db, db_sum, chunk_count, cooldown_frames, threshold, is_active_config
        
        dbfs = calculate_dbfs(indata)
        
        # Only start a new trigger if the system is currently Active
        if is_active_config and dbfs > threshold:
            if not is_recording:
                is_recording = True
                start_time = datetime.now()
                audio_buffer = []
                max_db = dbfs
                db_sum = 0
                chunk_count = 0
                print(f"Triggered! DBFS: {dbfs:.2f}")
            cooldown_frames = 0 
            
        if is_recording:
            audio_buffer.append(indata.copy())
            max_db = max(max_db, dbfs)
            db_sum += dbfs
            chunk_count += 1
            cooldown_frames += 1
            
            # Stop if cooldown reached, OR if system was suddenly deactivated mid-recording
            if cooldown_frames > COOLDOWN_LIMIT or not is_active_config:
                is_recording = False
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds() - (3 if is_active_config else 0)
                
                # Only save if it's a valid snippet (>0.5s)
                if duration > 0.5:
                    avg_db = db_sum / chunk_count
                    audio_data = np.concatenate(audio_buffer)
                    save_queue.put((start_time, float(duration), float(max_db), float(avg_db), audio_data))

    print("System armed. Monitoring audio stream...")
    with sd.InputStream(device=device_id, channels=CHANNELS, samplerate=SAMPLE_RATE, callback=audio_callback, blocksize=1024):
        while True:
            try:
                # --- AUTOMATIC SCHEDULING LOGIC ---
                current_time = datetime.now()
                current_hour = current_time.hour
                
                # Detect the moment the hour changes
                if last_checked_hour != current_hour:
                    if current_hour == 0:
                        print("Midnight reached. Auto-activating listener.")
                        set_active_state(conn, True)
                    elif current_hour == 8:
                        print("8:00 AM reached. Auto-deactivating listener.")
                        set_active_state(conn, False)
                    last_checked_hour = current_hour

                # Always pull latest config (catches UI toggles and auto-schedule)
                threshold, is_active_config = get_config(conn)
                
                # Check for finished recordings
                event_data = save_queue.get(timeout=1)
                start_time, duration, max_db, avg_db, audio_data = event_data
                
                timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
                file_name = f"noise_{timestamp_str}.wav"
                file_path = os.path.join(AUDIO_DIR, file_name)
                
                with wave.open(file_path, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2) 
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
                
                c = conn.cursor()
                c.execute('''INSERT INTO noise_events 
                             (start_time, duration, max_dbfs, avg_dbfs, file_path) 
                             VALUES (?, ?, ?, ?, ?)''', 
                          (start_time, duration, max_db, avg_db, file_name))
                conn.commit()
                print(f"Saved {file_name} | Duration: {duration:.1f}s | Max dB: {max_db:.1f}")
                
            except queue.Empty:
                pass # Normal behavior every 1 second, keeps the loop spinning

if __name__ == "__main__":
    main()
