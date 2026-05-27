import os
import shutil
import time


class SyncProgress:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def has_subdirectories(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    try:
        for entry in os.listdir(path):
            if os.path.isdir(os.path.join(path, entry)):
                return True
    except PermissionError:
        return False
    return False


def resolve_target(src: str, dst: str) -> str:
    if has_subdirectories(src):
        return dst
    return os.path.join(dst, os.path.basename(os.path.normpath(src)))


def sync_directories(
    src: str,
    dst: str,
    pause_seconds: float,
    progress: SyncProgress,
    log_callback: callable,
) -> bool:
    if not os.path.isdir(src):
        log_callback(f"ERROR: Source directory does not exist: {src}")
        return False

    if not os.path.isdir(dst):
        log_callback(f"ERROR: Destination directory does not exist: {dst}")
        return False

    target_base = resolve_target(src, dst)
    os.makedirs(target_base, exist_ok=True)

    total_files = 0
    copied_files = 0

    for dirpath, dirnames, filenames in os.walk(src):
        if progress.cancelled:
            log_callback("Sync cancelled by user")
            return False

        rel_path = os.path.relpath(dirpath, src)
        target_dir = os.path.join(target_base, rel_path) if rel_path != "." else target_base

        for dirname in dirnames:
            if progress.cancelled:
                return False
            os.makedirs(os.path.join(target_dir, dirname), exist_ok=True)

        for filename in filenames:
            if progress.cancelled:
                return False
            total_files += 1

    log_callback(f"Found {total_files} files to copy")

    for dirpath, dirnames, filenames in os.walk(src):
        if progress.cancelled:
            log_callback("Sync cancelled by user")
            return False

        rel_path = os.path.relpath(dirpath, src)
        target_dir = os.path.join(target_base, rel_path) if rel_path != "." else target_base

        for filename in sorted(filenames):
            if progress.cancelled:
                log_callback("Sync cancelled by user")
                return False

            src_file = os.path.join(dirpath, filename)
            dst_file = os.path.join(target_dir, filename)

            try:
                shutil.copy2(src_file, dst_file)
                copied_files += 1
                log_callback(f"[{copied_files}/{total_files}] Copied: {os.path.join(rel_path, filename) if rel_path != '.' else filename}")

                if pause_seconds > 0 and copied_files < total_files:
                    _sleep_with_cancel(pause_seconds, progress)
                    if progress.cancelled:
                        log_callback("Sync cancelled by user")
                        return False

            except Exception as e:
                log_callback(f"ERROR copying {src_file}: {e}")
                continue

    log_callback(f"Sync complete: {copied_files} files copied to {target_base}")
    return True


def _sleep_with_cancel(seconds: float, progress: SyncProgress):
    interval = 0.1
    elapsed = 0.0
    while elapsed < seconds:
        if progress.cancelled:
            return
        time.sleep(interval)
        elapsed += interval
