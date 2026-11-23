#!/usr/bin/env python3
"""
OmniScroll Lab Uploader — Multi-Window Multitasking Test Bench
Flashes the isolated test firmware without modifying main project files.
"""
import sys
import os
import time
import subprocess
import serial
import serial.tools.list_ports

ARDUINO_CLI = r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"
FQBN        = "esp32:esp32:lolin_s2_mini:CDCOnBoot=dis_cdc,PartitionScheme=huge_app,EraseFlash=none"
SKETCH_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware")

USB_BUILD_PROPS = [
    "--build-property", r'build.extra_flags=-DUSB_PRODUCT=\"OmniScroll-Lab\" -DUSB_MANUFACTURER=\"OmniScroll\"',
]

TARGET_PORT = None
for idx, arg in enumerate(sys.argv):
    if arg == "--port" and idx + 1 < len(sys.argv):
        TARGET_PORT = sys.argv[idx + 1]


def get_ports():
    ports = serial.tools.list_ports.comports()
    valid = []
    for p in ports:
        hwid = str(p.hwid).upper()
        desc = str(p.description).upper()
        if "BTHENUM" in hwid or "BLUETOOTH" in desc:
            continue
        valid.append(p)
    espressif = [p.device for p in valid if p.vid == 0x303A or "303A" in str(p.hwid).upper()]
    if espressif:
        return espressif + [p.device for p in valid if p.device not in espressif]
    return [p.device for p in valid]


def reset_into_bootloader(port):
    print(f"[*] Triggering 1200-bps reset on {port}...")
    try:
        ser = serial.Serial(port, 1200)
        ser.close()
        time.sleep(1.8)
        return True
    except Exception as e:
        print(f"[-] Reset failed: {e}")
        return False


def wait_for_port(port, timeout=30):
    print(f"[*] Waiting for {port}...")
    for _ in range(timeout):
        if port in get_ports():
            print(f"[+] Found {port}!")
            time.sleep(2)
            return True
        time.sleep(1)
    return False


def main():
    if "--compile-only" in sys.argv:
        print("[*] Compiling test sketch...")
        cmd = [
            ARDUINO_CLI, "compile",
            "--fqbn", FQBN,
        ] + USB_BUILD_PROPS + [SKETCH_DIR]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
        process.wait()
        if process.returncode == 0:
            print("[+] Compilation successful!")
        else:
            print("[-] Compilation failed!")
            sys.exit(1)
        return

    # Upload routine
    port = TARGET_PORT
    if not port:
        ports = get_ports()
        if ports:
            port = ports[0]
            print(f"[+] Using detected port: {port}")
        else:
            print("[*] Waiting up to 90s for ESP32-S2 connection / Download Mode...")
            print("[*] (Hold '0' [BOOT], tap 'RST', then release '0' if needed)")
            found = False
            for _ in range(180):
                p = get_ports()
                if p:
                    port = p[0]
                    print(f"\n[+] Detected {port}!")
                    found = True
                    time.sleep(1.0)
                    break
                print(".", end="", flush=True)
                time.sleep(0.5)
            if not found:
                print("\n[-] No serial ports found.")
                sys.exit(1)

    # Check if port is already in bootloader mode (PID 0x2)
    already_in_bootloader = False
    for p in serial.tools.list_ports.comports():
        if p.device == port and p.pid == 0x2:
            already_in_bootloader = True
            break

    if already_in_bootloader or "--no-reset" in sys.argv:
        print(f"[*] Port {port} is in Bootloader / Download Mode. Skipping reset.")
    else:
        reset_into_bootloader(port)
        time.sleep(1.5)
        ports_after = get_ports()
        if ports_after:
            port = ports_after[0]
            print(f"[*] Post-reset active port: {port}")

    print(f"[*] Compiling & Flashing test firmware to {port}...")
    cmd = [
        ARDUINO_CLI, "compile",
        "--fqbn", FQBN,
        "--upload",
        "-p", port,
    ] + USB_BUILD_PROPS + [SKETCH_DIR]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    hash_ok = False
    for line in process.stdout:
        print(line, end="")
        if "Hash of data verified." in line:
            hash_ok = True
    process.wait()

    if process.returncode == 0 or (process.returncode == 1 and hash_ok):
        print("\n=======================================================")
        print("  ✓ OmniScroll Multi-Window Lab Firmware Uploaded!")
        print("  Double-tap capacitive top plate in middle to cycle modes.")
        print("=======================================================")
    else:
        print(f"\n[-] Flash failed with code {process.returncode}")
        sys.exit(process.returncode)


if __name__ == "__main__":
    main()
