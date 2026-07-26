import sys
import serial
import serial.tools.list_ports
import time

def main():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if not ports:
        print("[-] No serial ports found!")
        return

    port = ports[0]
    if len(sys.argv) > 1:
        port = sys.argv[1]
    elif "COM7" in ports:
        port = "COM7"
        
    print(f"[*] Starting serial monitor on {port} at 115200 baud...")
    print("[*] Go ahead and spin the wheel! (I will stream the output)")
    
    try:
        # Native USB often requires DTR/RTS to be asserted to start streaming
        with serial.Serial(port, 115200, timeout=0.1) as ser:
            while True:
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    print(line)
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
    except Exception as e:
        print(f"\n[-] Error: {e}")

if __name__ == '__main__':
    main()
