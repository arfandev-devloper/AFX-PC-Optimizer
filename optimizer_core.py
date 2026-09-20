import os
import json
import time
import shutil
import socket
import tempfile
import platform
import subprocess
from pathlib import Path

import psutil


MIN_AGE_SECONDS = 24 * 60 * 60


def bytes_to_human(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def _is_windows():
    return platform.system().lower() == "windows"


def get_system_summary():
    system_drive = (os.environ.get("SystemDrive", "C:") + "\\") if _is_windows() else "/"
    cpu_name = platform.processor() or "Unknown CPU"
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "hostname": socket.gethostname(),
        "cpu": cpu_name,
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
        "ram_total": psutil.virtual_memory().total,
        "system_drive": system_drive,
    }


def safe_temp_locations():
    candidates = [Path(tempfile.gettempdir())]

    if _is_windows():
        local = os.environ.get("LOCALAPPDATA")
        windir = os.environ.get("WINDIR")
        if local:
            candidates.append(Path(local) / "Temp")
        if windir:
            candidates.append(Path(windir) / "Temp")

    seen = set()
    result = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key not in seen and path.exists() and path.is_dir():
            seen.add(key)
            result.append(path)
    return result


def _iter_eligible_files(root, min_age_seconds=MIN_AGE_SECONDS):
    cutoff = time.time() - min_age_seconds
    try:
        iterator = root.rglob("*")
    except Exception:
        return

    for path in iterator:
        try:
            if not path.is_file() or path.is_symlink():
                continue
            stat = path.stat()
            if stat.st_mtime > cutoff:
                continue
            yield path, stat.st_size
        except (PermissionError, FileNotFoundError, OSError):
            continue


def scan_junk():
    locations = []
    total_files = 0
    total_bytes = 0
    file_records = []

    for root in safe_temp_locations():
        count = 0
        size = 0
        files = []
        for path, file_size in _iter_eligible_files(root):
            count += 1
            size += file_size
            files.append((str(path), file_size))
        locations.append({"path": str(root), "files": count, "bytes": size})
        total_files += count
        total_bytes += size
        file_records.extend(files)

    return {
        "files": total_files,
        "bytes": total_bytes,
        "locations": locations,
        "file_records": file_records,
        "created_at": time.time(),
    }


def clean_junk(scan_result):
    deleted_files = 0
    deleted_bytes = 0
    skipped_files = 0

    for raw_path, expected_size in scan_result.get("file_records", []):
        path = Path(raw_path)
        try:
            if path.exists() and path.is_file() and not path.is_symlink():
                current = path.stat()
                if current.st_mtime > time.time() - MIN_AGE_SECONDS:
                    skipped_files += 1
                    continue
                path.unlink()
                deleted_files += 1
                deleted_bytes += current.st_size
        except (PermissionError, FileNotFoundError, OSError):
            skipped_files += 1

    # Remove empty directories inside approved temp roots only.
    for root in safe_temp_locations():
        try:
            dirs = [p for p in root.rglob("*") if p.is_dir() and not p.is_symlink()]
            for folder in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
                try:
                    folder.rmdir()
                except OSError:
                    pass
        except (PermissionError, FileNotFoundError, OSError):
            pass

    return {
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "skipped_files": skipped_files,
    }


def _run(command, timeout=25):
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False
        )
        output = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, output
    except Exception as exc:
        return False, str(exc)


def flush_dns():
    if not _is_windows():
        return False, "Flush DNS is supported by this app on Windows only."
    ok, output = _run(["ipconfig", "/flushdns"])
    return ok, output or ("DNS cache flushed." if ok else "DNS flush failed.")


def empty_recycle_bin():
    if not _is_windows():
        return False, "Recycle Bin cleanup is supported on Windows only."
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Clear-RecycleBin -Force -ErrorAction Stop; Write-Output 'Recycle Bin emptied.'"
    ]
    ok, output = _run(command)
    return ok, output or ("Recycle Bin emptied." if ok else "Could not empty Recycle Bin.")


def set_power_plan(mode):
    if not _is_windows():
        return False, "Power plan switching is supported on Windows only."

    aliases = {
        "balanced": "SCHEME_BALANCED",
        "high": "SCHEME_MIN",
    }
    alias = aliases.get(mode)
    if not alias:
        return False, "Unknown power plan."

    ok, output = _run(["powercfg", "/setactive", alias])
    if ok:
        label = "Balanced" if mode == "balanced" else "High Performance"
        return True, f"{label} power plan activated."
    return False, output or "Windows could not switch the requested power plan."


def create_restore_point():
    if not _is_windows():
        return False, "Restore points are supported on Windows only."
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Checkpoint-Computer -Description 'AFX PC Optimizer' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop; "
        "Write-Output 'Restore point created.'"
    ]
    ok, output = _run(command, timeout=60)
    return ok, output or ("Restore point created." if ok else "Could not create restore point.")


def get_startup_apps():
    if not _is_windows():
        return []

    ps = (
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object Name,Command,Location | ConvertTo-Json -Depth 2 -Compress"
    )
    ok, output = _run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps
    ], timeout=30)

    if not ok or not output:
        return []

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            return [
                {
                    "Name": str(item.get("Name", "")),
                    "Command": str(item.get("Command", "")),
                    "Location": str(item.get("Location", "")),
                }
                for item in data
                if isinstance(item, dict)
            ]
    except json.JSONDecodeError:
        pass
    return []