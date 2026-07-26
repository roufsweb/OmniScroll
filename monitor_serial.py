import serial
import serial.tools.list_ports
import time
import sys

# Find active ports (ignore COM1 usually reserved)
ports = [p.device for p in serial.tools.list_ports.comports() if p.device != 'COM1']
if not ports:
    print("No COM ports found.")
    sys.exit(1)

port = ports[-1] # Usually the last plugged in device is the highest COM port
print(f"[*] Connecting to {port} at 115200 baud...")

try:
    ser = serial.Serial(port, 115200, timeout=1)
except Exception as e:
    print(f"[-] Failed to open {port}: {e}")
    sys.exit(1)

print("\n[+] Connected! Please perform the following actions over the next 20 seconds:")
print("  1. Leave it alone (baseline)")
print("  2. Spin the metal dial (interference test)")
print("  3. Double tap the touch wire (intentional tap)")
print("\nRecording...")

start_time = time.time()
with open("serial_log.txt", "w") as f:
    while time.time() - start_time < 20:
        try:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore')
                if line:
                    f.write(line)
                    print(line.strip())
            else:
                time.sleep(0.05)
        except Exception as e:
            print(f"Read error: {e}")
            break

ser.close()
print("\n[+] Done logging to serial_log.txt!")
