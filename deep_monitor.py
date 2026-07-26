import serial
import serial.tools.list_ports
import time
import sys
import re
from collections import defaultdict

PORT = "COM17"
BAUD = 115200
DURATION = 30

# Try to auto-detect if not found
ports = [p.device for p in serial.tools.list_ports.comports() if p.device != 'COM1']
print(f"[*] Available ports: {ports}")

if PORT not in ports:
    # Try the last available port
    if ports:
        PORT = ports[-1]
        print(f"[!] Falling back to {PORT}")
    else:
        print("No ports found.")
        sys.exit(1)

print(f"[*] Connecting to {PORT} at {BAUD} baud...")
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
except Exception as e:
    print(f"[-] Failed: {e}")
    sys.exit(1)

print(f"""
[+] Connected! Recording for {DURATION} seconds.

IMPORTANT - Please do the following in order:
  1.  0-7s:  DO NOTHING. Just let it sit idle.
  2.  7-14s: SPIN the wheel left and right vigorously.
  3.  14-17s: STOP. Let it settle.
  4.  17-22s: Do 3 clean DOUBLE TAPS with a clear pause between each.
  5.  22-30s: SCROLL again then immediately try to double tap.

Recording...
""")

lines = []
start_time = time.time()
log_path = "deep_log.txt"

with open(log_path, "w") as f:
    while time.time() - start_time < DURATION:
        try:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    ts = time.time() - start_time
                    tagged = f"[t={ts:05.2f}s] {line}"
                    f.write(tagged + "\n")
                    lines.append((ts, line))
                    print(tagged)
            else:
                time.sleep(0.01)
        except Exception as e:
            print(f"Read error: {e}")
            break

ser.close()
print(f"\n[+] Done! Saved to {log_path}")
print("\n--- DEEP ANALYSIS ---")

# Analyze telemetry readings
telemetry = [(t, int(m.group(1)), int(m.group(2)), int(m.group(3)))
             for t, l in lines
             if (m := re.search(r'Touch Raw: (\d+).*Baseline: (\d+).*Delta: (\d+)', l))]

taps = [(t, l) for t, l in lines if 'Double Tap' in l]
ignored = [(t, l) for t, l in lines if 'Ignored' in l]
scrolls = [(t, l) for t, l in lines if '[Wheel] dx' in l]

print(f"\nTotal telemetry snapshots: {len(telemetry)}")
if telemetry:
    deltas = [d for _, _, _, d in telemetry]
    print(f"Delta range: min={min(deltas)}, max={max(deltas)}, avg={sum(deltas)//len(deltas)}")

print(f"\nTotal wheel movement events: {len(scrolls)}")
print(f"Double taps REGISTERED: {len(taps)}")
print(f"Double taps IGNORED (lockout): {len(ignored)}")

if taps:
    print("\nDouble tap timestamps:")
    for t, l in taps:
        print(f"  t={t:.2f}s: {l}")
if ignored:
    print("\nIgnored tap timestamps:")
    for t, l in ignored:
        print(f"  t={t:.2f}s: {l}")

print("\n--- PHASE ANALYSIS ---")
idle_deltas = [d for t, _, _, d in telemetry if t < 7]
scroll_deltas = [d for t, _, _, d in telemetry if 7 <= t < 14]
settle_deltas = [d for t, _, _, d in telemetry if 14 <= t < 17]
tap_deltas = [d for t, _, _, d in telemetry if 17 <= t < 22]

if idle_deltas:
    print(f"Idle phase deltas:    min={min(idle_deltas):4d}  max={max(idle_deltas):4d}  avg={sum(idle_deltas)//len(idle_deltas):4d}")
if scroll_deltas:
    print(f"Scroll phase deltas:  min={min(scroll_deltas):4d}  max={max(scroll_deltas):4d}  avg={sum(scroll_deltas)//len(scroll_deltas):4d}")
if settle_deltas:
    print(f"Settle phase deltas:  min={min(settle_deltas):4d}  max={max(settle_deltas):4d}  avg={sum(settle_deltas)//len(settle_deltas):4d}")
if tap_deltas:
    print(f"Tap phase deltas:     min={min(tap_deltas):4d}  max={max(tap_deltas):4d}  avg={sum(tap_deltas)//len(tap_deltas):4d}")
