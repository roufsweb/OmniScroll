import serial
import serial.tools.list_ports
import time
import re
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

PORT = "COM17"
BAUD = 115200

# Try to auto-detect if not found
ports = [p.device for p in serial.tools.list_ports.comports() if p.device != 'COM1']
if PORT not in ports and ports:
    PORT = ports[-1]

ser = None
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"[*] Connected to {PORT}")
except Exception as e:
    print(f"[-] Failed to open port: {e}")

def read_serial():
    global ser
    while True:
        if ser and ser.is_open:
            try:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Parse telemetry
                        m = re.search(r'Touch Raw: (\d+).*Baseline: (\d+).*Delta: (\d+).*Threshold: (\d+)', line)
                        if m:
                            data = {
                                "type": "telemetry",
                                "raw": int(m.group(1)),
                                "baseline": int(m.group(2)),
                                "delta": int(m.group(3)),
                                "threshold": int(m.group(4))
                            }
                            socketio.emit('telemetry', data)
                        else:
                            # Forward all other logs as events
                            socketio.emit('log', {"msg": line})
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"Read error: {e}")
                time.sleep(1)
        else:
            time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('set_threshold')
def handle_threshold(data):
    val = data.get('value')
    if val and ser and ser.is_open:
        cmd = f"T={val}\n"
        ser.write(cmd.encode('utf-8'))
        print(f"Sent: {cmd.strip()}")

if __name__ == '__main__':
    threading.Thread(target=read_serial, daemon=True).start()
    print("Starting Web UI on http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
