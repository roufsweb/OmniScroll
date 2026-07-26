import serial
import serial.tools.list_ports
import time
import sys

PORT = "COM17"
BAUD = 115200
DURATION = 10

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

def record_phase(phase_name, filename):
    print(f"\n==============================================")
    print(f"GET READY: {phase_name}")
    print(f"Starting in 5 seconds...")
    print(f"==============================================")
    time.sleep(5)
    
    print(f"\n[+] RECORDING {phase_name} FOR {DURATION} SECONDS...")
    start_time = time.time()
    
    with open(filename, "w") as f:
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
    
    print(f"[!] DONE RECORDING {phase_name}.\n")

record_phase("PHASE 1: DOUBLE CLICKS ONLY (No Spinning)", "log_taps.txt")
record_phase("PHASE 2: SPINNING ONLY (No Taps)", "log_spin.txt")
record_phase("PHASE 3: SPINNING + DOUBLE CLICKS", "log_mixed.txt")

ser.close()
print("All phases complete! Logs saved to log_taps.txt, log_spin.txt, and log_mixed.txt")
