import os
import subprocess
import sys

import pytest

from vinylstudio_to_jb7.platform import (
    IS_MAC,
    IS_LINUX,
    IS_WINDOWS,
    _resolve_mac_disk,
    dot_clean_available,
    eject_volume,
    eject_volume_available,
    remove_metadata_files,
    run_dot_clean,
)


class TestDotCleanAvailable:
    def test_returns_false_when_not_mac(self, monkeypatch):
        monkeypatch.setattr("vinylstudio_to_jb7.platform.IS_MAC", False)
        assert dot_clean_available() is False

    def test_returns_false_when_not_installed(self, monkeypatch):
        monkeypatch.setattr("vinylstudio_to_jb7.platform.IS_MAC", True)
        monkeypatch.setattr("shutil.which", lambda x: None)
        assert dot_clean_available() is False

    def test_returns_true_when_available(self, monkeypatch):
        monkeypatch.setattr("vinylstudio_to_jb7.platform.IS_MAC", True)
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/dot_clean")
        assert dot_clean_available() is True


class TestRunDotClean:
    def test_not_available(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.dot_clean_available", lambda: False
        )
        ok, msg = run_dot_clean("/some/path")
        assert ok is False
        assert "not available" in msg

    def test_success(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.dot_clean_available", lambda: True
        )

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = run_dot_clean("/some/path")
        assert ok is True
        assert "completed" in msg

    def test_failure(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.dot_clean_available", lambda: True
        )

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "something went wrong"

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = run_dot_clean("/some/path")
        assert ok is False
        assert "failed" in msg

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.dot_clean_available", lambda: True
        )

        def mock_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, timeout=300)

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = run_dot_clean("/some/path")
        assert ok is False
        assert "timed out" in msg

    def test_file_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.dot_clean_available", lambda: True
        )

        def mock_run(cmd, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = run_dot_clean("/some/path")
        assert ok is False
        assert "not found" in msg

    def test_generic_exception(self, monkeypatch):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.dot_clean_available", lambda: True
        )

        def mock_run(cmd, **kwargs):
            raise PermissionError("access denied")

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = run_dot_clean("/some/path")
        assert ok is False
        assert "error" in msg


class TestEjectVolumeAvailable:
    def test_returns_true_any_platform(self, monkeypatch):
        for platform_name in [True, True, True]:
            monkeypatch.setattr(
                "vinylstudio_to_jb7.platform.IS_MAC", platform_name
            )
            monkeypatch.setattr(
                "vinylstudio_to_jb7.platform.IS_LINUX", False
            )
            monkeypatch.setattr(
                "vinylstudio_to_jb7.platform.IS_WINDOWS", False
            )
            assert eject_volume_available() is True

    @pytest.mark.parametrize("mac,linux,windows", [(False, False, False)])
    def test_returns_false_unknown_platform(
        self, monkeypatch, mac, linux, windows
    ):
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", mac
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", linux
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", windows
        )
        assert eject_volume_available() is False

    def test_always_true(self):
        assert eject_volume_available() is True


class TestEjectVolume:
    def test_path_not_exist(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: False)
        ok, msg = eject_volume("/nonexistent")
        assert ok is False
        assert "does not exist" in msg

    def test_mac_success(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform._resolve_mac_disk",
            lambda p: "/dev/disk2",
        )

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = "success"
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/Volumes/JB7")
        assert ok is True
        assert "Ejected" in msg

    def test_mac_no_disk_found(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform._resolve_mac_disk",
            lambda p: None,
        )
        ok, msg = eject_volume("/Volumes/JB7")
        assert ok is False
        assert "Could not find disk" in msg

    def test_mac_eject_fails(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform._resolve_mac_disk",
            lambda p: "/dev/disk2",
        )

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "not permitted"

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/Volumes/JB7")
        assert ok is False
        assert "failed" in msg.lower()

    def test_linux_success(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                class Result:
                    returncode = 0
                    stdout = "unmounted"
                    stderr = ""
                return Result()
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/mnt/usb")
        assert ok is True
        assert "Unmounted" in msg

    def test_linux_udisks_fails_eject_succeeds(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                class Result:
                    returncode = 1
                    stdout = ""
                    stderr = "not mounted"
                return Result()
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/mnt/usb")
        assert ok is True
        assert "Ejected" in msg

    def test_linux_both_fail(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            class Result:
                returncode = 1
                stdout = ""
                stderr = "failed"
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/mnt/usb")
        assert ok is False
        assert "failed" in msg.lower()

    def test_windows_success(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", True
        )
        monkeypatch.setattr(
            "os.path.splitdrive", lambda p: ("D:", "\\path")
        )

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("D:\\path")
        assert ok is True
        assert "Ejected" in msg

    def test_windows_no_drive_letter(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", True
        )
        monkeypatch.setattr("os.path.splitdrive", lambda p: ("", ""))

        ok, msg = eject_volume("//server/share")
        assert ok is False
        assert "drive letter" in msg.lower()

    def test_windows_eject_fails(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", True
        )
        monkeypatch.setattr(
            "os.path.splitdrive", lambda p: ("D:", "\\path")
        )

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "access denied"
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("D:\\path")
        assert ok is False
        assert "failed" in msg.lower()

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform._resolve_mac_disk",
            lambda p: "/dev/disk2",
        )

        def mock_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, timeout=60)

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/Volumes/JB7")
        assert ok is False
        assert "timed out" in msg

    def test_generic_exception(self, monkeypatch):
        monkeypatch.setattr("os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_MAC", True
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_LINUX", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform.IS_WINDOWS", False
        )
        monkeypatch.setattr(
            "vinylstudio_to_jb7.platform._resolve_mac_disk",
            lambda p: "/dev/disk2",
        )

        def mock_run(cmd, **kwargs):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(subprocess, "run", mock_run)
        ok, msg = eject_volume("/Volumes/JB7")
        assert ok is False
        assert "error" in msg


class TestResolveMacDisk:
    def test_success(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = "Filesystem  Size  Used Avail Use% Mounted on\n/dev/disk2s1  500G  200G  300G  40% /Volumes/JB7\n"
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _resolve_mac_disk("/Volumes/JB7")
        assert result == "/dev/disk2s1"


class TestRemoveMetadataFiles:
    def test_removes_ds_store(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        (d / ".DS_Store").write_text("garbage")
        (d / "track.mp3").write_text("audio")
        removed, errors = remove_metadata_files(str(d))
        assert removed == 1
        assert errors == []
        assert not (d / ".DS_Store").exists()
        assert (d / "track.mp3").exists()

    def test_removes_apple_double(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        (d / "._track.mp3").write_text("garbage")
        removed, errors = remove_metadata_files(str(d))
        assert removed == 1
        assert not (d / "._track.mp3").exists()

    def test_removes_localized(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        (d / ".localized").write_text("")
        removed, errors = remove_metadata_files(str(d))
        assert removed == 1

    def test_removes_thumbs_db(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        (d / "Thumbs.db").write_text("garbage")
        removed, errors = remove_metadata_files(str(d))
        assert removed == 1

    def test_removes_nested_files(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        sub = d / "album"
        sub.mkdir()
        (sub / ".DS_Store").write_text("garbage")
        (sub / "._track.mp3").write_text("garbage")
        (sub / "track.mp3").write_text("audio")
        (d / ".DS_Store").write_text("garbage")
        removed, errors = remove_metadata_files(str(d))
        assert removed == 3
        assert not (sub / ".DS_Store").exists()
        assert not (sub / "._track.mp3").exists()
        assert not (d / ".DS_Store").exists()
        assert (sub / "track.mp3").exists()

    def test_preserves_regular_hidden_files(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        (d / ".hiddenconfig").write_text("keep")
        removed, errors = remove_metadata_files(str(d))
        assert removed == 0
        assert (d / ".hiddenconfig").exists()

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "music"
        d.mkdir()
        removed, errors = remove_metadata_files(str(d))
        assert removed == 0
        assert errors == []

    def test_nonexistent_path_returns_zero(self):
        removed, errors = remove_metadata_files("/nonexistent")
        assert removed == 0
        assert errors == []

    def test_permission_error_on_file(self, tmp_path, monkeypatch):
        d = tmp_path / "music"
        d.mkdir()
        (d / ".DS_Store").write_text("x")

        def bad_remove(p):
            raise PermissionError("denied")

        monkeypatch.setattr(os, "remove", bad_remove)
        removed, errors = remove_metadata_files(str(d))
        assert removed == 0
        assert len(errors) == 1
        assert "denied" in errors[0]
