"""Tests for the Dropbox ingest client (no network, no dropbox install needed).

We inject a fake ``dropbox`` module so the lazy import in ``_client`` resolves to
our stub, then assert that listing/download/longpoll call the right SDK methods
and that cursor pagination is handled.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingest import dropbox_client  # noqa: E402
from services.ingest.dropbox_client import (  # noqa: E402
    DropboxFile,
    download,
    list_new_files,
    longpoll,
)


class _FileMeta:
    def __init__(self, name, path, size, rev):
        self.name = name
        self.path_display = path
        self.size = size
        self.rev = rev


class _FolderMeta:
    """No ``rev`` attr -> should be filtered out."""

    def __init__(self, name):
        self.name = name
        self.path_display = "/raw-video/sub"


class _Result:
    def __init__(self, entries, cursor, has_more=False):
        self.entries = entries
        self.cursor = cursor
        self.has_more = has_more


class _LongpollResult:
    def __init__(self, changes):
        self.changes = changes


class _FakeDbx:
    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.calls = []
        # page 1 has_more -> page 2.
        self._pages = [
            _Result(
                [
                    _FileMeta("a.mov", "/raw-video/a.mov", 10, "rev_a"),
                    _FolderMeta("sub"),  # filtered
                ],
                cursor="cur1",
                has_more=True,
            ),
            _Result(
                [_FileMeta("b.mp4", "/raw-video/b.mp4", 20, "rev_b")],
                cursor="cur2",
                has_more=False,
            ),
        ]

    def files_list_folder(self, folder):
        self.calls.append(("list_folder", folder))
        return self._pages[0]

    def files_list_folder_continue(self, cursor):
        self.calls.append(("continue", cursor))
        if cursor == "cur1":
            return self._pages[1]
        # Subsequent-call path (cursor delta from a prior run).
        return _Result(
            [_FileMeta("c.mov", "/raw-video/c.mov", 30, "rev_c")],
            cursor="cur_next",
            has_more=False,
        )

    def files_list_folder_longpoll(self, cursor, timeout=30):
        self.calls.append(("longpoll", cursor, timeout))
        return _LongpollResult(changes=True)

    def files_download_to_file(self, local_path, dropbox_path):
        self.calls.append(("download", local_path, dropbox_path))
        with open(local_path, "wb") as f:
            f.write(b"fake video bytes")


def _install_fake_dropbox(captured: dict):
    mod = types.ModuleType("dropbox")

    def _ctor(**kwargs):
        dbx = _FakeDbx(**kwargs)
        captured["dbx"] = dbx
        return dbx

    mod.Dropbox = _ctor
    sys.modules["dropbox"] = mod
    return mod


def _set_refresh_env():
    os.environ["DROPBOX_APP_KEY"] = "k"
    os.environ["DROPBOX_APP_SECRET"] = "s"
    os.environ["DROPBOX_REFRESH_TOKEN"] = "r"
    os.environ.pop("DROPBOX_ACCESS_TOKEN", None)


def test_initial_listing_paginates_and_filters():
    captured: dict = {}
    _install_fake_dropbox(captured)
    _set_refresh_env()
    os.environ["DROPBOX_WATCH_FOLDER"] = "/raw-video"

    files, cursor = list_new_files(None)

    # Folder entry filtered; both file pages collected.
    names = [f.name for f in files]
    assert names == ["a.mov", "b.mp4"]
    assert all(isinstance(f, DropboxFile) for f in files)
    assert files[0].rev == "rev_a" and files[0].size_bytes == 10
    assert cursor == "cur2"

    dbx = captured["dbx"]
    # Refresh-token auth was used.
    assert dbx.init_kwargs.get("oauth2_refresh_token") == "r"
    assert dbx.init_kwargs.get("app_key") == "k"
    # Initial list then one continue for has_more.
    assert ("list_folder", "/raw-video") in dbx.calls
    assert ("continue", "cur1") in dbx.calls


def test_cursor_delta_uses_continue():
    captured: dict = {}
    _install_fake_dropbox(captured)
    _set_refresh_env()

    files, cursor = list_new_files("existing_cursor")
    assert [f.name for f in files] == ["c.mov"]
    assert cursor == "cur_next"
    dbx = captured["dbx"]
    assert dbx.calls[0] == ("continue", "existing_cursor")
    # No full list_folder call on the delta path.
    assert all(c[0] != "list_folder" for c in dbx.calls)


def test_longpoll_reports_changes():
    captured: dict = {}
    _install_fake_dropbox(captured)
    _set_refresh_env()
    assert longpoll("cur1", timeout=12) is True
    assert captured["dbx"].calls[-1] == ("longpoll", "cur1", 12)


def test_download_writes_file_and_calls_sdk(tmp=None):
    import tempfile

    captured: dict = {}
    _install_fake_dropbox(captured)
    _set_refresh_env()

    f = DropboxFile(path="/raw-video/a.mov", name="a.mov", size_bytes=10, rev="rev_a")
    with tempfile.TemporaryDirectory() as d:
        local = download(f, dest_dir=d)
        assert os.path.isfile(local)
        assert local.endswith("a.mov")
        with open(local, "rb") as fh:
            assert fh.read() == b"fake video bytes"
    dbx = captured["dbx"]
    assert any(c[0] == "download" and c[2] == "/raw-video/a.mov" for c in dbx.calls)


def test_access_token_fallback():
    captured: dict = {}
    _install_fake_dropbox(captured)
    for k in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"):
        os.environ.pop(k, None)
    os.environ["DROPBOX_ACCESS_TOKEN"] = "tok"
    list_new_files(None)
    assert captured["dbx"].init_kwargs.get("oauth2_access_token") == "tok"
    os.environ.pop("DROPBOX_ACCESS_TOKEN", None)


class RateLimitError(Exception):
    """Mimics dropbox.exceptions.RateLimitError (matched by class name)."""

    def __init__(self, backoff):
        super().__init__("too_many_requests")
        self.backoff = backoff


def test_rate_limit_retries_and_honors_backoff():
    import time as _time

    import services.ingest.dropbox_client as dc

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RateLimitError(backoff=0.01)
        return "ok"

    slept: list = []
    orig_sleep = _time.sleep
    _time.sleep = lambda s: slept.append(s)
    try:
        result = dc._call_with_retry(flaky)
    finally:
        _time.sleep = orig_sleep

    assert result == "ok"
    assert calls["n"] == 3
    assert slept == [0.01, 0.01]  # honored the backoff hint each retry


def test_non_rate_limit_error_not_retried():
    import services.ingest.dropbox_client as dc

    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("real bug")

    try:
        dc._call_with_retry(boom)
    except ValueError:
        pass
    else:
        raise AssertionError("non-rate-limit error must propagate")
    assert calls["n"] == 1  # not retried


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
