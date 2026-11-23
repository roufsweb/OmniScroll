"""
wifi_scanner.py — High-performance Windows Wi-Fi network scanner for OmniScroll.
Extracts SSIDs, signal percentages, authentication modes, and crucially
validates 2.4 GHz compatibility for the ESP32-S2 microcontroller.
"""
import re
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def scan_wifi_networks() -> list:
    """
    Executes Windows native `netsh wlan show networks mode=bssid`
    and parses available Wi-Fi networks with signal strength and frequency band.
    Returns a sorted list of network dicts:
    [
        {
            "ssid": str,
            "signal": int (0-100),
            "band": str ("2.4 GHz" or "5 GHz"),
            "auth": str,
            "compatible": bool (True for 2.4 GHz, False for 5 GHz only)
        }, ...
    ]
    """
    networks = {}
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        proc = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
            timeout=5
        )

        output = proc.stdout
        current_ssid = None
        current_auth = "Unknown"

        for line in output.splitlines():
            line_str = line.strip()

            # Detect SSID header (e.g., "SSID 1 : MyNetwork")
            ssid_match = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line_str)
            if ssid_match:
                current_ssid = ssid_match.group(1).strip()
                current_auth = "Unknown"
                continue

            if not current_ssid:
                continue

            # Detect Authentication (e.g., "Authentication : WPA2-Personal")
            auth_match = re.match(r"^Authentication\s*:\s*(.*)$", line_str)
            if auth_match:
                current_auth = auth_match.group(1).strip()
                continue

            # Detect Band (e.g., "Band : 2.4 GHz" or "Band : 5 GHz")
            band_match = re.match(r"^Band\s*:\s*(.*)$", line_str)
            if band_match:
                band = band_match.group(1).strip()
                if current_ssid in networks:
                    # If this BSSID is 2.4GHz, mark the SSID as having 2.4GHz support
                    if "2.4" in band:
                        networks[current_ssid]["band"] = "2.4 GHz"
                        networks[current_ssid]["compatible"] = True
                continue

            # Detect Signal (e.g., "Signal : 82%")
            sig_match = re.match(r"^Signal\s*:\s*(\d+)%", line_str)
            if sig_match:
                sig_val = int(sig_match.group(1))
                if current_ssid not in networks:
                    networks[current_ssid] = {
                        "ssid": current_ssid,
                        "signal": sig_val,
                        "band": "Unknown",
                        "auth": current_auth,
                        "compatible": True  # Default to true until verified
                    }
                else:
                    # Keep maximum signal among BSSIDs
                    if sig_val > networks[current_ssid]["signal"]:
                        networks[current_ssid]["signal"] = sig_val
                continue

        # Second pass to finalize band compatibility
        result = []
        for ssid, info in networks.items():
            if not ssid:
                continue
            # If band wasn't explicitly detected, infer from common naming or mark 2.4 GHz
            if info["band"] == "Unknown":
                if "_5G" in ssid.upper() or "5GHZ" in ssid.upper():
                    info["band"] = "5 GHz"
                    info["compatible"] = False
                else:
                    info["band"] = "2.4 GHz"
                    info["compatible"] = True
            elif "5" in info["band"] and "2.4" not in info["band"]:
                info["compatible"] = False

            result.append(info)

        # Sort by signal strength descending (compatible networks prioritized)
        result.sort(key=lambda x: (x["compatible"], x["signal"]), reverse=True)
        return result

    except Exception as e:
        logging.error(f"Error scanning Wi-Fi networks: {e}")
        return []


if __name__ == "__main__":
    nets = scan_wifi_networks()
    print(f"Scanned {len(nets)} Wi-Fi networks:")
    for n in nets:
        compat = "[OK] 2.4GHz (Compatible)" if n['compatible'] else "[X] 5GHz Only (Incompatible)"
        print(f"  [{n['signal']:3d}%] {n['ssid']:<24} {n['band']:<8} {compat}")
