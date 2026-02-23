# Intelbras AMT-8000 Home Assistant Integration

Complete Home Assistant integration for the **Intelbras AMT-8000** alarm system via the iSec2 (ISECNet v2) protocol.

## Features

- **Alarm Control Panel** — Main panel with Arm Away, Arm Home (Stay), Arm Night, Disarm, and Panic/Trigger
- **Per-Partition Control** — Individual alarm panels for each enabled partition
- **Zone Sensors** — Binary sensors for every enabled zone (open/violated detection)
- **Zone Diagnostics** — Tamper and low battery binary sensors per zone
- **System Sensors** — Siren active, system tamper, zones firing
- **Battery Monitoring** — Battery level percentage and status sensors
- **Device Info** — Model name and firmware version
- **Fully Async** — All communication is non-blocking via `asyncio`
- **Robust Error Handling** — Automatic reconnection with exponential backoff
- **HACS Compatible** — Install via HACS custom repository
- **Portuguese-BR Translations** — Localized UI for Brazilian users

## Requirements

- Intelbras AMT-8000 alarm system with Ethernet module
- The alarm must be reachable via TCP on your network (default port: **9009**)
- Remote configuration password (4 or 6 digits)
- Home Assistant 2024.1.0 or newer

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **⋮ (menu)** → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for "Intelbras AMT-8000" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/amt8000` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **"Intelbras AMT-8000"**
3. Enter:
   - **Host**: IP address of your AMT-8000
   - **Port**: TCP port (default: 9009)
   - **Password**: Remote configuration password (4 or 6 digits)
   - **Number of zones**: How many zones to monitor (default: 48)
   - **Number of partitions**: How many partition panels to create (default: 4)
   - **Away partitions**: Comma-separated partition numbers for Away mode (`0` = all)
   - **Stay/Home partitions**: Comma-separated partition numbers for Home mode (leave empty to disable)
   - **Night partitions**: Comma-separated partition numbers for Night mode (leave empty to disable)

### Partition Configuration Examples

**Simple setup (arm everything):**
- Away: `0`
- Stay: _(empty)_
- Night: _(empty)_

**3-partition setup:**
- Away: `0` (all)
- Stay: `2` (outside sensors only)
- Night: `2,3` (outside sensors + access points)

## Entities Created

| Entity Type | Name | Description |
|---|---|---|
| `alarm_control_panel` | Alarm | Main alarm panel (arm/disarm/trigger) |
| `alarm_control_panel` | Partition N | Per-partition arm/disarm |
| `binary_sensor` | Zone N | Zone open/violated status |
| `binary_sensor` | Zone N Tamper | Zone tamper detection |
| `binary_sensor` | Zone N Battery | Zone wireless sensor battery |
| `binary_sensor` | Siren | Siren active status |
| `binary_sensor` | System Tamper | System tamper status |
| `binary_sensor` | Zones Firing | Any zones currently firing |
| `sensor` | Battery Level | System battery percentage |
| `sensor` | Battery Status | Battery status text |
| `sensor` | Model | Alarm model name |
| `sensor` | Firmware Version | Firmware version |

## Protocol Details

This integration communicates with the AMT-8000 via the **iSec2 / ISECNet v2** protocol over TCP. It's the same protocol used by the Intelbras mobile app and monitoring software.

The integration polls the alarm every 15 seconds by default and creates a fresh TCP connection for each operation, which avoids the connection-stale issues that plague persistent connections.

## Acknowledgments

- [merencia/amt8000-hass-integration](https://github.com/merencia/amt8000-hass-integration) — Original integration
- [caarlos0/homekit-amt8000](https://github.com/caarlos0/homekit-amt8000) — Go HomeKit bridge (protocol reference)
- [elvis-epx/alarme-intelbras](https://github.com/elvis-epx/alarme-intelbras) — Protocol documentation

## License

MIT License
