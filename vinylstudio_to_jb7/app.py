import collections
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .platform import IS_MAC, dot_clean_available, eject_volume, remove_metadata_files, run_dot_clean
from .sync import SyncProgress, sync_directories


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("vinylstudio-to-jb7")
        self.root.geometry("780x600")
        self.root.minsize(600, 400)

        self.sync_progress: SyncProgress | None = None
        self.sync_thread: threading.Thread | None = None
        self._eject_result: tuple[bool, str] | None = None
        self._log_queue: collections.deque = collections.deque()
        self._poll_log_queue()

        self._build_ui()
        self._apply_platform_options()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        row = 0

        ttk.Label(main, text="Source Directory:").grid(row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1
        src_frame = ttk.Frame(main)
        src_frame.grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        self.src_var = tk.StringVar()
        self.src_entry = ttk.Entry(src_frame, textvariable=self.src_var)
        self.src_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(src_frame, text="Browse...", command=self._browse_src).pack(side=tk.RIGHT, padx=(6, 0))
        row += 1

        ttk.Label(main, text="Destination Directory:").grid(row=row, column=0, sticky=tk.W, pady=(0, 2))
        row += 1
        dst_frame = ttk.Frame(main)
        dst_frame.grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        self.dst_var = tk.StringVar()
        self.dst_entry = ttk.Entry(dst_frame, textvariable=self.dst_var)
        self.dst_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dst_frame, text="Browse...", command=self._browse_dst).pack(side=tk.RIGHT, padx=(6, 0))
        row += 1

        pause_frame = ttk.Frame(main)
        pause_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))
        ttk.Label(pause_frame, text="Pause between files (seconds):").pack(side=tk.LEFT)
        self.pause_var = tk.StringVar(value="0.5")
        self.pause_spin = ttk.Spinbox(
            pause_frame, from_=0, to=60, increment=0.1,
            textvariable=self.pause_var, width=8
        )
        self.pause_spin.pack(side=tk.LEFT, padx=(6, 0))
        row += 1

        self.dot_clean_var = tk.BooleanVar(value=True)
        self.dot_clean_cb = ttk.Checkbutton(
            main, text="Clean macOS metadata (.DS_Store, ._ files) and run dot_clean on destination",
            variable=self.dot_clean_var
        )
        self.dot_clean_cb.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))
        row += 1

        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        self.sync_btn = ttk.Button(btn_frame, text="Sync", command=self._start_sync)
        self.sync_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._cancel_sync, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.eject_btn = ttk.Button(btn_frame, text="Eject Destination", command=self._eject_dst)
        self.eject_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Clear Log", command=self._clear_log).pack(side=tk.RIGHT)
        row += 1

        log_frame = ttk.LabelFrame(main, text="Log", padding=4)
        log_frame.grid(row=row, column=0, columnspan=3, sticky=tk.NSEW, pady=(0, 4))
        main.rowconfigure(row, weight=1)
        main.columnconfigure(1, weight=1)

        self.log_text = tk.Text(log_frame, state=tk.DISABLED, wrap=tk.WORD, font=("Menlo", 10))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        row += 1

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _apply_platform_options(self):
        if not IS_MAC:
            self.dot_clean_cb.configure(state=tk.DISABLED)
            self.dot_clean_var.set(False)

    def _browse_src(self):
        path = filedialog.askdirectory(title="Select Source Directory")
        if path:
            self.src_var.set(path)

    def _browse_dst(self):
        path = filedialog.askdirectory(title="Select Destination Directory")
        if path:
            self.dst_var.set(path)

    def _log(self, message: str):
        self._log_queue.append(message)

    def _poll_log_queue(self):
        while self._log_queue:
            message = self._log_queue.popleft()
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(100, self._poll_log_queue)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_ui_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.sync_btn.configure(state=state)
        self.src_entry.configure(state=state)
        self.dst_entry.configure(state=state)
        self.pause_spin.configure(state=state)
        self.eject_btn.configure(state=state)
        if IS_MAC:
            self.dot_clean_cb.configure(state=state)
        self.cancel_btn.configure(state=tk.DISABLED if enabled else tk.NORMAL)

    def _start_sync(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()

        if not src:
            messagebox.showerror("Error", "Please select a source directory")
            return
        if not dst:
            messagebox.showerror("Error", "Please select a destination directory")
            return
        if src == dst:
            messagebox.showerror("Error", "Source and destination must be different")
            return

        try:
            pause = float(self.pause_var.get())
            if pause < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Pause must be a non-negative number")
            return

        self._log(f"Starting sync: {src} -> {dst}")
        self._log(f"Pause between files: {pause}s" if pause > 0 else "No pause between files")
        self._set_ui_enabled(False)
        self.status_var.set("Syncing...")

        self.sync_progress = SyncProgress()
        self.sync_thread = threading.Thread(
            target=self._sync_worker,
            args=(src, dst, pause, self.sync_progress),
            daemon=True,
        )
        self.sync_thread.start()
        self.root.after(100, self._check_sync_done)

    def _sync_worker(self, src: str, dst: str, pause: float, progress: SyncProgress):
        success = sync_directories(src, dst, pause, progress, self._log)
        if success and self.dot_clean_var.get() and IS_MAC:
            self._log("Removing macOS metadata files (.DS_Store, ._*, ...)...")
            count, errs = remove_metadata_files(dst)
            self._log(f"Removed {count} metadata files")
            for err in errs:
                self._log(f"  ERROR: {err}")
            if dot_clean_available():
                self._log("Running dot_clean on destination...")
                ok, msg = run_dot_clean(dst)
                self._log(msg)
        self._sync_result = success

    def _check_sync_done(self):
        if self.sync_thread is not None and self.sync_thread.is_alive():
            self.root.after(100, self._check_sync_done)
            return

        self.sync_progress = None
        self.sync_thread = None
        self._set_ui_enabled(True)
        self.status_var.set("Ready")

        if hasattr(self, "_sync_result"):
            if self._sync_result:
                self._log("Sync finished successfully")
            else:
                self._log("Sync finished with errors")
            del self._sync_result

    def _cancel_sync(self):
        if self.sync_progress:
            self._log("Cancelling sync...")
            self.sync_progress.cancel()
            self.cancel_btn.configure(state=tk.DISABLED)

    def _eject_dst(self):
        dst = self.dst_var.get().strip()
        if not dst:
            messagebox.showerror("Error", "Please select a destination directory first")
            return

        self._log(f"Ejecting volume for: {dst}")
        self.status_var.set("Ejecting...")
        self.root.update_idletasks()

        self._eject_result = None

        def eject_worker():
            ok, msg = eject_volume(dst)
            self._eject_result = (ok, msg)

        thread = threading.Thread(target=eject_worker, daemon=True)
        thread.start()
        self.root.after(100, self._poll_eject_done)

    def _poll_eject_done(self):
        if self._eject_result is None:
            self.root.after(100, self._poll_eject_done)
            return
        ok, msg = self._eject_result
        self._eject_result = None
        self._log(msg)
        self.status_var.set("Ready")
        if ok:
            self.dst_var.set("")
        else:
            messagebox.showerror("Eject Failed", msg)

    def run(self):
        self.root.mainloop()
