import os
import tempfile
import threading
import time

import pytest

from vinylstudio_to_jb7.sync import (
    SyncProgress,
    _sleep_with_cancel,
    has_subdirectories,
    resolve_target,
    sync_directories,
)


def _flat_target(dst: str, src: str) -> str:
    return os.path.join(dst, os.path.basename(os.path.normpath(src)))


class TestHasSubdirectories:
    def test_flat_source(self, tmp_path):
        d = tmp_path / "src"
        d.mkdir()
        (d / "file.txt").write_text("x")
        assert has_subdirectories(str(d)) is False

    def test_with_subdirs(self, tmp_path):
        d = tmp_path / "src"
        d.mkdir()
        sub = d / "sub"
        sub.mkdir()
        assert has_subdirectories(str(d)) is True

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "src"
        d.mkdir()
        assert has_subdirectories(str(d)) is False

    def test_not_a_dir(self):
        assert has_subdirectories("/nonexistent") is False

    def test_permission_error(self, monkeypatch):
        def bad_listdir(p):
            raise PermissionError("denied")
        monkeypatch.setattr(os, "listdir", bad_listdir)
        assert has_subdirectories("/some/path") is False


class TestResolveTarget:
    def test_flat_source(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "f.txt").write_text("x")
        dst = tmp_path / "dst"
        dst.mkdir()
        expected = os.path.join(str(dst), "src")
        assert resolve_target(str(src), str(dst)) == expected

    def test_source_with_subdirs(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "sub").mkdir()
        dst = tmp_path / "dst"
        dst.mkdir()
        assert resolve_target(str(src), str(dst)) == str(dst)

    def test_hidden_dir_counts_as_subdir(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / ".hidden").mkdir()
        dst = tmp_path / "dst"
        dst.mkdir()
        assert resolve_target(str(src), str(dst)) == str(dst)

    def test_empty_source_is_flat(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        dst.mkdir()
        expected = os.path.join(str(dst), "src")
        assert resolve_target(str(src), str(dst)) == expected


class TestSyncProgress:
    def test_init(self):
        p = SyncProgress()
        assert p.cancelled is False

    def test_cancel(self):
        p = SyncProgress()
        p.cancel()
        assert p.cancelled is True


class TestSyncDirectories:
    def test_basic_copy_flat_source(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                for i in range(3):
                    with open(os.path.join(src, f"f{i}.txt"), "w") as f:
                        f.write(f"content{i}")

                logs = []
                p = SyncProgress()
                result = sync_directories(src, dst, 0, p, logs.append)

                target = _flat_target(dst, src)
                assert result is True
                assert os.path.exists(os.path.join(target, "f0.txt"))
                assert os.path.exists(os.path.join(target, "f1.txt"))
                assert os.path.exists(os.path.join(target, "f2.txt"))
                assert len(logs) > 0

    def test_nested_directories_source(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                os.makedirs(os.path.join(src, "a", "b"))
                with open(os.path.join(src, "a", "b", "nested.txt"), "w") as f:
                    f.write("nested")
                with open(os.path.join(src, "root.txt"), "w") as f:
                    f.write("root")

                logs = []
                p = SyncProgress()
                result = sync_directories(src, dst, 0, p, logs.append)

                assert result is True
                assert os.path.exists(os.path.join(dst, "root.txt"))
                assert os.path.exists(os.path.join(dst, "a", "b", "nested.txt"))

    def test_empty_source(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                logs = []
                p = SyncProgress()
                result = sync_directories(src, dst, 0, p, logs.append)
                assert result is True
                assert "0 files copied" in logs[-1]

    def test_src_not_exist(self):
        with tempfile.TemporaryDirectory() as dst:
            logs = []
            p = SyncProgress()
            result = sync_directories("/nonexistent/path", dst, 0, p, logs.append)
            assert result is False
            assert "ERROR" in logs[0]

    def test_dst_not_exist(self):
        with tempfile.TemporaryDirectory() as src:
            logs = []
            p = SyncProgress()
            result = sync_directories(src, "/nonexistent/dst", 0, p, logs.append)
            assert result is False
            assert "ERROR" in logs[0]

    def test_pause_respected_flat(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                for i in range(3):
                    with open(os.path.join(src, f"f{i}.txt"), "w") as f:
                        f.write(f"c{i}")

                logs = []
                p = SyncProgress()
                start = time.time()
                result = sync_directories(src, dst, 0.3, p, logs.append)
                elapsed = time.time() - start

                assert result is True
                assert elapsed >= 0.5

    def test_cancel_during_first_pass(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                for i in range(100):
                    with open(os.path.join(src, f"f{i}.txt"), "w") as f:
                        f.write("x")

                logs = []
                p = SyncProgress()

                def cancel_later():
                    time.sleep(0.01)
                    p.cancel()

                threading.Thread(target=cancel_later, daemon=True).start()
                result = sync_directories(src, dst, 0, p, logs.append)
                assert result is False
                assert any("cancelled" in l.lower() for l in logs)

    def test_cancel_during_second_pass(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                with open(os.path.join(src, "f0.txt"), "w") as f:
                    f.write("x")
                os.makedirs(os.path.join(src, "slowdir"))
                with open(os.path.join(src, "slowdir", "f1.txt"), "w") as f:
                    f.write("x")

                logs = []
                p = SyncProgress()

                def cancel_later():
                    time.sleep(0.05)
                    p.cancel()

                threading.Thread(target=cancel_later, daemon=True).start()
                result = sync_directories(src, dst, 0.5, p, logs.append)

                assert result is False

    def test_copy_error_continues(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                with open(os.path.join(src, "good.txt"), "w") as f:
                    f.write("good")

                logs = []
                p = SyncProgress()

                def broken_copy2(*args, **kwargs):
                    raise PermissionError("denied")

                import shutil
                original = shutil.copy2
                shutil.copy2 = broken_copy2
                try:
                    result = sync_directories(src, dst, 0, p, logs.append)
                    assert result is True
                    assert any("ERROR" in l for l in logs)
                    assert "0 files copied" in logs[-1]
                finally:
                    shutil.copy2 = original

    def test_flat_creates_subdir_on_target(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                (src / "f.txt" if hasattr(src, "__fspath__") else None)
                with open(os.path.join(src, "track.mp3"), "w") as f:
                    f.write("data")

                logs = []
                p = SyncProgress()
                result = sync_directories(src, dst, 0, p, logs.append)

                target = _flat_target(dst, src)
                assert result is True
                assert os.path.isdir(target)
                assert os.path.exists(os.path.join(target, "track.mp3"))

    def test_nested_does_not_create_extra_wrapper(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                os.makedirs(os.path.join(src, "album1"))
                with open(os.path.join(src, "album1", "t1.mp3"), "w") as f:
                    f.write("data")

                logs = []
                p = SyncProgress()
                result = sync_directories(src, dst, 0, p, logs.append)

                src_basename = os.path.basename(os.path.normpath(src))
                wrapper = os.path.join(dst, src_basename, "album1", "t1.mp3")
                direct = os.path.join(dst, "album1", "t1.mp3")
                assert result is True
                assert os.path.exists(direct)
                assert not os.path.exists(wrapper)

    def test_log_shows_target_base(self):
        with tempfile.TemporaryDirectory() as src:
            with tempfile.TemporaryDirectory() as dst:
                with open(os.path.join(src, "f.txt"), "w") as f:
                    f.write("x")

                logs = []
                p = SyncProgress()
                result = sync_directories(src, dst, 0, p, logs.append)
                assert result is True
                target = _flat_target(dst, src)
                assert target in logs[-1]


class TestSleepWithCancel:
    def test_sleep_completes(self):
        p = SyncProgress()
        start = time.time()
        _sleep_with_cancel(0.2, p)
        elapsed = time.time() - start
        assert elapsed >= 0.15

    def test_cancel_during_sleep(self):
        p = SyncProgress()

        def cancel_later():
            time.sleep(0.05)
            p.cancel()

        threading.Thread(target=cancel_later, daemon=True).start()
        start = time.time()
        _sleep_with_cancel(5, p)
        elapsed = time.time() - start
        assert elapsed < 1.0
