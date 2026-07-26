#!/usr/bin/env python3
import sys
import time
import subprocess
import serial
import serial.tools.list_ports

ARDUINO_CLI = r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"

# FQBN for Lolin ESP32-S2 Mini with Hardware CDC disabled so TinyUSB HID can work
FQBN = "esp32:esp32:lolin_s2_mini:CDCOnBoot=dis_cdc,PartitionScheme=huge_app,EraseFlash=all"
SKETCH_PATH = r"e:\rouf\hardware-project\OmniScroll"
TARGET_PORT_OVERRIDE = None

for idx, arg in enumerate(sys.argv):
    if arg == "--port" and idx + 1 < len(sys.argv):
        TARGET_PORT_OVERRIDE = sys.argv[idx + 1]
    elif not arg.startswith("--") and idx > 0 and sys.argv[idx-1] != "--port" and sys.argv[idx] != sys.argv[0]:
        SKETCH_PATH = arg

def get_ports():
    return [port.device for port in serial.tools.list_ports.comports()]

def reset_to_bootloader(port):
    print(f"[*] Toggling 1200 bps reset on {port}...")
    try:
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = 1200
        ser.dtr = True
        ser.rts = True
        ser.open()
        time.sleep(0.2)
        ser.close()
        print("[+] Reset signal sent successfully.")
        return True
    except Exception as e:
        print(f"[-] Failed to send reset signal: {e}")
        return False

def main():
    ports_before = get_ports()
    if not ports_before:
        print("[-] No serial ports detected! Please verify the ESP32-S3 is connected.")
        sys.exit(1)
    
    target_port = ports_before[0]
    if TARGET_PORT_OVERRIDE and TARGET_PORT_OVERRIDE in ports_before:
        target_port = TARGET_PORT_OVERRIDE
    elif len(ports_before) > 1:
        print(f"[*] Detected multiple ports: {ports_before}")
        if "COM7" in ports_before:
            target_port = "COM7"
        elif "COM21" in ports_before:
            target_port = "COM21"
        elif "COM13" in ports_before:
            target_port = "COM13"
        print(f"[*] Selected port: {target_port}")
    else:
        print(f"[+] Found device on port: {target_port}")
    
    no_reset = "--no-reset" in sys.argv
    if no_reset:
        print("[*] Skipping reset as requested (--no-reset)")
        reset_success = False
    else:
        reset_success = reset_to_bootloader(target_port)
    
    new_port = target_port
    if reset_success:
        print("[*] Waiting for USB re-enumeration...")
        time.sleep(2.5)
        
        ports_after = get_ports()
        if not ports_after:
            print("[-] No ports found after reset!")
            sys.exit(1)
            
        if target_port in ports_after:
            new_port = target_port
        else:
            diff = list(set(ports_after) - set(ports_before))
            if diff:
                new_port = diff[0]
            else:
                new_port = ports_after[0]
    else:
        print("[*] Port reset failed/skipped. Proceeding to direct upload...")
            
    print(f"[+] Using port: {new_port}")

    cmd = [
        ARDUINO_CLI, "compile",
        "--fqbn", FQBN,
        "--upload",
        "-p", new_port,
        SKETCH_PATH
    ]
    
    print(f"[*] Running compile and upload...")
    print(f"[*] Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        hash_verified = False
        for line in process.stdout:
            print(line, end="")
            if "Hash of data verified." in line:
                hash_verified = True
                
        process.wait()
        
        print("-" * 60)
        if process.returncode == 0 or (process.returncode == 1 and hash_verified):
            print("[+] OmniScroll Upload completed successfully!")
        else:
            print(f"[-] Upload failed with exit code: {process.returncode}")
            sys.exit(process.returncode)
            
    except Exception as e:
        print(f"[-] Execution error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
