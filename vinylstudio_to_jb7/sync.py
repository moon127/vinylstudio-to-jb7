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
    dir_exists_callback: callable | None = None,
    file_exists_callback: callable | None = None,
    filename_transform: callable | None = None,
) -> bool:
    if not os.path.isdir(src):
        log_callback(f"ERROR: Source directory does not exist: {src}")
        return False

    if not os.path.isdir(dst):
        log_callback(f"ERROR: Destination directory does not exist: {dst}")
        return False

    target = resolve_target(src, dst)
    os.makedirs(target, exist_ok=True)

    skipped_dirs: set[str] = set()
    total_files = 0
    copied_files = 0

    for dirpath, dirnames, filenames in os.walk(src):
        if progress.cancelled:
            log_callback("Sync cancelled by user")
            return False

        rel_path = os.path.relpath(dirpath, src)
        target_dir = os.path.join(target, rel_path) if rel_path != "." else target

        for dirname in dirnames:
            if progress.cancelled:
                return False
            dest_child = os.path.join(target_dir, dirname)
            child_rel = os.path.relpath(os.path.join(dirpath, dirname), src)
            if os.path.isdir(dest_child) and dir_exists_callback:
                action = dir_exists_callback(child_rel)
                if action == "skip":
                    skipped_dirs.add(child_rel)
                    log_callback(f"Skipping existing directory: {child_rel}")
                    continue
                elif action == "cancel":
                    log_callback("Sync cancelled by user")
                    progress.cancel()
                    return False
            os.makedirs(dest_child, exist_ok=True)

        for filename in filenames:
            if progress.cancelled:
                return False
            total_files += 1

    log_callback(f"Found {total_files} files to copy")

    overwrite_all_dirs: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(src):
        if progress.cancelled:
            log_callback("Sync cancelled by user")
            return False

        rel_path = os.path.relpath(dirpath, src)
        if rel_path in skipped_dirs or any(rel_path.startswith(s + os.sep) for s in skipped_dirs):
            continue

        target_dir = os.path.join(target, rel_path) if rel_path != "." else target

        for filename in sorted(filenames):
            if progress.cancelled:
                log_callback("Sync cancelled by user")
                return False

            dest_filename = filename_transform(filename) if filename_transform else filename
            src_file = os.path.join(dirpath, filename)
            dst_file = os.path.join(target_dir, dest_filename)

            if os.path.exists(dst_file) and file_exists_callback and rel_path not in overwrite_all_dirs:
                action = file_exists_callback(rel_path, dest_filename)
                if action == "skip":
                    log_callback(f"[{copied_files + 1}/{total_files}] Skipped: {dest_filename}")
                    continue
                elif action == "overwrite_all":
                    overwrite_all_dirs.add(rel_path)
                elif action == "cancel":
                    log_callback("Sync cancelled by user")
                    progress.cancel()
                    return False

            try:
                shutil.copy2(src_file, dst_file)
                copied_files += 1
                log_callback(f"[{copied_files}/{total_files}] Copied: {dest_filename}")

                if pause_seconds > 0 and copied_files < total_files:
                    _sleep_with_cancel(pause_seconds, progress)
                    if progress.cancelled:
                        log_callback("Sync cancelled by user")
                        return False

            except Exception as e:
                log_callback(f"ERROR copying {src_file}: {e}")
                continue

    log_callback(f"Sync complete: {copied_files} files copied to {target}")
    return True


def _sleep_with_cancel(seconds: float, progress: SyncProgress):
    interval = 0.1
    elapsed = 0.0
    while elapsed < seconds:
        if progress.cancelled:
            return
        time.sleep(interval)
        elapsed += interval
