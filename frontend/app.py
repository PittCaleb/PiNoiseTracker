from flask import Flask, render_template, jsonify, request, send_from_directory
import sqlite3
import os

app = Flask(__name__)
DB_PATH = '/app/data/noise.db'
AUDIO_DIR = '/app/data/audio/'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/events')
def get_events():
    conn = get_db_connection()
    events = conn.execute(
        'SELECT * FROM noise_events ORDER BY start_time DESC LIMIT 1000'
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in events])

@app.route('/api/latest_id')
def get_latest_id():
    conn = get_db_connection()
    # Extremely fast query to just get the highest ID
    result = conn.execute('SELECT MAX(id) as max_id FROM noise_events').fetchone()
    conn.close()
    return jsonify({'latest_id': result['max_id'] or 0})

@app.route('/api/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/api/tag/<int:event_id>', methods=['POST'])
def update_tag(event_id):
    data = request.json
    new_tag = data.get('tag')
    conn = get_db_connection()
    conn.execute('UPDATE noise_events SET tag = ? WHERE id = ?', (new_tag, event_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    conn = get_db_connection()
    event = conn.execute('SELECT file_path FROM noise_events WHERE id = ?', (event_id,)).fetchone()
    if event:
        file_path = os.path.join(AUDIO_DIR, event['file_path'])
        if os.path.exists(file_path):
            os.remove(file_path)
    
    conn.execute('DELETE FROM noise_events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.json
        if 'threshold' in data:
            conn.execute('UPDATE config SET value = ? WHERE key = ?', (data['threshold'], 'threshold_dbfs'))
        if 'active' in data:
            conn.execute('UPDATE config SET value = ? WHERE key = ?', (1.0 if data['active'] else 0.0, 'listener_active'))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    else:
        threshold = conn.execute("SELECT value FROM config WHERE key='threshold_dbfs'").fetchone()
        active_row = conn.execute("SELECT value FROM config WHERE key='listener_active'").fetchone()
        active_val = bool(active_row['value']) if active_row else True
        conn.close()
        return jsonify({
            'threshold': threshold['value'], 
            'active': active_val
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
