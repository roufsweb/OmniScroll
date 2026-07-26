import serial
import serial.tools.list_ports
import time
import sys

PORT = "COM17"
BAUD = 115200
DURATION = 15 # 15 seconds to give plenty of time

ports = [p.device for p in serial.tools.list_ports.comports() if p.device != 'COM1']
if PORT not in ports:
    if ports:
        PORT = ports[-1]
    else:
        print("No ports found.")
        sys.exit(1)

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
except Exception as e:
    print(f"Failed to open port: {e}")
    sys.exit(1)

print(f"\n==============================================")
print(f"RECORDING SPINNING ONLY (No Taps)")
print(f"==============================================")
print(f"Recording for {DURATION} seconds...")

start_time = time.time()
with open("log_spin_only.txt", "w") as f:
    while time.time() - start_time < DURATION:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                ts = time.time() - start_time
                out = f"[t={ts:05.2f}s] {line}"
                f.write(out + "\n")
                print(out)
        else:
            time.sleep(0.01)

ser.close()
print(f"\n[!] DONE RECORDING SPINNING ONLY.\n")
