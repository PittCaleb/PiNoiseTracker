import sounddevice as sd
import numpy as np
import sqlite3
import wave
import os
import queue
import time
from datetime import datetime

DB_PATH = '/app/data/noise.db'
AUDIO_DIR = '/app/data/audio/'
SAMPLE_RATE = 44100
CHANNELS = 1

os.makedirs(AUDIO_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS noise_events (id INTEGER PRIMARY KEY AUTOINCREMENT, start_time DATETIME, duration REAL, max_dbfs REAL, file_path TEXT, tag TEXT DEFAULT "unknown")')
    c.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('threshold_dbfs', '-20.0')")
    c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('heartbeat', '0')")
    c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('system_enabled', 'true')")
    conn.commit()
    return conn

def get_config_val(key, default):
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        conn.close()
        return res[0] if res else default
    except:
        return default

def check_auto_enable():
    # This now uses LOCAL time thanks to the Docker volume mount
    now = datetime.now()
    if now.hour == 0 and now.minute == 0:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE config SET value = 'true' WHERE key = 'system_enabled'")
            conn.commit()
            conn.close()
        except:
            pass

def update_heartbeat():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE config SET value = ? WHERE key = 'heartbeat'", (datetime.now().isoformat(),))
        conn.commit()
        conn.close()
    except:
        pass

def calculate_dbfs(indata):
    rms = np.sqrt(np.mean(indata**2))
    val = 20 * np.log10(rms) if rms > 0 else -100.0
    return float(val)

def find_microphone():
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            name = dev['name'].lower()
            if 'usb' in name or 'camera' in name:
                return i
    return None

def main():
    init_db()
    device_id = find_microphone()
    save_queue = queue.Queue()
    
    state = {
        'is_recording': False,
        'buffer': [],
        'start_time': None,
        'max_db': -100.0,
        'cooldown': 0
    }

    def audio_callback(indata, frames, time_info, status):
        if get_config_val('system_enabled', 'true') == 'false':
            return

        threshold = float(get_config_val('threshold_dbfs', '-20.0'))
        dbfs = calculate_dbfs(indata)
        
        if dbfs > threshold:
            if not state['is_recording']:
                state['is_recording'] = True
                state['start_time'] = datetime.now() # Uses local time
                state['buffer'] = []
                state['max_db'] = dbfs
            state['cooldown'] = 0
            
        if state['is_recording']:
            state['buffer'].append(indata.copy())
            state['max_db'] = max(state['max_db'], dbfs)
            state['cooldown'] += 1
            if state['cooldown'] > 130:
                state['is_recording'] = False
                audio_data = np.concatenate(state['buffer'])
                duration = float(len(audio_data) / SAMPLE_RATE)
                save_queue.put((state['start_time'], duration, float(state['max_db']), audio_data))

    with sd.InputStream(device=device_id, channels=CHANNELS, samplerate=SAMPLE_RATE, callback=audio_callback, blocksize=1024):
        while True:
            update_heartbeat()
            check_auto_enable()
            try:
                while not save_queue.empty():
                    start_t, dur, mdb, data = save_queue.get_nowait()
                    ts = start_t.strftime("%Y%m%d_%H%M%S")
                    fname = f"noise_{ts}.wav"
                    fpath = os.path.join(AUDIO_DIR, fname)
                    with wave.open(fpath, 'wb') as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(2)
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes((data * 32767).astype(np.int16).tobytes())
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT INTO noise_events (start_time, duration, max_dbfs, file_path) VALUES (?,?,?,?)",
                                 (start_t.strftime("%Y-%m-%d %H:%M:%S"), float(dur), float(mdb), fname))
                    conn.commit()
                    conn.close()
            except queue.Empty:
                pass
            time.sleep(5)

if __name__ == "__main__":
    main()
