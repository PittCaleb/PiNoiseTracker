from flask import Flask, render_template, jsonify, request, send_from_directory
import sqlite3
import os
import random
from datetime import datetime

app = Flask(__name__)
DB_PATH = '/app/data/noise.db'
AUDIO_DIR = '/app/data/audio/'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_random_color():
    return "#{:06x}".format(random.randint(0x222222, 0xDDDDDD))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    conn = get_db_connection()
    hb = conn.execute("SELECT value FROM config WHERE key='heartbeat'").fetchone()
    enabled = conn.execute("SELECT value FROM config WHERE key='system_enabled'").fetchone()
    conn.close()
    is_enabled = enabled['value'] == 'true' if enabled else True
    if not hb or hb['value'] == '0': return jsonify({'active': False, 'enabled': is_enabled})
    try:
        last_seen = datetime.fromisoformat(hb['value'])
        is_active = (datetime.now() - last_seen).total_seconds() < 25
        return jsonify({'active': is_active, 'enabled': is_enabled})
    except:
        return jsonify({'active': False, 'enabled': is_enabled})

@app.route('/api/toggle', methods=['POST'])
def toggle_system():
    conn = get_db_connection()
    current = conn.execute("SELECT value FROM config WHERE key='system_enabled'").fetchone()
    new_state = 'false' if (current and current['value'] == 'true') else 'true'
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('system_enabled', ?)", (new_state,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'state': new_state})

@app.route('/api/events')
def get_events():
    conn = get_db_connection()
    rows = conn.execute('SELECT id, start_time, duration, max_dbfs, file_path, tag FROM noise_events ORDER BY start_time DESC LIMIT 1000').fetchall()
    conn.close()
    cleaned = []
    for r in rows:
        cleaned.append({
            "id": int(r['id']),
            "start_time": str(r['start_time']),
            "duration": float(r['duration']) if r['duration'] else 0.0,
            "max_dbfs": float(r['max_dbfs']) if isinstance(r['max_dbfs'], (int, float)) else -100.0,
            "file_path": str(r['file_path']),
            "tag": str(r['tag']) if r['tag'] else "unknown"
        })
    return jsonify(cleaned)

@app.route('/api/event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    conn = get_db_connection()
    event = conn.execute('SELECT file_path FROM noise_events WHERE id = ?', (event_id,)).fetchone()
    if event:
        file_path = os.path.join(AUDIO_DIR, event['file_path'])
        if os.path.exists(file_path): os.remove(file_path)
        conn.execute('DELETE FROM noise_events WHERE id = ?', (event_id,))
        conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/tags', methods=['GET'])
def get_tags():
    conn = get_db_connection()
    tags = conn.execute('SELECT * FROM tags ORDER BY tag_name ASC').fetchall()
    conn.close()
    return jsonify({str(r['tag_name']): str(r['color']) for r in tags})

@app.route('/api/tag/<int:event_id>', methods=['POST'])
def update_tag(event_id):
    tag = request.json.get('tag', 'unknown').strip().lower()
    conn = get_db_connection()
    conn.execute('UPDATE noise_events SET tag = ? WHERE id = ?', (tag, event_id))
    conn.execute('INSERT OR IGNORE INTO tags (tag_name, color) VALUES (?, ?)', (tag, generate_random_color()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/tags/<tag_name>', methods=['POST'])
def update_tag_color(tag_name):
    color = request.json.get('color')
    conn = get_db_connection()
    conn.execute('UPDATE tags SET color = ? WHERE tag_name = ?', (color, tag_name.lower()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    conn = get_db_connection()
    if request.method == 'POST':
        val = request.json.get('threshold')
        conn.execute("UPDATE config SET value = ? WHERE key = 'threshold_dbfs'", (str(val),))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    res = conn.execute("SELECT value FROM config WHERE key='threshold_dbfs'").fetchone()
    conn.close()
    return jsonify({'threshold': float(res['value']) if res else -20.0})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
