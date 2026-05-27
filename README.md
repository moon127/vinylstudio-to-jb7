# vinylstudio-to-jb7

A cross-platform GUI application for syncing audio files to a **Brennan JB7** media player.

## The Problem

The Brennan JB7 media player organises tracks by their filesystem creation timestamp rather than by filename. When copying many files at once (e.g. via drag-and-drop or `rsync`), all files end up with nearly identical timestamps, causing the JB7 to play them in an unpredictable order.

This tool solves that by copying files **one at a time** with a **user-configurable pause** between each copy. This ensures each file gets a distinct creation timestamp on the destination volume, preserving your intended play order.

## Features

- **Cross-platform** — runs on macOS, Linux, and Windows (Python + tkinter)
- **Configurable pause** — set the delay between file copies (e.g. 0.5s) to suit slow USB drives
- **Smart source handling** — if the selected source contains only files, a subdirectory named after the source is created on the destination; if it already contains subdirectories, the folder structure is mirrored as-is
- **macOS metadata cleanup** — removes `.DS_Store`, `._*`, `.localized`, and `Thumbs.db` files from the copied tree, then runs `dot_clean` to merge remaining Apple Double resource fork files
- **Volume eject** — eject the destination volume from the UI (macOS: `diskutil`, Linux: `udisksctl`/`eject`, Windows: PowerShell)
- **Live log** — see each file being copied in real time
- **Cancel** — safely abort an in-progress sync

## Requirements

- **Python 3.10+**
- **tkinter** (see macOS notes below if using Homebrew Python)

## Installation

### Using the Makefile (recommended)

```bash
# Clone the repository
git clone <repo-url> vinylstudio-to-jb7
cd vinylstudio-to-jb7

# Create virtual environment and install test dependencies
make venv
```

### Manually

```bash
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows
pip install pytest pytest-cov   # only needed for running tests
```

### macOS: tkinter with Homebrew Python

If you installed Python via Homebrew, tkinter may not work out of the box:

```bash
# Install Tcl/Tk and the Python tkinter bindings
brew install tcl-tk
brew install python-tk@3.14

# If you already had Python installed, reinstall it to link tkinter
brew reinstall python@3.14
```

Verify it works:

```bash
python3 -c "import tkinter; print('ok')"
```

If you use a different Python version, replace `3.14` with your Python version (e.g. `python-tk@3.12`).

## Running

```bash
# Activate the virtual environment (if not already active)
source venv/bin/activate

# Launch the application
python main.py
```

## Tests

```bash
make test
```

This runs the full test suite with coverage reporting (threshold: 90%). Tests cover sync logic, platform utilities, and GUI components with mocked tkinter.

To view an HTML coverage report:

```bash
make test-html
# open htmlcov/index.html
```

## Cleanup

```bash
make clean
```

Removes the virtual environment, cache files, and build artifacts.

## GUI Walkthrough

1. **Source Directory** — click Browse and select your music folder.
   - **Flat source** (files only, e.g. a single album): creates `destination/<dirname>/files...`
   - **Nested source** (has subdirectories, e.g. your whole library): mirrors subdirectories directly into the destination
2. **Destination Directory** — click Browse and select the root of your JB7 USB drive.
3. **Pause between files** — set the delay in seconds (default 0.5). Increase for very slow USB sticks.
4. **Clean macOS metadata** — checked by default on macOS. Removes `.DS_Store`, `._*`, `.localized`, `Thumbs.db` from the copied tree, then runs `dot_clean` to merge any remaining Apple Double files.
5. Click **Sync** to begin. The log area shows progress for each file.
6. Click **Cancel** at any time to stop the sync.
7. Click **Eject Destination** to safely unmount/eject the destination volume when done.

## How It Works

1. The application checks whether the source contains subdirectories to determine the sync strategy.
2. It walks the source directory and counts all files.
3. It copies each file using `shutil.copy2` (preserving metadata), sleeping for the configured pause between copies.
4. On macOS, if the option is enabled, it removes metadata/cache files (`.DS_Store`, `._*`, etc.) and runs `dot_clean` to merge any remaining Apple Double resource fork files.
5. Every file on the destination gets a slightly different creation timestamp, and the JB7 plays them in filename order.

## Platform Notes

### macOS

- Metadata cleanup (`.DS_Store`, `._*`, etc.) runs automatically after sync when the checkbox is enabled.
- `dot_clean` is called after file removal to merge any remaining resource fork files.
- Volume eject uses `diskutil eject`.
- If `dot_clean` requires permissions, grant Terminal/your app access to removable volumes in System Settings > Privacy & Security > Files and Folders.

### Linux

- Volume eject attempts `udisksctl unmount` first, then falls back to `eject`.
- Install `udisks2` or `eject` if the eject button does not work.

### Windows

- Volume eject uses a PowerShell COM object (Shell.Application).
- The destination path must be a drive with a drive letter (e.g. `D:\`).

## Packaging (Optional)

To build a standalone executable with [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py --name vinylstudio-to-jb7
```

The executable will be in the `dist/` directory.

## Project Structure

```
vinylstudio-to-jb7/
├── main.py                          # Entry point
├── Makefile                         # venv, test, clean targets
├── requirements.txt
├── README.md
├── vinylstudio_to_jb7/
│   ├── app.py                       # tkinter GUI application
│   ├── sync.py                      # Sequential file copy with pause + cancel
│   └── platform.py                  # macOS dot_clean, metadata cleanup, cross-platform eject
└── tests/
    ├── test_app.py                  # GUI unit tests (mocked)
    ├── test_platform.py             # Platform utility tests
    └── test_sync.py                 # Sync logic tests
```

## License

MIT
