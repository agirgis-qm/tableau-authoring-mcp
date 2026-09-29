import os
import time

from tableau_authoring_mcp.twb.status import release_from_build, workbook_status


def test_status_reads_build_counts_and_version(minimal):
    s = workbook_status(minimal)
    assert s.tableau_build == "20262.26.0819.2015"
    assert s.tableau_release == "2026.2"
    assert s.version_attribute == "18.1"
    assert (s.datasources, s.worksheets, s.dashboards) == (1, 1, 1)
    assert s.desktop == "closed"
    assert s.lock_files == [] and s.backups == [] and s.notes == []


def test_lock_file_on_linux_is_unknown_not_closed(minimal, monkeypatch):
    monkeypatch.setattr("tableau_authoring_mcp.twb.status.sys.platform", "linux")
    (minimal.parent / ".~minimal__4242.twbr").write_text("autosave")
    (minimal.parent / ".~other__1.twbr").write_text("someone else's")
    s = workbook_status(minimal)
    assert s.desktop == "unknown"
    assert [lf.pid for lf in s.lock_files] == [4242]
    assert "can't see whether Desktop is running" in s.notes[0]


def test_lock_file_with_dead_process_on_mac_is_stale(minimal, monkeypatch):
    monkeypatch.setattr("tableau_authoring_mcp.twb.status._desktop_running", lambda pid: False)
    (minimal.parent / ".~minimal__4242.twbr").write_text("autosave")
    assert workbook_status(minimal).desktop == "stale-lock"


def test_lock_file_with_running_desktop_is_open(minimal, monkeypatch):
    monkeypatch.setattr("tableau_authoring_mcp.twb.status._desktop_running", lambda pid: True)
    (minimal.parent / ".~minimal__4242.twbr").write_text("autosave")
    s = workbook_status(minimal)
    assert s.desktop == "open"
    assert "Close it in Desktop" in s.notes[0]


def test_backups_are_listed_newest_first(minimal):
    old = minimal.parent / "minimal.before-add-filter.twb"
    new = minimal.parent / "minimal.before-set-captions.twb"
    old.write_text("x")
    new.write_text("x")
    past = time.time() - 3600
    os.utime(old, (past, past))
    s = workbook_status(minimal)
    assert [b.change for b in s.backups] == ["set-captions", "add-filter"]


def test_release_from_build():
    assert release_from_build("20252.25.0101.0000") == "2025.2"
    assert release_from_build(None) is None
    assert release_from_build("junk") is None
