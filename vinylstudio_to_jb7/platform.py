import os
import platform
import shutil
import subprocess
import sys


IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"


DOTFILE_NAMES = {".DS_Store", ".localized", "Thumbs.db"}


def dot_clean_available() -> bool:
    return IS_MAC and shutil.which("dot_clean") is not None


def run_dot_clean(path: str) -> tuple[bool, str]:
    if not dot_clean_available():
        return False, "dot_clean is not available on this system"
    try:
        result = subprocess.run(
            ["dot_clean", path],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return True, f"dot_clean completed on {path}"
        return False, f"dot_clean failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "dot_clean timed out"
    except FileNotFoundError:
        return False, "dot_clean not found"
    except Exception as e:
        return False, f"dot_clean error: {e}"


def remove_metadata_files(path: str) -> tuple[int, list[str]]:
    removed = 0
    errors = []
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if filename in DOTFILE_NAMES or filename.startswith("._"):
                filepath = os.path.join(dirpath, filename)
                try:
                    os.remove(filepath)
                    removed += 1
                except Exception as e:
                    errors.append(f"{filepath}: {e}")
    return removed, errors


def eject_volume_available() -> bool:
    return IS_MAC or IS_LINUX or IS_WINDOWS


def eject_volume(path: str) -> tuple[bool, str]:
    if not os.path.exists(path):
        return False, f"Path does not exist: {path}"

    try:
        if IS_MAC:
            disk = _resolve_mac_disk(path)
            if not disk:
                return False, f"Could not find disk for path: {path}"
            cmd = ["diskutil", "eject", disk]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return True, f"Ejected {disk}"
            return False, f"Eject failed: {result.stderr.strip() or result.stdout.strip()}"

        elif IS_LINUX:
            result = subprocess.run(
                ["udisksctl", "unmount", "-b", path],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return True, f"Unmounted {path}"
            result2 = subprocess.run(
                ["eject", path],
                capture_output=True, text=True, timeout=60
            )
            if result2.returncode == 0:
                return True, f"Ejected {path}"
            return False, f"Eject failed: {result2.stderr.strip() or result.stderr.strip()}"

        elif IS_WINDOWS:
            drive = os.path.splitdrive(path)[0]
            if not drive:
                return False, f"Could not determine drive letter for: {path}"
            script = f"""
$drive = '{drive}'
$driveLetter = $drive[0]
$shell = New-Object -COMObject Shell.Application
$shell.Namespace(17).ParseName($driveLetter + ':').InvokeVerb('Eject')
"""
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return True, f"Ejected {drive}"
            return False, f"Eject failed: {result.stderr.strip()}"

        return False, "Eject not supported on this platform"

    except subprocess.TimeoutExpired:
        return False, "Eject timed out"
    except Exception as e:
        return False, f"Eject error: {e}"


def _resolve_mac_disk(path: str) -> str | None:
    resolved = os.path.realpath(path)
    try:
        result = subprocess.run(
            ["df", resolved],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return None
        device = lines[1].split()[0]
        if device.startswith("/dev/"):
            return device
        return None
    except Exception:
        return None
