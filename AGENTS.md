# vinylstudio-to-jb7 — Agent Context

## Project Goal

Cross-platform Python GUI app that syncs audio files to a Brennan JB7 media player. Copies files **one at a time** with a configurable pause so each gets a distinct creation timestamp (JB7 sorts by creation time, not filename).

## Architecture

- `main.py` — entry point, calls `App().run()`
- `vinylstudio_to_jb7/app.py` — tkinter GUI (`App` class), sync orchestration, platform logic wiring, dialogs
- `vinylstudio_to_jb7/sync.py` — core copy loop: `has_subdirectories`, `resolve_target`, `sync_directories`, `SyncProgress`
- `vinylstudio_to_jb7/platform.py` — `dot_clean_available`, `run_dot_clean`, `remove_metadata_files`, `eject_volume`
- `vinylstudio_to_jb7/metadata.py` — MusicBrainz album metadata lookup, id file generation, track number stripping
- `tests/test_app.py`, `tests/test_sync.py`, `tests/test_platform.py`, `tests/test_metadata.py`

## Decision Log & Design History

### 1. id file format (initial)
- Lines: `Artist / Album`, Year, Genre, then one track per line
- VA albums get `Various Artists / Album` header and `Artist / Track` per track
- Fallback when MusicBrainz fails: year=1970, genre=Unknown, tracks derived from stripped filenames
- Trailing newline added to avoid `%` in shell display

### 2. Thread-safe dialog pattern
- Background thread sets `_dialog_request`, calls `root.after(0, _process_dialog)`, blocks on `threading.Event`
- Main thread processes dialog, sets `_dialog_result`, signals event
- Used for: dir conflicts (`messagebox.askyesnocancel`), file conflicts (custom `_OptionDialog`), MusicBrainz dialogs, confirm fallback
- All tk `Var.get()` calls extracted to thread-start time and passed as parameters — no tk access from worker thread

### 3. Hardfi mode sub-checkbox
- "Strip track numbers (if present), generate hardfi id files (MusicBrainz)"
- Auto-checked when hardfi toggled on; disabled when hardfi off
- Passes `filename_transform=strip_track_number` to `sync_directories`
- Post-sync: `_generate_id_files` does MusicBrainz lookup per album dir

### 4. Three-stage MusicBrainz lookup chain (added iteratively)
- **Stage 1** (initial): `lookup_album_metadata` — picks best candidate, if multiple exact-title matches picks first. Problem: silent wrong choice.
- **Stage 2** (added `_ReleaseSelectionDialog`): When multiple exact-title matches exist (e.g. original 1985 vs remaster 1996), show a selection dialog so user can pick.
- **Stage 3** (added `_MusicBrainzSearchDialog`): When no exact match exists, let user manually search artists and browse releases.
- **Stage 4** (fallback): If user declines/cancels all dialogs, ask `messagebox.askyesno` to use fallback metadata. If still declined, skip id file entirely.

### 5. Candidate dict format evolution
Initial: `{id, title, year, artist}`
- Added `format` (e.g. "CD", "Vinyl", "CD/DVD") and `track_count` (total across all mediums) so dialogs can distinguish releases (e.g. CD vs Vinyl of same album)
- `search_releases()`: extracts medium-list from search API response (included by default)
- `get_artist_releases()`: needs explicit `includes=["media"]` because `browse_releases` doesn't return `medium-list` without it
- `_ReleaseSelectionDialog` and `_MusicBrainzSearchDialog` both display `[CD] 12 tracks` suffix
- Tests construct candidate dicts with minimum fields; `.get()` with defaults handles missing keys gracefully

### 6. Mock object patterns for tkinter dialogs (key gotchas)
- `type("L", (), {"curselection": lambda s: (1,)})()` — must call `()` to instantiate (not just create class)
- The lambda takes `s` (self) because instance lookup produces a bound method that passes self
- For `_on_ok` tests: mock `self.destroy = lambda: None` to avoid AttributeError on `children`
- `wait_window` monkeypatch: `lambda self: None`

## Detailed Design: id file generation flow

1. After sync completes, `_generate_id_files(album_dir, progress)` iterates subdirs of target
2. Skips non-directories, `hardfi/` itself, dirs with existing `id` file
3. Calls `parse_album_dir(dirname)` to split `"Artist   Album"` into (artist, album) on 2+ spaces
4. Calls `search_releases(artist, album, limit=10)` → list of dicts with `{id, title, year, artist, format, track_count}`
5. Filter to exact title matches (case-insensitive):
   - **0 matches** → `_request_musicbrainz_search(artist, album)` → `_MusicBrainzSearchDialog`:
     - User types artist name → `search_artists` populates left listbox
     - Select artist → `get_artist_releases` populates right listbox with `Title (year) [Format] N tracks`
     - Select release → returns release_id
     - Cancel → None
   - **1 match** → auto-use that release_id
   - **2+ matches** → `_request_release_selection(candidates, ...)` → `_ReleaseSelectionDialog`:
     - Listbox shows `Title (year) [Format] N tracks`
     - "Use Selected" returns release_id, "Search Manually" returns None
6. If release_id obtained → `get_release_metadata(release_id)` → `AlbumMetadata`
7. If release_id is None:
   - `_request_confirm_fallback(artist, album)` → `messagebox.askyesno`
   - True → create `AlbumMetadata(artist, album, year="1970", genre="Unknown")` with tracks from filenames
   - False → skip this album
8. Calls `get_track_files(album_dir)` for stripped filenames
9. Calls `generate_id_file(album_dir, metadata, stripped_filenames)` → writes `id` file
10. Uses `SyncProgress.cancelled` checks throughout for responsive cancellation

## Thread-safe dialog APIs

| Method | Dialog | Returns |
|---|---|---|
| `_request_musicbrainz_search(artist, album)` | `_MusicBrainzSearchDialog` | `release_id \| None` |
| `_request_release_selection(candidates, artist, album)` | `_ReleaseSelectionDialog` | `release_id \| None` |
| `_request_confirm_fallback(artist, album)` | `messagebox.askyesno` | `bool` |
| `_confirm_dir(dir_path)` | `messagebox.askyesnocancel` | `True`=overwrite, `False`=skip, `None`=cancel |
| `_confirm_file(filename)` | `_OptionDialog` | `str`: "skip", "overwrite", "overwrite_all", "cancel" |

## Testing

```bash
make test          # pytest + coverage (threshold 90%)
make test-html     # HTML coverage report
```

- Tests mock tkinter (headless/CI). App fixture creates `App()` with `root.withdraw()`.
- Threaded dialog tests: `monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))` to run synchronously
- `_OptionDialog` tests: mock `wait_window`, test `_done` directly
- `_MusicBrainzSearchDialog` tests: mock `wait_window` and `_do_search`
- `_ReleaseSelectionDialog` tests: use `__new__` + mock `destroy`, or mock `wait_window` for constructor
- MusicBrainz API functions: monkeypatch `musicbrainzngs` module functions with `**kwargs` signatures
- Mock candidate dicts: only need `id`; other fields use `.get()` defaults

## Conventions

- Stdlib-only (tkinter, threading, os, shutil, time, collections). No external deps except `musicbrainzngs` for metadata lookup.
- Type hints on all function signatures
- `SyncProgress.cancelled` checked frequently in loops for responsive cancellation
- `make venv` creates venv and installs pytest/pytest-cov and musicbrainzngs
- Source must be Python 3.10+ compatible
- No comments in code unless essential
