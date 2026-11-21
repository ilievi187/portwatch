# PortWatch

**Live Linux local ports & process manager** built with Python + Qt 6 (`PySide6`), featuring smooth hover glow effects and **live Omarchy theme synchronization**.

[![License: MIT](https://img.shields.io/badge/License-MIT-7376b7.svg)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Support-Buy%20Me%20a%20Coffee-FFDD00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/aurorauap)

## Features
- Live inspection of all listening TCP & UDP sockets (`ss -tulnpH` + `/proc` RAM & command line).
- Instant distinction between **Local** (`127.0.0.1`) and **LAN Exposed** (`0.0.0.0` / `::`) ports.
- 1-click **Open in Browser**, **Copy URL**, and **Kill Process (`SIGTERM`)**.
- Live 3-second auto-refresh toggle, search (`Ctrl+F`), and protocol filters.
- Adapts live to your active Omarchy theme (`colors.toml` + Hyprland rounding).

## Quick Start
```bash
git clone https://github.com/ilievi187/portwatch.git
cd portwatch
./run.sh
```

## License
[MIT License](LICENSE)
