#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
APP_ID="portwatch"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="${HOME}/.local/share/applications"

mkdir -p "${ICON_DIR}" "${APPS_DIR}"
cp "${APP_DIR}/${APP_ID}.svg" "${ICON_DIR}/${APP_ID}.svg"
chmod +x "${APP_DIR}/run.sh" "${APP_DIR}/gui.py"

cat > "${APPS_DIR}/${APP_ID}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=PortWatch
Comment=Live Linux local ports & process manager
Exec=${APP_DIR}/run.sh
Icon=${APP_ID}
Categories=System;Network;Development;
Keywords=ports;tcp;udp;network;process;kill;localhost;
Terminal=false
StartupWMClass=portwatch
EOF

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${APPS_DIR}" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Installed PortWatch shortcut -> ${APPS_DIR}/${APP_ID}.desktop"
