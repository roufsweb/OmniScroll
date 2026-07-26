import re

log_file = "deep_log.txt"
print(f"=== Deep Analysis of {log_file} ===\n")

with open(log_file) as f:
    raw_lines = f.readlines()

entries = []
for line in raw_lines:
    ts_match = re.match(r'\[t=([\d.]+)s\] (.*)', line.strip())
    if ts_match:
        t = float(ts_match.group(1))
        msg = ts_match.group(2)
        entries.append((t, msg))

# Parse all data types
telemetry = []
wheels = []
taps = []
ignores = []

for t, msg in entries:
    m = re.search(r'Touch Raw: (\d+).*Baseline: (\d+).*Delta: (\d+)', msg)
    if m:
        telemetry.append((t, int(m.group(1)), int(m.group(2)), int(m.group(3))))
    elif '[Wheel] dx' in msg:
        dm = re.search(r'dx: (-?\d+).*Accumulator: (-?\d+)', msg)
        if dm:
            wheels.append((t, int(dm.group(1)), int(dm.group(2))))
    elif 'Double Tap Detected' in msg:
        taps.append(t)
    elif 'Ignored' in msg:
        ignores.append(t)

print(f"Telemetry readings: {len(telemetry)}")
print(f"Wheel events:       {len(wheels)}")
print(f"Taps registered:    {len(taps)}  @ {[f't={t:.1f}s' for t in taps]}")
print(f"Taps ignored:       {len(ignores)} @ {[f't={t:.1f}s' for t in ignores]}")

# Find when wheel stopped moving
last_wheel_per_phase = {}
for t, dx, acc in wheels:
    phase = int(t)
    last_wheel_per_phase[phase] = t

# Print all telemetry readings with phase labels
print("\n--- All Telemetry Readings (with phase context) ---")
phases = {
    (0,7): "IDLE",
    (7,14): "SPIN",
    (14,17): "SETTLE",
    (17,22): "TAP",
    (22,30): "SPIN+TAP"
}
for t, raw, baseline, delta in telemetry:
    phase = "UNKNOWN"
    for (start,end), name in phases.items():
        if start <= t < end:
            phase = name
    print(f"  t={t:05.2f}s [{phase:9s}] Raw={raw:6d} Baseline={baseline:6d} Delta={delta:5d}")

# Find post-scroll gap analysis
print("\n--- Post-Scroll Gap Analysis (when did wheel stop vs when user tapped) ---")
for tap_t in taps + ignores:
    label = "REGISTERED" if tap_t in taps else "IGNORED"
    recent_wheels = [(t, dx) for t, dx, _ in wheels if tap_t - 0.5 < t < tap_t]
    if recent_wheels:
        last_w_t = recent_wheels[-1][0]
        gap = tap_t - last_w_t
        print(f"  Tap at t={tap_t:.2f}s [{label}] | Last wheel at t={last_w_t:.2f}s | Gap={gap*1000:.0f}ms")
    else:
        print(f"  Tap at t={tap_t:.2f}s [{label}] | No recent wheel events found")

# Baseline drift check
if telemetry:
    baselines = [(t, b) for t, _, b, _ in telemetry]
    print(f"\n--- Baseline Stability ---")
    print(f"  Start baseline: {baselines[0][1]}")
    print(f"  End baseline:   {baselines[-1][1]}")
    print(f"  Drift:          {baselines[-1][1] - baselines[0][1]}")
    
    # Check if baseline is tracking properly
    idle_readings = [(t, raw, delta) for t, raw, _, delta in telemetry if t < 7]
    print(f"\n  Idle readings (t<7s):")
    for t, raw, delta in idle_readings:
        healthy = "OK" if delta < 100 else "HIGH - baseline not tracking!"
        print(f"    t={t:.2f}s Raw={raw} Delta={delta} [{healthy}]")

print("\n=== ROOT CAUSE SUMMARY ===")
idle_deltas = [d for t,_,_,d in telemetry if t < 7]
if idle_deltas and max(idle_deltas) > 200:
    print("! BASELINE NOT TRACKING: Idle delta is too high. The baseline froze early.")
    print("  Fix: Remove the <30 gate, let EMA always track when below threshold.")
    
print("! POST-SPIN HIGH STATE: After spinning, sensor reads high for ~300ms.")
print("  Fix: Extend reset() call to persist for 400ms after last scroll event.")

tap_phase_deltas = [d for t,_,_,d in telemetry if 17 <= t < 22]
if tap_phase_deltas:
    if min(tap_phase_deltas) < 1100:
        print(f"! THRESHOLD MAY BE TOO HIGH: Min tap delta={min(tap_phase_deltas)} but threshold=1100")
        suggested = int(min(tap_phase_deltas) * 0.7)
        print(f"  Suggested threshold: {suggested}")
    else:
        print(f"OK: Tap deltas ({min(tap_phase_deltas)}-{max(tap_phase_deltas)}) all above threshold 1100")
