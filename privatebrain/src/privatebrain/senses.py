"""Senses: a continuously updated view of the brain's own world, from ordinary code.

Each sense reads something cheap (the clock, /proc, the disk, a TCP connect) and returns a
reading. Events are raised on *changes* (the remote model became unreachable, the disk fell
below its floor), not on every reading, so the journal records what happened rather than a
stream of samples. No sense calls a model.
"""

from __future__ import annotations

import os
import shutil
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from . import llm
from .events import event
from .home import Home

PROVIDER_URL = os.environ.get("PRIVATEBRAIN_PROVIDER_URL",
                              llm.PROVIDER.base_url + "/" if llm.PROVIDER.http else "https://api.anthropic.com/")
DISK_FLOOR_MB = 200
MEM_FLOOR_MB = 128
CLOCK_JUMP_S = 120


# --- probes (injectable, so tests and demos can cut a connection) ------------------------------

def _hostport(url: str, default_port: int) -> tuple[str, int]:
    u = urllib.parse.urlsplit(url if "//" in url else f"//{url}")
    return u.hostname or "", u.port or default_port


def network_probe(timeout: float = 3.0) -> bool:
    """Can this machine open a TCP connection to its first hop: the HTTPS proxy if one is
    configured, otherwise the provider itself? False means no usable network at all."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    host, port = _hostport(proxy, 80) if proxy else _hostport(PROVIDER_URL, 443)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def provider_probe(timeout: float = 3.0) -> bool:
    """Does the model provider answer HTTP at all? Any HTTP status counts (a 401 or 404 still
    proves it is up); only a failure to get a response means it is unreachable. Free: no
    model call, no credentials sent."""
    try:
        urllib.request.urlopen(urllib.request.Request(PROVIDER_URL, method="HEAD"), timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def cli_probe() -> bool:
    """Is there a way to make a model call: the `claude` CLI, or an API key for an HTTP provider."""
    if llm.PROVIDER.http:
        return bool(llm.PROVIDER.api_key) or not llm.PROVIDER.needs_key
    return shutil.which("claude") is not None


@dataclass
class Probes:
    network: Callable[[], bool] = network_probe
    provider: Callable[[], bool] = provider_probe
    cli: Callable[[], bool] = cli_probe


# --- readings ----------------------------------------------------------------------------------

def _proc_kb(path: str, key: str) -> int | None:
    try:
        with open(path, encoding="ascii") as f:
            for line in f:
                if line.startswith(key + ":"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def internal(home: Home, started: float) -> dict:
    rss = _proc_kb("/proc/self/status", "VmRSS")
    avail = _proc_kb("/proc/meminfo", "MemAvailable")
    try:
        disk_free = shutil.disk_usage(home.root).free // 2**20
    except OSError:
        disk_free = None
    probe = home.root / ".write-probe"
    try:
        probe.write_text("ok", encoding="ascii")
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    try:
        load1 = round(os.getloadavg()[0], 2)
    except OSError:
        load1 = None
    return {
        "pid": os.getpid(),
        "uptime_s": round(time.monotonic() - started, 1),
        "rss_mb": rss // 1024 if rss else None,
        "load1": load1,
        "cpus": os.cpu_count(),
        "mem_available_mb": avail // 1024 if avail else None,
        "disk_free_mb": disk_free,
        "storage_writable": writable,
        "local_model": "not installed",
    }


def connectivity(probes: Probes, *, breaker_open: bool, forced_offline: bool) -> dict:
    net = probes.network()
    provider = net and probes.provider()
    cli = probes.cli()
    reasons = []
    if forced_offline:
        reasons.append("operator_disconnected")
    if not net:
        reasons.append("network_unavailable")
    elif not provider:
        reasons.append("provider_unreachable")
    if not cli:
        reasons.append("model_client_missing")
    if breaker_open:
        reasons.append("recent_calls_failing")
    return {"network": net, "provider": provider, "model_client": cli,
            "remote_model": not reasons, "reasons": reasons,
            "probed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def mode_of(conn: dict) -> str:
    """online: the remote model can be used. degraded: the network works but the model does
    not. offline: no network. The substrate works the same in all three; only model work waits."""
    if conn["remote_model"]:
        return "online"
    return "offline" if not conn["network"] or "operator_disconnected" in conn["reasons"] else "degraded"


# --- the sensorium: readings plus change detection ---------------------------------------------

@dataclass
class Senses:
    home: Home
    probes: Probes = field(default_factory=Probes)
    probe_every_s: float = 30.0
    forced_offline: bool = False
    started: float = field(default_factory=time.monotonic)
    _last_conn: dict | None = None
    _last_probe: float = -1e9
    _last_breaker: bool = False
    _last_wall: float | None = None
    _last_mono: float | None = None

    def read(self, prev: dict, *, breaker_open: bool, force_probe: bool = False) -> tuple[dict, list[dict]]:
        """One reading of every sense, and the events for whatever changed since `prev`
        (the previous reading, which the loop persists across restarts)."""
        events: list[dict] = []
        mono, wall = time.monotonic(), time.time()

        # temporal
        if self._last_mono is not None:
            drift = (wall - self._last_wall) - (mono - self._last_mono)
            if abs(drift) > CLOCK_JUMP_S:
                events.append(event("clock_jump", source="temporal", severity="warning",
                                    drift_s=round(drift, 1)))
        self._last_wall, self._last_mono = wall, mono
        temporal = {"now": datetime.now(timezone.utc).isoformat(timespec="seconds")}

        # internal
        body = internal(self.home, self.started)
        p = prev.get("internal") or {}
        low = [k for k, floor in (("disk_free_mb", DISK_FLOOR_MB), ("mem_available_mb", MEM_FLOOR_MB))
               if body[k] is not None and body[k] < floor]
        body["low"] = low
        if low and not p.get("low"):
            events.append(event("resources_low", source="internal", severity="warning",
                                resources=low, **{k: body[k] for k in low}))
        elif not low and p.get("low"):
            events.append(event("resources_ok", source="internal"))
        if not body["storage_writable"] and p.get("storage_writable", True):
            events.append(event("storage_unwritable", source="internal", severity="critical",
                                path=str(self.home.root)))
        elif body["storage_writable"] and p.get("storage_writable") is False:
            events.append(event("storage_writable", source="internal"))

        # connectivity, probed at most every `probe_every_s` unless something forces it
        if force_probe or breaker_open != self._last_breaker or mono - self._last_probe >= self.probe_every_s:
            self._last_conn = connectivity(self.probes, breaker_open=breaker_open,
                                           forced_offline=self.forced_offline)
            self._last_probe, self._last_breaker = mono, breaker_open
        conn = dict(self._last_conn)
        conn["mode"] = mode_of(conn)
        pc = prev.get("connectivity") or {}
        if pc.get("remote_model", True) and not conn["remote_model"]:
            events.append(event("remote_model_unavailable", source="connectivity", severity="warning",
                                affected_capability="remote_reasoning", reasons=conn["reasons"]))
        elif pc.get("remote_model") is False and conn["remote_model"]:
            events.append(event("remote_model_available", source="connectivity",
                                affected_capability="remote_reasoning"))
        if pc.get("network", True) and not conn["network"]:
            events.append(event("network_lost", source="connectivity", severity="warning"))
        elif pc.get("network") is False and conn["network"]:
            events.append(event("network_restored", source="connectivity"))
        if pc.get("mode") and pc["mode"] != conn["mode"]:
            events.append(event("mode_changed", source="connectivity", severity="info",
                                **{"from": pc["mode"], "to": conn["mode"]}))

        return {"temporal": temporal, "internal": body, "connectivity": conn}, events
