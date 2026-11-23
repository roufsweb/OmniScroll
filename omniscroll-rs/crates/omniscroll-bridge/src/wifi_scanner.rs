//! Native Windows Wi-Fi network scanner.
//! Scans for available 2.4 GHz and 5 GHz 802.11 BSSIDs using Windows netsh with hidden window flags.

use std::process::Command;
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WifiNetwork {
    pub ssid: String,
    pub signal: u8,
    pub authentication: String,
    pub bssid: String,
}

pub struct WifiScanner;

impl WifiScanner {
    /// Scans for nearby Wi-Fi networks without spawning a console window.
    pub fn scan_networks() -> Vec<WifiNetwork> {
        let mut cmd = Command::new("netsh");
        cmd.args(["wlan", "show", "networks", "mode=bssid"]);
        cmd.creation_flags(CREATE_NO_WINDOW);

        let output = match cmd.output() {
            Ok(out) => String::from_utf8_lossy(&out.stdout).to_string(),
            Err(_) => return Vec::new(),
        };

        Self::parse_netsh_output(&output)
    }

    /// Asynchronously scans for nearby Wi-Fi networks using Tokio.
    pub async fn scan_networks_async() -> Vec<WifiNetwork> {
        tokio::task::spawn_blocking(Self::scan_networks)
            .await
            .unwrap_or_default()
    }

    /// Parses the raw output from `netsh wlan show networks mode=bssid`.
    pub fn parse_netsh_output(raw: &str) -> Vec<WifiNetwork> {
        let mut networks = Vec::new();
        let mut cur_ssid = String::new();
        let mut cur_auth = String::new();
        let mut cur_bssid = String::new();
        let mut cur_signal = 0u8;

        for line in raw.lines() {
            let trimmed = line.trim();

            if trimmed.starts_with("SSID") && trimmed.contains(':') {
                if !cur_ssid.is_empty() {
                    networks.push(WifiNetwork {
                        ssid: cur_ssid.clone(),
                        signal: cur_signal,
                        authentication: cur_auth.clone(),
                        bssid: cur_bssid.clone(),
                    });
                }
                let parts: Vec<&str> = trimmed.splitn(2, ':').collect();
                cur_ssid = parts.get(1).unwrap_or(&"").trim().to_string();
                cur_auth.clear();
                cur_bssid.clear();
                cur_signal = 0;
            } else if trimmed.starts_with("Authentication") || trimmed.starts_with("Auth") {
                if let Some(pos) = trimmed.find(':') {
                    cur_auth = trimmed[pos + 1..].trim().to_string();
                }
            } else if trimmed.starts_with("BSSID") {
                if let Some(pos) = trimmed.find(':') {
                    cur_bssid = trimmed[pos + 1..].trim().to_string();
                }
            } else if trimmed.starts_with("Signal") {
                if let Some(pos) = trimmed.find(':') {
                    let sig_str = trimmed[pos + 1..].trim().trim_end_matches('%');
                    cur_signal = sig_str.parse::<u8>().unwrap_or(0);
                }
            }
        }

        if !cur_ssid.is_empty() {
            networks.push(WifiNetwork {
                ssid: cur_ssid,
                signal: cur_signal,
                authentication: cur_auth,
                bssid: cur_bssid,
            });
        }

        // De-duplicate by SSID keeping highest signal strength
        let mut deduped: Vec<WifiNetwork> = Vec::new();
        for net in networks {
            if net.ssid.is_empty() {
                continue;
            }
            if let Some(existing) = deduped.iter_mut().find(|n| n.ssid == net.ssid) {
                if net.signal > existing.signal {
                    existing.signal = net.signal;
                    existing.bssid = net.bssid;
                }
            } else {
                deduped.push(net);
            }
        }

        // Sort descending by signal strength
        deduped.sort_by(|a, b| b.signal.cmp(&a.signal));
        deduped
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_netsh_sample() {
        let sample = r#"
SSID 1 : HomeNetwork_5G
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : 00:11:22:33:44:55
         Signal             : 88%
         Radio type         : 802.11ax
         Channel            : 36

SSID 2 : Guest_WiFi
    Network type            : Infrastructure
    Authentication          : Open
    Encryption              : None
    BSSID 1                 : AA:BB:CC:DD:EE:FF
         Signal             : 62%
         Radio type         : 802.11n
         Channel            : 6
"#;
        let nets = WifiScanner::parse_netsh_output(sample);
        assert_eq!(nets.len(), 2);
        assert_eq!(nets[0].ssid, "HomeNetwork_5G");
        assert_eq!(nets[0].signal, 88);
        assert_eq!(nets[0].authentication, "WPA2-Personal");
        assert_eq!(nets[1].ssid, "Guest_WiFi");
        assert_eq!(nets[1].signal, 62);
    }
}
