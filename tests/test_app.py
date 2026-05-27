import os
import threading
import tkinter as tk

import pytest

from vinylstudio_to_jb7.app import App
from vinylstudio_to_jb7.platform import IS_MAC


@pytest.fixture
def app():
    os.environ["DISPLAY"] = ""
    app_instance = App()
    app_instance.root.withdraw()
    yield app_instance
    app_instance.root.destroy()


class TestAppInit:
    def test_title(self, app):
        assert app.root.title() == "vinylstudio-to-jb7"

    def test_default_pause(self, app):
        assert app.pause_var.get() == "0.5"

    def test_dot_clean_default_on_mac(self, app):
        assert app.dot_clean_var.get() is True


class TestApplyPlatformOptions:
    def test_dot_clean_disabled_on_non_mac(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.IS_MAC", False
        )
        app2 = App()
        app2.root.withdraw()
        assert app2.dot_clean_var.get() is False
        assert str(app2.dot_clean_cb.cget("state")) == "disabled"
        app2.root.destroy()


class TestBrowseDirs:
    def test_browse_src_sets_var(self, app):
        app._browse_src()
        assert app._browse_src

    def test_browse_dst_sets_var(self, app):
        app._browse_dst()
        assert app._browse_dst


class TestLog:
    def test_log_message(self, app):
        app._log("test message")
        app._poll_log_queue()
        app.log_text.configure(state=tk.NORMAL)
        content = app.log_text.get("1.0", tk.END)
        app.log_text.configure(state=tk.DISABLED)
        assert "test message" in content

    def test_clear_log(self, app):
        app._log("something")
        app._clear_log()
        app.log_text.configure(state=tk.NORMAL)
        content = app.log_text.get("1.0", tk.END).strip()
        app.log_text.configure(state=tk.DISABLED)
        assert content == ""


class TestSetUiEnabled:
    def test_disable(self, app):
        app._set_ui_enabled(False)
        assert str(app.sync_btn.cget("state")) == "disabled"
        assert str(app.cancel_btn.cget("state")) == "normal"

    def test_enable(self, app):
        app._set_ui_enabled(True)
        assert str(app.sync_btn.cget("state")) == "normal"
        assert str(app.cancel_btn.cget("state")) == "disabled"


class TestStartSync:
    def test_no_source(self, app):
        app.src_var.set("")
        app.dst_var.set("/some/dst")
        app._start_sync()
        assert app.sync_thread is None

    def test_no_dest(self, app):
        app.src_var.set("/some/src")
        app.dst_var.set("")
        app._start_sync()
        assert app.sync_thread is None

    def test_src_equals_dst(self, app):
        app.src_var.set("/same/path")
        app.dst_var.set("/same/path")
        app._start_sync()
        assert app.sync_thread is None

    def test_invalid_pause(self, app):
        app.src_var.set("/src")
        app.dst_var.set("/dst")
        app.pause_var.set("not-a-number")
        app._start_sync()
        assert app.sync_thread is None

    def test_negative_pause(self, app):
        app.src_var.set("/src")
        app.dst_var.set("/dst")
        app.pause_var.set("-1")
        app._start_sync()
        assert app.sync_thread is None

    def test_starts_sync_thread(self, app, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "test.txt").write_text("hello")

        app.src_var.set(str(src))
        app.dst_var.set(str(dst))
        app.pause_var.set("0")
        app._start_sync()

        assert app.sync_thread is not None
        assert app.sync_thread.is_alive()
        app._cancel_sync()
        app.sync_thread.join(timeout=5)

    def test_creates_progress_object(self, app, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()

        app.src_var.set(str(src))
        app.dst_var.set(str(dst))
        app.pause_var.set("0")
        app._start_sync()
        assert app.sync_progress is not None
        app._cancel_sync()
        app.sync_thread.join(timeout=5)


class TestCancelSync:
    def test_cancel_no_progress(self, app):
        app._cancel_sync()
        assert app.sync_progress is None

    def test_cancel_with_progress(self, app, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "test.txt").write_text("hello")

        import time
        from vinylstudio_to_jb7.sync import SyncProgress

        app.src_var.set(str(src))
        app.dst_var.set(str(dst))
        app.pause_var.set("5")
        app._start_sync()
        app._cancel_sync()

        assert app.sync_progress.cancelled is True
        app.sync_thread.join(timeout=5)


class TestEjectDst:
    def test_no_destination(self, app):
        app.dst_var.set("")
        app._eject_dst()

    def test_eject_starts_thread(self, app, tmp_path):
        dst = tmp_path / "dst"
        dst.mkdir()
        app.dst_var.set(str(dst))
        app._eject_dst()


class TestEjectDone:
    def test_eject_success_clears_dst(self, app):
        app.dst_var.set("/Volumes/JB7")
        app._eject_result = (True, "Ejected /dev/disk2")
        app._poll_eject_done()
        assert app.dst_var.get() == ""

    def test_eject_failure_preserves_dst(self, app):
        app.dst_var.set("/Volumes/JB7")
        app._eject_result = (False, "Eject failed")
        app._poll_eject_done()
        assert app.dst_var.get() == "/Volumes/JB7"


class TestSyncWorker:
    def test_sync_worker_normal(self, app, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "f.txt").write_text("content")

        from vinylstudio_to_jb7.sync import SyncProgress

        app.src_var.set(str(src))
        app.dst_var.set(str(dst))
        app.dot_clean_var.set(False)
        app.sync_progress = SyncProgress()

        app._sync_worker(str(src), str(dst), 0, app.sync_progress)

        assert app._sync_result is True
        target = os.path.join(str(dst), "src")
        assert os.path.exists(os.path.join(target, "f.txt"))

    def test_sync_worker_with_dot_clean(self, app, tmp_path, monkeypatch):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "f.txt").write_text("content")

        monkeypatch.setattr("vinylstudio_to_jb7.app.IS_MAC", True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.remove_metadata_files",
            lambda p: (0, []),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.run_dot_clean",
            lambda p: (True, "dot_clean completed"),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.dot_clean_available",
            lambda: True,
        )

        from vinylstudio_to_jb7.sync import SyncProgress

        app.src_var.set(str(src))
        app.dst_var.set(str(dst))
        app.dot_clean_var.set(True)
        app.sync_progress = SyncProgress()

        app._sync_worker(str(src), str(dst), 0, app.sync_progress)
        assert app._sync_result is True


class TestCheckSyncDone:
    def test_thread_still_alive_polls_again(self, app):
        t = threading.Thread(target=lambda: None)
        t.start()
        app.sync_thread = t
        app._check_sync_done()
        t.join(timeout=5)

    def test_sync_done_success(self, app):
        app._sync_result = True
        app.sync_thread = None
        app.sync_progress = None
        app._set_ui_enabled(False)
        app._check_sync_done()
        assert app.status_var.get() == "Ready"
        assert str(app.sync_btn.cget("state")) == "normal"

    def test_sync_done_failure(self, app):
        app._sync_result = False
        app.sync_thread = None
        app.sync_progress = None
        app._set_ui_enabled(False)
        app._check_sync_done()
        assert app.status_var.get() == "Ready"

    def test_no_result_does_nothing(self, app):
        app._check_sync_done()
