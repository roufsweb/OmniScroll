# OmniScroll Serial API & Communication Protocol

The OmniScroll uses a Web Serial API (via `USBCDC`) to communicate with the web-based control panel. The web UI is hosted completely client-side via `docs/index.html`.

All communication is line-based text, terminated by a newline (`\n`). 
Because we use `CDCOnBoot=dis_cdc`, the Serial stack works independently of the HID composite descriptors, meaning communication works even if the HID driver fails to enumerate on Windows.

## 1. Web to Device (Commands)

### SET Commands
Used to apply settings dynamically and save them to NVS (Non-Volatile Storage). These trigger a brief haptic click for confirmation.

**Global Parameters:**
* `SET:BRI:<0-100>` - Set global master LED brightness (percent).
* `SET:IDLE:<seconds>` - Set time before the LED dims (0 = disable).
* `SET:CPI:<0-3>` - Set MX8650 optical sensor DPI (0=400, 1=800, 2=1200, 3=1600).
* `SET:THR:<number>` - Set global capacitive touch threshold.

**Hardware White Balance Calibration:**
* `SET:CAL:R:<float>` - Red channel scaling (0.0 to 1.0)
* `SET:CAL:G:<float>` - Green channel scaling (0.0 to 1.0)
* `SET:CAL:B:<float>` - Blue channel scaling (0.0 to 1.0)

**Per-Mode Parameters (Max 8 Modes):**
Requires selecting the mode index first within the command chain.
* `SET:MODE:<0-7>,EN:<0|1>,CS:<HEX>,HP:<0-4>,INV:<0|1>,MTHR:<number>`
  * `EN` - Enabled boolean (1 = true)
  * `CS` - Color hex string (without `#`, e.g., `ff0000`)
  * `HP` - Haptic Profile (0=Click, 1=Thud, 2=Tick, 3=Soft, 4=Off)
  * `INV` - Invert scroll direction boolean (1 = true)
  * `MTHR` - Scroll threshold (higher = less sensitive, more wheel travel needed per tick)

*Commands can be chained:* `SET:BRI:100,MODE:0,CS:ff0000,HP:1`

### PREVIEW Commands
Identical to `SET:`, but does **not** save to NVS and does **not** trigger a haptic click. Used for real-time slider adjustments in the UI before committing.
* `PREVIEW:BRI:50`
* `PREVIEW:CAL:R:0.5`

### Query Commands
* `GET:STATUS` - Requests a rapid telemetry update.
* `GET:CONFIG` - Requests the complete configuration state (to populate the UI on load).
* `TEST:HAPTIC` - Plays the currently selected haptic profile once.

## 2. Device to Web (Responses)

### STATUS Response
Rapid telemetry sent when `GET:STATUS` is received, formatted as JSON string prefixed with `STATUS:`.
```json
STATUS:{"mode":"SCROLL","touch":1234,"baseline":0,"accX":10}
```

### CONFIG Response
Full state payload sent when `GET:CONFIG` is received, formatted as JSON string prefixed with `CONFIG:`.
```json
CONFIG:{
  "bri": 100,
  "idle": 30,
  "cpi": 1,
  "thr": 800,
  "cal_r": 0.100,
  "cal_g": 0.080,
  "cal_b": 1.000,
  "modes": [
    {"name":"SCROLL","en":1,"c":"0000ff","hp":0,"inv":0,"thr":10},
    {"name":"VOLUME","en":1,"c":"00ff00","hp":3,"inv":0,"thr":25}
  ]
}
```

### Async Notifications
* `MODE:<ModeName>` - Broadcast automatically when the user physically switches modes via capacitive double-tap or the physical hardware button. The web UI uses this to instantly highlight the active mode.
* `SCROLL:<delta>` - Broadcast in real time when the optical wheel rotates. The web control panel uses this to smoothly animate the physical 3D cylindrical metal rim live.
