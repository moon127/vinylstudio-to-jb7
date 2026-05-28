# vinylstudio-to-jb7 — Agent Context

## Project Goal

Cross-platform Python GUI app that syncs audio files to a Brennan JB7 media player. Copies files **one at a time** with a configurable pause so each gets a distinct creation timestamp (JB7 sorts by creation time, not filename).

## Architecture

- `main.py` — entry point, calls `App().run()`
- `vinylstudio_to_jb7/app.py` — tkinter GUI (`App` class), sync orchestration, platform logic wiring
- `vinylstudio_to_jb7/sync.py` — core copy loop: `has_subdirectories`, `resolve_target`, `sync_directories`, `SyncProgress`
- `vinylstudio_to_jb7/platform.py` — `dot_clean_available`, `run_dot_clean`, `remove_metadata_files`, `eject_volume`
- `vinylstudio_to_jb7/metadata.py` — MusicBrainz album metadata lookup, id file generation, track number stripping
- `tests/test_app.py`, `tests/test_sync.py`, `tests/test_platform.py`, `tests/test_metadata.py`

## Key Design Decisions

### Source handling (resolve_target)
- If source has **subdirectories** (e.g. `Artist   Album/`), mirror directly into destination
- If source is **flat** (files only), wrap in `dst/<basename(src)>/`

### Hardfi mode
- Checkbox "Output in JB7 hardfi format" redirects output to `dst/hardfi/`
- Source expected to already contain `Artist   Album/01 track.mp3` layout (standard VinylStudio export format: `[Album Artist]   [Album Title] / [Track Number] [Track Title]`)
- Sub-checkbox "Strip track numbers and generate album.id file" (auto-checked when hardfi is on)
  - `filename_transform=strip_track_number` passed to `sync_directories` — strips leading digits+space from filenames during copy
  - After sync completes, `_generate_id_files` iterates album dirs in target, attempts MusicBrainz auto-lookup via `metadata.py`, falls back to `_MusicBrainzSearchDialog` then confirmation dialog, writes `id` file per album
  - Free of tk var access in background thread (strip_tracks, do_dot_clean passed as args)

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

### Album id file generation (metadata.py)
- `metadata.py` uses `musicbrainzngs` to look up album metadata (artist, title, year, genre, tracks)
- `parse_album_dir(dirname)` splits `"Artist   Album"` into `(artist, album)` on 2+ spaces
- `strip_track_number(filename)` strips leading `\d+\s` from filenames
- `search_releases(artist, title)` returns list of candidate dicts with id/title/year/artist
- Three-stage lookup: (1) exact title match → single = auto-use, multiple → `_ReleaseSelectionDialog`; (2) no exact match → `_MusicBrainzSearchDialog` manual search; (3) user declines → `messagebox.askyesno` fallback; (4) still declines → skip
- `get_release_metadata(release_id)` fetches full release data from MusicBrainz
- `_ReleaseSelectionDialog` shows release year/title/artist listbox for multi-match disambiguation
- Tests: mock `type("L", ..., {"curselection": ...})()` — must instantiate with `()` and the lambda takes parameter `s`
- `generate_id_file` writes `"\n".join(lines) + "\n"` (trailing newline to avoid `%`)
- `generate_id_file(album_dir, metadata, stripped_filenames)` writes `id` file with format:
  - Line 1: `Artist / Album` (or `Various Artists / Album` for VA)
  - Line 2: Year
  - Line 3: Genre
  - Lines 4+: Track titles (one per line, `Artist / Track` for VA)
- For VA albums (detected via MB per-track artist-credit or directory name), tracks include artist prefix
- Fallback: year=1970, genre=Unknown, tracks from stripped filename (no extension)

### Thread-safe dialogs (MusicBrainz search)
- Same event-based mechanism as dir/file conflict dialogs
- `_request_musicbrainz_search(artist, album)` → shows `_MusicBrainzSearchDialog`, returns release_id or None
- `_request_release_selection(candidates, artist, album)` → shows `_ReleaseSelectionDialog`, returns release_id or None (when multiple exact-title matches exist)
- `_request_confirm_fallback(artist, album)` → `messagebox.askyesno`, returns bool

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
- Test `_MusicBrainzSearchDialog` by mocking `wait_window` and `_do_search`
- Test `_request_musicbrainz_search` / `_request_confirm_fallback` by monkeypatching the dialog class / messagebox and the `after` method
- `metadata.py` functions that hit MusicBrainz API should monkeypatch the `musicbrainzngs` module functions with `*args, **kwargs` signatures

## Conventions

- Stdlib-only (tkinter, threading, os, shutil, time, collections). No external deps except `musicbrainzngs` for metadata lookup.
- Type hints on all function signatures
- `SyncProgress.cancelled` checked frequently in loops for responsive cancellation
- `make venv` creates venv and installs pytest/pytest-cov and musicbrainzngs
- Source must be Python 3.10+ compatible
