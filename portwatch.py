"""PortWatch backend — inspects live listening TCP/UDP ports and owning processes on Linux."""

from __future__ import annotations

import os
import re
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PortEntry:
    proto: str
    address: str
    port: int
    pid: int | None
    process: str
    cmdline: str
    rss_mb: float
    exposed: bool

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.address in ("0.0.0.0", "*", "::", "[::]") else self.address.strip("[]")
        scheme = "https" if self.port in (443, 8443) else "http"
        return f"{scheme}://{host}:{self.port}"


def _read_proc_info(pid: int) -> tuple[str, float]:
    cmdline = ""
    rss_mb = 0.0
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        cmdline = " ".join(part.decode("utf-8", errors="replace") for part in raw.split(b"\x00") if part)
    except OSError:
        pass
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("VmRSS:"):
                kb = int(line.split()[1])
                rss_mb = round(kb / 1024.0, 1)
                break
    except (OSError, ValueError, IndexError):
        pass
    return cmdline, rss_mb


def list_listening_ports() -> list[PortEntry]:
    """Return all currently listening TCP and UDP sockets via `ss -tulnp`."""
    res = subprocess.run(["ss", "-tulnpH"], capture_output=True, text=True, timeout=5)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "Failed to run `ss -tulnpH`.")

    entries: list[PortEntry] = []
    seen: set[tuple[str, str, int, int | None]] = set()

    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0].upper()
        local = parts[4]

        # Split host:port (handles IPv6 [::]:8080 and *:8080 and 127.0.0.1%lo:53)
        if local.rfind(":") == -1:
            continue
        addr_part, port_str = local.rsplit(":", 1)
        if not port_str.isdigit():
            continue
        port = int(port_str)
        addr = addr_part.split("%", 1)[0]

        pid: int | None = None
        proc_name = "system / root"
        rest = " ".join(parts[5:])
        m = re.search(r'"([^"]+)",pid=(\d+)', rest)
        if m:
            proc_name = m.group(1)
            pid = int(m.group(2))

        key = (proto, addr, port, pid)
        if key in seen:
            continue
        seen.add(key)

        cmdline, rss_mb = _read_proc_info(pid) if pid else ("", 0.0)
        exposed = addr in ("0.0.0.0", "*", "::", "[::]")

        entries.append(
            PortEntry(
                proto="TCP" if proto.startswith("TCP") else "UDP",
                address=addr,
                port=port,
                pid=pid,
                process=proc_name,
                cmdline=cmdline,
                rss_mb=rss_mb,
                exposed=exposed,
            )
        )

    entries.sort(key=lambda e: (e.port, e.proto, e.process.lower()))
    return entries


def kill_process(pid: int) -> str:
    """Gracefully terminate a process with SIGTERM."""
    try:
        os.kill(pid, signal.SIGTERM)
        return f"Sent SIGTERM to PID {pid}"
    except PermissionError:
        raise RuntimeError(f"Permission denied terminating PID {pid} (owned by another user/root).")
    except ProcessLookupError:
        return f"Process {pid} already exited."
