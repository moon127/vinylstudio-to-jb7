import os
import threading
import tkinter as tk

import pytest

from vinylstudio_to_jb7.app import App, _MusicBrainzSearchDialog, _OptionDialog, _ReleaseSelectionDialog
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

    def test_hardfi_default_off(self, app):
        assert app.hardfi_var.get() is False

    def test_strip_tracks_default_off(self, app):
        assert app.strip_tracks_var.get() is False

    def test_strip_tracks_disabled_by_default(self, app):
        assert str(app.strip_tracks_cb.cget("state")) == "disabled"

    def test_hardfi_toggle_enables_strip_tracks(self, app):
        app.hardfi_var.set(True)
        app._on_hardfi_toggle()
        assert app.strip_tracks_var.get() is True
        assert str(app.strip_tracks_cb.cget("state")) == "normal"

    def test_hardfi_untoggle_disables_strip_tracks(self, app):
        app.hardfi_var.set(True)
        app._on_hardfi_toggle()
        app.hardfi_var.set(False)
        app._on_hardfi_toggle()
        assert app.strip_tracks_var.get() is False
        assert str(app.strip_tracks_cb.cget("state")) == "disabled"

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


class TestProcessDialog:
    def test_none_request_does_nothing(self, app):
        app._dialog_request = None
        app._dialog_event.clear()
        app._process_dialog()
        assert not app._dialog_event.is_set()

    def test_dir_overwrite(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesnocancel",
            lambda t, m: True,
        )
        app._dialog_request = ("dir", "MyAlbum")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "overwrite"
        assert app._dialog_event.is_set()

    def test_dir_skip(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesnocancel",
            lambda t, m: False,
        )
        app._dialog_request = ("dir", "MyAlbum")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "skip"
        assert app._dialog_event.is_set()

    def test_dir_cancel(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesnocancel",
            lambda t, m: None,
        )
        app._dialog_request = ("dir", "MyAlbum")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "cancel"
        assert app._dialog_event.is_set()

    def test_file_skip(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'skip'})(),
        )
        app._dialog_request = ("file", "Album", "t.mp3")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "skip"
        assert app._dialog_event.is_set()

    def test_file_overwrite(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'overwrite'})(),
        )
        app._dialog_request = ("file", "Album", "t.mp3")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "overwrite"
        assert app._dialog_event.is_set()

    def test_file_overwrite_all(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'overwrite_all'})(),
        )
        app._dialog_request = ("file", "Album", "t.mp3")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "overwrite_all"
        assert app._dialog_event.is_set()

    def test_file_cancel(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'cancel'})(),
        )
        app._dialog_request = ("file", "Album", "t.mp3")
        app._dialog_event.clear()
        app._process_dialog()
        assert app._dialog_result == "cancel"
        assert app._dialog_event.is_set()


class TestOptionDialog:
    def test_done_sets_result(self):
        dlg = _OptionDialog.__new__(_OptionDialog)
        dlg.result = None
        destroyed = []
        dlg.destroy = lambda: destroyed.append(True)
        dlg._done("test_value")
        assert dlg.result == "test_value"
        assert destroyed == [True]

    def test_constructor_creates_widgets(self, app, monkeypatch):
        monkeypatch.setattr(_OptionDialog, "wait_window", lambda self: None)
        dlg = _OptionDialog(app.root, "Title", "Message", [("Skip", "skip")])
        assert dlg.title() == "Title"
        assert dlg.result is None


class TestMusicBrainzSearchDialog:
    def test_constructor_creates_widgets(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog.wait_window",
            lambda self: None,
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog._do_search",
            lambda self: None,
        )
        dlg = _MusicBrainzSearchDialog(app.root, "Dido", "Life For Rent")
        assert dlg.title() == "MusicBrainz Lookup"
        assert dlg.result is None

    def test_on_cancel_sets_none(self):
        dlg = _MusicBrainzSearchDialog.__new__(_MusicBrainzSearchDialog)
        dlg.result = "something"
        destroyed = []
        dlg.destroy = lambda: destroyed.append(True)
        dlg._on_cancel()
        assert dlg.result is None
        assert destroyed == [True]

    def test_on_ok_no_selection_does_nothing(self):
        dlg = _MusicBrainzSearchDialog.__new__(_MusicBrainzSearchDialog)
        dlg.result = None
        dlg._album_listbox = type("L", (), {"curselection": lambda s: []})()
        dlg._album_data = []
        dlg._on_ok()
        assert dlg.result is None


class TestReleaseSelectionDialog:
    def test_on_cancel_sets_none(self):
        dlg = _ReleaseSelectionDialog.__new__(_ReleaseSelectionDialog)
        dlg.result = "something"
        destroyed = []
        dlg.destroy = lambda: destroyed.append(True)
        dlg._on_cancel()
        assert dlg.result is None
        assert destroyed == [True]

    def test_on_ok_sets_result(self):
        dlg = _ReleaseSelectionDialog.__new__(_ReleaseSelectionDialog)
        dlg.result = None
        dlg._candidates = [
            {"id": "1", "title": "Original", "year": "1985", "artist": "Artist"},
            {"id": "2", "title": "Remaster", "year": "1996", "artist": "Artist"},
        ]
        dlg._release_listbox = type("L", (), {"curselection": lambda s: (1,)})()
        destroyed = []
        dlg.destroy = lambda: destroyed.append(True)
        dlg._on_ok()
        assert dlg.result == "2"
        assert destroyed == [True]

    def test_on_ok_no_selection_does_nothing(self):
        dlg = _ReleaseSelectionDialog.__new__(_ReleaseSelectionDialog)
        dlg.result = None
        dlg._candidates = []
        dlg._release_listbox = type("L", (), {"curselection": lambda s: ()})()
        destroyed = []
        dlg.destroy = lambda: destroyed.append(True)
        dlg._on_ok()
        assert dlg.result is None
        assert destroyed == []


class TestConfirmDir:
    def test_overwrite(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesnocancel",
            lambda t, m: True,
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_dir("Album") == "overwrite"

    def test_skip(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesnocancel",
            lambda t, m: False,
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_dir("Album") == "skip"

    def test_cancel(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesnocancel",
            lambda t, m: None,
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_dir("Album") == "cancel"


class TestConfirmFile:
    def test_overwrite(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'overwrite'})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_file("Album", "t.mp3") == "overwrite"

    def test_overwrite_all(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'overwrite_all'})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_file("Album", "t.mp3") == "overwrite_all"

    def test_skip(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'skip'})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_file("Album", "t.mp3") == "skip"

    def test_cancel(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._OptionDialog",
            lambda parent, title, message, options: type('D', (), {'result': 'cancel'})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        assert app._confirm_file("Album", "t.mp3") == "cancel"


class TestMusicBrainzRequestMethods:
    def test_request_musicbrainz_search(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog",
            lambda parent, artist, album: type("D", (), {"result": "release-123"})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        result = app._request_musicbrainz_search("Dido", "Life For Rent")
        assert result == "release-123"

    def test_request_musicbrainz_search_none(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog",
            lambda parent, artist, album: type("D", (), {"result": None})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        result = app._request_musicbrainz_search("Dido", "Life For Rent")
        assert result is None

    def test_request_confirm_fallback_yes(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesno", lambda t, m: True
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        result = app._request_confirm_fallback("Dido", "Life For Rent")
        assert result is True

    def test_request_confirm_fallback_no(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesno", lambda t, m: False
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        result = app._request_confirm_fallback("Dido", "Life For Rent")
        assert result is False


class TestReleaseSelectionRequest:
    def test_request_release_selection(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._ReleaseSelectionDialog",
            lambda parent, candidates, artist, album: type("D", (), {"result": "release-456"})(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))
        candidates = [{"id": "release-456", "title": "Brothers in Arms", "year": "1985", "artist": "Dire Straits"}]
        result = app._request_release_selection(candidates, "Dire Straits", "Brothers in Arms")
        assert result == "release-456"


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

        app._sync_worker(str(src), str(dst), 0, app.sync_progress, strip_tracks=False, do_dot_clean=False)

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

        app._sync_worker(str(src), str(dst), 0, app.sync_progress, strip_tracks=False, do_dot_clean=True)
        assert app._sync_result is True

    def test_sync_worker_hardfi(self, app, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        album = src / "Artist   Album"
        album.mkdir()
        (album / "01 a.mp3").write_text("x")
        (album / "02 b.mp3").write_text("x")

        from vinylstudio_to_jb7.sync import SyncProgress

        app.dot_clean_var.set(False)
        app.sync_progress = SyncProgress()
        hardfi_dir = os.path.join(str(dst), "hardfi")

        app._sync_worker(str(src), str(dst), 0, app.sync_progress, hardfi_dir, strip_tracks=False, do_dot_clean=False)
        assert app._sync_result is True
        assert os.path.exists(os.path.join(hardfi_dir, "Artist   Album", "01 a.mp3"))
        assert os.path.exists(os.path.join(hardfi_dir, "Artist   Album", "02 b.mp3"))


class TestGenerateIdFiles:
    def test_generates_id_files_for_albums(self, app, tmp_path, monkeypatch):
        album_dir = tmp_path / "Dido   Life For Rent"
        album_dir.mkdir()
        (album_dir / "01 White Flag.mp3").write_text("x")
        (album_dir / "02 Stoned.mp3").write_text("x")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.search_releases",
            lambda a, t: [{"id": "abc", "title": "Life For Rent", "year": "2003", "artist": "Dido"}],
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.get_release_metadata",
            lambda rid: type("M", (), {
                "artist": "Dido", "title": "Life For Rent", "year": "2003",
                "genre": "Alternative Rock", "tracks": ["White Flag", "Stoned"],
                "is_various": False,
            })(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))

        from vinylstudio_to_jb7.sync import SyncProgress
        app._generate_id_files(str(tmp_path), SyncProgress())

        id_file = album_dir / "id"
        assert id_file.exists()
        content = id_file.read_text()
        assert "Dido / Life For Rent" in content
        assert "White Flag" in content
        assert "Stoned" in content

    def test_skip_when_user_declines_fallback(self, app, tmp_path, monkeypatch):
        album_dir = tmp_path / "Unknown   Album"
        album_dir.mkdir()
        (album_dir / "01 track.mp3").write_text("x")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.search_releases", lambda a, t: []
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog",
            lambda parent, artist, album: type("D", (), {"result": None})(),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesno", lambda t, m: False
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))

        from vinylstudio_to_jb7.sync import SyncProgress
        app._generate_id_files(str(tmp_path), SyncProgress())

        id_file = album_dir / "id"
        assert not id_file.exists()

    def test_uses_fallback_when_confirmed(self, app, tmp_path, monkeypatch):
        album_dir = tmp_path / "Unknown   Album"
        album_dir.mkdir()
        (album_dir / "01 track.mp3").write_text("x")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.search_releases", lambda a, t: []
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog",
            lambda parent, artist, album: type("D", (), {"result": None})(),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.messagebox.askyesno", lambda t, m: True
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))

        from vinylstudio_to_jb7.sync import SyncProgress
        app._generate_id_files(str(tmp_path), SyncProgress())

        id_file = album_dir / "id"
        assert id_file.exists()
        content = id_file.read_text()
        assert "Unknown / Album" in content
        assert "1970" in content
        assert "Unknown" in content


    def test_selects_from_multiple_exact_matches(self, app, tmp_path, monkeypatch):
        album_dir = tmp_path / "Dire Straits   Brothers in Arms"
        album_dir.mkdir()
        (album_dir / "01 So Far Away.mp3").write_text("x")

        candidates = [
            {"id": "orig", "title": "Brothers in Arms", "year": "1985", "artist": "Dire Straits"},
            {"id": "remaster", "title": "Brothers in Arms", "year": "1996", "artist": "Dire Straits"},
        ]
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.search_releases", lambda a, t: candidates
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._ReleaseSelectionDialog",
            lambda parent, candidates, artist, album: type("D", (), {"result": "orig"})(),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.get_release_metadata",
            lambda rid: type("M", (), {
                "artist": "Dire Straits", "title": "Brothers in Arms", "year": "1985",
                "genre": "Rock", "tracks": ["So Far Away"], "is_various": False,
            })(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))

        from vinylstudio_to_jb7.sync import SyncProgress
        app._generate_id_files(str(tmp_path), SyncProgress())

        id_file = album_dir / "id"
        assert id_file.exists()
        content = id_file.read_text()
        assert "1985" in content
        assert "1996" not in content

    def test_multiple_matches_user_cancels_opens_manual(self, app, tmp_path, monkeypatch):
        album_dir = tmp_path / "Dire Straits   Brothers in Arms"
        album_dir.mkdir()
        (album_dir / "01 track.mp3").write_text("x")

        candidates = [
            {"id": "orig", "title": "Brothers in Arms", "year": "1985", "artist": "Dire Straits"},
            {"id": "remaster", "title": "Brothers in Arms", "year": "1996", "artist": "Dire Straits"},
        ]
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.search_releases", lambda a, t: candidates
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._ReleaseSelectionDialog",
            lambda parent, c, a, album: type("D", (), {"result": None})(),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog",
            lambda parent, artist, album: type("D", (), {"result": "remaster"})(),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.get_release_metadata",
            lambda rid: type("M", (), {
                "artist": "Dire Straits", "title": "Brothers in Arms", "year": "1996",
                "genre": "Rock", "tracks": ["track"], "is_various": False,
            })(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))

        from vinylstudio_to_jb7.sync import SyncProgress
        app._generate_id_files(str(tmp_path), SyncProgress())

        id_file = album_dir / "id"
        assert id_file.exists()
        assert "1996" in id_file.read_text()

    def test_no_exact_match_opens_manual_search(self, app, tmp_path, monkeypatch):
        album_dir = tmp_path / "Dire Straits   Brothers"
        album_dir.mkdir()
        (album_dir / "01 track.mp3").write_text("x")

        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.search_releases",
            lambda a, t: [{"id": "abc", "title": "Brothers in Arms", "year": "1985", "artist": "Dire Straits"}],
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._MusicBrainzSearchDialog",
            lambda parent, artist, album: type("D", (), {"result": "abc"})(),
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app.get_release_metadata",
            lambda rid: type("M", (), {
                "artist": "Dire Straits", "title": "Brothers in Arms", "year": "1985",
                "genre": "Rock", "tracks": ["track"], "is_various": False,
            })(),
        )
        monkeypatch.setattr(app.root, "after", lambda ms, fn, *a: fn(*a))

        from vinylstudio_to_jb7.sync import SyncProgress
        app._generate_id_files(str(tmp_path), SyncProgress())

        id_file = album_dir / "id"
        assert id_file.exists()
        assert "1985" in id_file.read_text()

    def test_release_selection_constructor(self, app, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.app._ReleaseSelectionDialog.wait_window",
            lambda self: None,
        )
        candidates = [{"id": "1", "title": "Album", "year": "2000", "artist": "Artist"}]
        dlg = _ReleaseSelectionDialog(app.root, candidates, "Artist", "Album")
        assert dlg.title() == "Select Release"
        assert dlg.result is None


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
