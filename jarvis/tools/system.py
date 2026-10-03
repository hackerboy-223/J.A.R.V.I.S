from __future__ import annotations

import os
import platform
import socket
import time

import psutil


def system_status(_: dict) -> dict:
    vm = psutil.virtual_memory()
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_percent": psutil.cpu_percent(interval=0.15),
        "memory_total_gb": round(vm.total / 1024**3, 2),
        "memory_used_percent": vm.percent,
        "boot_time": psutil.boot_time(),
        "agent_pid": os.getpid(),
        "agent_uptime_seconds": round(time.monotonic(), 1),
    }
