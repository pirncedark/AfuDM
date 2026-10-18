"""Torrent reuse, completion policy and actionable launch errors; no network."""
import base64
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import daemon, trackers
from core.db import Store
from core.manager import Manager
from core.rpc import Aria2Error


@pytest.fixture
def manager():
    mgr = object.__new__(Manager)
    mgr.store = Store(":memory:")
    mgr.rpc = Mock()
    mgr.rpc.tell_waiting.return_value = []
    mgr.rpc.add_torrent.return_value = "torrent-gid"
    mgr.rpc.add_uri.return_value = "uri-gid"
    yield mgr
    mgr.store.conn.close()


def torrent_file(tmp_path, name=b"Game", body=None):
    # A hand-built, valid single-file torrent, independent of the reader.
    if body is None:
        body = (b"d4:infod6:lengthi4e4:name" + str(len(name)).encode()
                + b":" + name + b"12:piece lengthi4e6:pieces20:"
                + b"a" * 20 + b"ee")
    source = tmp_path / "update.torrent"
    source.write_bytes(body)
    return source


def row(source, options=None):
    return {"id": 1, "source": str(source), "options": json.dumps(options or {})}


def test_download_completion_does_not_wait_for_seeding(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon.netcheck, "aria2_ipv6_args", lambda: [])
    assert "--seed-time=0" in daemon._args("test", str(tmp_path))


@pytest.mark.parametrize("name", [b"Game", "Türkçe oyun".encode()])
@pytest.mark.parametrize("is_dir", [True, False])
def test_existing_torrent_root_enables_hash_check(manager, tmp_path, name, is_dir):
    source = torrent_file(tmp_path, name)
    dest = tmp_path / "downloads"
    dest.mkdir()
    root = dest / name.decode()
    if is_dir:
        root.mkdir()
    else:
        root.write_bytes(b"old!")
    manager._launch_torrent(row(source), str(dest))
    payload, options = manager.rpc.add_torrent.call_args.args
    assert base64.b64decode(payload) == source.read_bytes()
    assert options["check-integrity"] == "true"
    assert options["dir"] == str(dest)
    assert options["bt-save-metadata"] == "false"


def test_new_torrent_does_not_enable_hash_check(manager, tmp_path):
    source = torrent_file(tmp_path)
    (tmp_path / "another-game").mkdir()
    manager._launch_torrent(row(source), str(tmp_path))
    assert "check-integrity" not in manager.rpc.add_torrent.call_args.args[1]


def test_multifile_torrent_checks_existing_game_directory(manager, tmp_path):
    source = torrent_file(tmp_path, body=(
        b"d4:infod5:filesld6:lengthi4e4:pathl8:data.bineee4:name4:Game"
        b"12:piece lengthi4e6:pieces20:" + b"a" * 20 + b"ee"
    ))
    (tmp_path / "Game").mkdir()
    (tmp_path / "Game" / "data.bin").write_bytes(b"old!")
    manager._launch_torrent(row(source), str(tmp_path))
    assert manager.rpc.add_torrent.call_args.args[1]["check-integrity"] == "true"


@pytest.mark.parametrize("name", [b"../Game", b"..\\Game", b"/Game", b"..", b"", b"\xff"])
def test_unusable_root_does_not_check_unrelated_files(manager, tmp_path, name):
    source = torrent_file(tmp_path, name)
    manager._launch_torrent(row(source), str(tmp_path))
    assert "check-integrity" not in manager.rpc.add_torrent.call_args.args[1]


@pytest.mark.parametrize("body", [b"invalid", b"d4:info4:Gamee", b"d4:infodee"])
def test_malformed_metadata_is_left_to_aria2(manager, tmp_path, body):
    source = torrent_file(tmp_path, body=body)
    assert manager._launch_torrent(row(source), str(tmp_path)) == "torrent-gid"
    assert "check-integrity" not in manager.rpc.add_torrent.call_args.args[1]


def test_magnet_without_metadata_keeps_normal_launch(manager, tmp_path):
    manager._launch_torrent(row("magnet:?xt=urn:btih:" + "a" * 40), str(tmp_path))
    assert "check-integrity" not in manager.rpc.add_uri.call_args.args[1]


@pytest.mark.parametrize("followed", [False, True])
def test_preview_adoption_checks_existing_root_before_resume(manager, tmp_path, followed):
    (tmp_path / "Game").mkdir()
    manager.rpc.tell_status.side_effect = (
        [{"followedBy": ["child"]}, {"bittorrent": {"info": {"name": "Game"}}}]
        if followed else [{"bittorrent": {"info": {"name": "Game"}}}]
    )
    manager._launch_torrent(row("magnet:?xt=urn:btih:abc", {"adopt_gid": "preview"}), str(tmp_path))
    gid = "child" if followed else "preview"
    assert manager.rpc.change_option.call_args.args == (
        gid, {"dir": str(tmp_path), "bt-save-metadata": "false", "check-integrity": "true"}
    )
    assert manager.rpc.unpause.call_args.args == (gid,)


def test_new_preview_keeps_normal_launch(manager, tmp_path):
    manager.rpc.tell_status.return_value = {"bittorrent": {"info": {"name": "Game"}}}
    manager._launch_torrent(row("magnet:?xt=urn:btih:abc", {"adopt_gid": "preview"}), str(tmp_path))
    assert "check-integrity" not in manager.rpc.change_option.call_args.args[1]


def test_local_preview_without_rpc_metadata_reads_torrent(manager, tmp_path):
    source = torrent_file(tmp_path)
    (tmp_path / "Game").mkdir()
    manager.rpc.tell_status.return_value = {}
    manager._launch_torrent(row(source, {"adopt_gid": "preview"}), str(tmp_path))
    assert manager.rpc.change_option.call_args.args[1]["check-integrity"] == "true"


def test_adopted_preview_disk_error_is_not_hidden_by_folder_error(manager, tmp_path):
    row_id = manager.store.add(kind="torrent", source="magnet:?xt=urn:btih:abc",
                               title="Game", dest_dir=str(tmp_path), options={"adopt_gid": "preview"})
    manager.rpc.tell_status.return_value = {}
    manager.rpc.change_option.side_effect = Aria2Error("There is not enough space")
    with pytest.raises(ValueError, match="Diskte yer yok"):
        manager._launch(manager.store.by_id(row_id))
    assert manager.store.by_id(row_id)["error"] == "Diskte yer yok. Başka bir klasör seçin ya da yer açın."
    manager.rpc.unpause.assert_not_called()


@pytest.mark.parametrize("message", ["not enough space", "There is not enough space", "NOT ENOUGH SPACE"])
def test_disk_space_failure_is_actionable_and_saved(manager, tmp_path, message):
    row_id = manager.store.add(kind="torrent", source="magnet:?xt=urn:btih:abc",
                               title="Game", dest_dir=str(tmp_path), options={})
    manager.rpc.add_uri.side_effect = Aria2Error(message)
    expected = "Diskte yer yok. Başka bir klasör seçin ya da yer açın."
    with pytest.raises(ValueError, match=expected):
        manager._launch(manager.store.by_id(row_id))
    saved = manager.store.by_id(row_id)
    assert saved["status"] == "error"
    assert saved["error"] == expected


def test_other_launch_errors_are_preserved(manager, tmp_path):
    row_id = manager.store.add(kind="torrent", source="magnet:?xt=urn:btih:abc",
                               title="Game", dest_dir=str(tmp_path), options={})
    manager.rpc.add_uri.side_effect = Aria2Error("connection refused")
    with pytest.raises(Aria2Error, match="connection refused"):
        manager._launch(manager.store.by_id(row_id))
    assert manager.store.by_id(row_id)["error"] == "connection refused"


def test_live_tracker_refresh_only_changes_global_options(manager):
    trackers.apply_to_aria2(manager.rpc, canli="udp://tracker.example.org:80/announce")
    assert manager.rpc.change_global_option.call_args.args == (
        {"bt-tracker": "udp://tracker.example.org:80/announce"},
    )
    manager.rpc.change_option.assert_not_called()
