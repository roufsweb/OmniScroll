import serial
import serial.tools.list_ports
import time
import sys

PORT = "COM17"
BAUD = 115200
DURATION = 20 # 20 seconds for a good mix

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
print(f"RECORDING: SPINNING + INTENTIONAL DOUBLE TAPS")
print(f"==============================================")
print(f"Recording for {DURATION} seconds...")
print(f"Instructions:")
print(f"1. Spin vigorously")
print(f"2. STOP the wheel for a half-second")
print(f"3. Double-tap to switch modes")
print(f"4. Repeat!\n")

start_time = time.time()
with open("log_mixed.txt", "w") as f:
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
print(f"\n[!] DONE RECORDING MIXED TEST.\n")
