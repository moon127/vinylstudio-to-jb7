# vinylstudio-to-jb7 — Agent Context

## Project Goal

Cross-platform Python GUI app that syncs audio files to a Brennan JB7 media player. Copies files **one at a time** with a configurable pause so each gets a distinct creation timestamp (JB7 sorts by creation time, not filename).

## Architecture

- `main.py` — entry point, calls `App().run()`
- `vinylstudio_to_jb7/app.py` — tkinter GUI (`App` class), sync orchestration, platform logic wiring
- `vinylstudio_to_jb7/sync.py` — core copy loop: `has_subdirectories`, `resolve_target`, `sync_directories`, `SyncProgress`
- `vinylstudio_to_jb7/platform.py` — `dot_clean_available`, `run_dot_clean`, `remove_metadata_files`, `eject_volume`
- `tests/test_app.py`, `tests/test_sync.py`, `tests/test_platform.py`

## Key Design Decisions

### Source handling (resolve_target)
- If source has **subdirectories** (e.g. `Artist   Album/`), mirror directly into destination
- If source is **flat** (files only), wrap in `dst/<basename(src)>/`

### Hardfi mode
- Checkbox "Output in JB7 hardfi format" redirects output to `dst/hardfi/`
- Source expected to already contain `Artist   Album/01 track.mp3` layout (standard VinylStudio export format: `[Album Artist]   [Album Title] / [Track Number] [Track Title]`)
- No filename transform — files copy as-is

### Thread-safe logging
- Background thread appends to `collections.deque` (`_log_queue`)
- Main thread polls via `root.after(100, _poll_log_queue)`

### Thread-safe dialogs (directory/file conflicts)
- `_confirm_dir`/`_confirm_file` set `_dialog_request`, schedule `_process_dialog` via `root.after(0, ...)`, block on `threading.Event`
- Main thread processes dialog, sets `_dialog_result`, signals event
- Directory conflict: `messagebox.askyesnocancel` (Yes=overwrite, No=skip, Cancel=cancel)
- File conflict: custom `_OptionDialog` (Skip / Overwrite / Overwrite All / Cancel Sync)
- Callbacks passed to `sync_directories` as `dir_exists_callback` / `file_exists_callback`

### Eject
- Background thread calls `eject_volume(dst)`, stores result
- Main thread polls `_eject_result` via `root.after(100, _poll_eject_done)`

### macOS metadata cleanup
- `remove_metadata_files` deletes `.DS_Store`, `._*`, `.localized`, `Thumbs.db`
- `run_dot_clean` merges remaining Apple Double files
- Checkbox default ON on macOS, hidden/disabled on other platforms

### Cross-platform eject
- macOS: `diskutil eject`
- Linux: `udisksctl unmount` → `eject` (fallback)
- Windows: PowerShell COM (Shell.Application)

## Testing

```bash
make test          # pytest + coverage (threshold 90%)
make test-html     # HTML coverage report
```

- Tests mock tkinter (typical for headless/CI). App fixture creates `App()` with `root.withdraw()`.
- For testing threaded dialog methods (`_confirm_dir`, `_confirm_file`), monkeypatch `app.root.after` to call the callback synchronously: `monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))`
- Test dialog `_OptionDialog` by mocking `wait_window` and testing `_done` directly

## Conventions

- Stdlib-only (tkinter, threading, os, shutil, time, collections). No external deps.
- Type hints on all function signatures
- `SyncProgress.cancelled` checked frequently in loops for responsive cancellation
- `make venv` creates venv and installs pytest/pytest-cov
- Source must be Python 3.10+ compatible
