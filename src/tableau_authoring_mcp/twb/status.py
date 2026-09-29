"""What a workbook is and whether it's safe to touch: build, Desktop lock, backups, size of the thing.

Desktop writes an autosave file `.~<name>__<pid>.twbr` next to a workbook while it has it open, and deletes it
on a clean close. After a crash the file stays behind, so a lock file alone doesn't prove Desktop has the
workbook open. On the Mac we can check whether that process is still running; on Linux (where the file
arrives through Syncthing) we can't, so the answer is "unknown" and write tools must treat it as open.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .document import Document

_BUILD_COMMENT = re.compile(rb"<!--\s*build\s+(\d{5}\.\d+\.\d+\.\d+)\s*-->")
_SOURCE_BUILD = re.compile(r"\((\d{5}\.\d+\.\d+\.\d+)\)")
_LOCK = re.compile(r"^\.~(?P<stem>.+)__(?P<pid>\d+)\.twbr$")

DesktopState = Literal["closed", "open", "stale-lock", "unknown"]


class LockFile(BaseModel):
    name: str
    pid: int
    modified: str = Field(description="Last modified, ISO 8601 UTC")
    process_running: bool | None = Field(
        description="Whether that Desktop process is still running; null when it can't be checked here"
    )


class Backup(BaseModel):
    name: str = Field(description="File name, e.g. sales.before-add-filter.twb")
    change: str = Field(description="The change it was taken before, from the file name")
    modified: str = Field(description="Last modified, ISO 8601 UTC")


class WorkbookStatus(BaseModel):
    path: str = Field(description="Absolute path")
    format: Literal["twb", "twbx"]
    size_bytes: int
    tableau_build: str | None = Field(description="Build that saved it, e.g. 20262.26.0819.2015")
    tableau_release: str | None = Field(description="Release derived from the build, e.g. 2026.2")
    version_attribute: str | None = Field(
        description="The <workbook version> attribute. Desktop always writes 18.1; don't use it to pick a schema"
    )
    desktop: DesktopState = Field(
        description="closed; open (Desktop is running with it); stale-lock (lock left by a crashed Desktop); "
        "unknown (lock present but this machine can't see Desktop's processes, e.g. Linux)"
    )
    lock_files: list[LockFile]
    backups: list[Backup] = Field(description="Backups next to it, newest first")
    datasources: int
    worksheets: int
    dashboards: int
    notes: list[str] = Field(description="Plain-language warnings and next steps")


def workbook_status(path: str | os.PathLike) -> WorkbookStatus:
    p = Path(path).expanduser().resolve()
    doc = Document.load(p)
    root = doc.root
    build = _build(doc.raw, root.get("source-build"))
    locks = lock_files(p)
    state = desktop_state(locks)
    notes: list[str] = []
    if state == "open":
        notes.append(
            "Tableau Desktop has this workbook open. Close it in Desktop before any write: "
            "a Desktop save would overwrite changes made here."
        )
    elif state == "unknown":
        notes.append(
            "A Desktop lock file is present, but this machine can't see whether Desktop is running. "
            f"Treat the workbook as open until the owner confirms Desktop has closed it{_age_hint(locks)}."
        )
    elif state == "stale-lock":
        notes.append(
            "A lock file was left by a Desktop process that is no longer running (a crash). It may hold "
            "unsaved work; check it before deleting."
        )
    if root.get("version") and root.get("version") != "18.1":
        notes.append(f"version='{root.get('version')}' is unusual; Desktop-saved workbooks say 18.1.")
    if build is None:
        notes.append("No build comment or source-build attribute: this file may not have been saved by Tableau.")
    return WorkbookStatus(
        path=str(p),
        format="twbx" if p.suffix.lower() == ".twbx" else "twb",
        size_bytes=p.stat().st_size,
        tableau_build=build,
        tableau_release=release_from_build(build),
        version_attribute=root.get("version"),
        desktop=state,
        lock_files=locks,
        backups=backups(p),
        datasources=len(root.findall("./datasources/datasource")),
        worksheets=len(root.findall("./worksheets/worksheet")),
        dashboards=len(root.findall("./dashboards/dashboard")),
        notes=notes,
    )


def _build(raw: bytes, source_build: str | None) -> str | None:
    m = _BUILD_COMMENT.search(raw[:2048])
    if m:
        return m.group(1).decode()
    if source_build:
        m2 = _SOURCE_BUILD.search(source_build)
        if m2:
            return m2.group(1)
    return None


def release_from_build(build: str | None) -> str | None:
    """'20262.26.0819.2015' -> '2026.2'."""
    if not build or len(build) < 5 or not build[:5].isdigit():
        return None
    return f"{build[:4]}.{build[4]}"


def lock_files(path: Path) -> list[LockFile]:
    found = []
    for f in path.parent.glob(".~*.twbr"):
        m = _LOCK.match(f.name)
        if not m or m.group("stem") != path.stem:
            continue
        pid = int(m.group("pid"))
        found.append(LockFile(name=f.name, pid=pid, modified=_mtime(f), process_running=_desktop_running(pid)))
    return sorted(found, key=lambda lf: lf.modified, reverse=True)


def desktop_state(locks: list[LockFile]) -> DesktopState:
    if not locks:
        return "closed"
    running = [lf.process_running for lf in locks]
    if any(r is True for r in running):
        return "open"
    if all(r is False for r in running):
        return "stale-lock"
    return "unknown"


def backups(path: Path) -> list[Backup]:
    prefix = f"{path.stem}.before-"
    found = [
        Backup(name=f.name, change=f.name[len(prefix) : -len(f.suffix)], modified=_mtime(f))
        for f in path.parent.iterdir()
        if f.name.startswith(prefix) and f.suffix.lower() == path.suffix.lower()
    ]
    return sorted(found, key=lambda b: b.modified, reverse=True)


def _age_hint(locks: list[LockFile]) -> str:
    """' (the lock was last written 15 days ago, so it's probably left over from a crash)' for old locks."""
    newest = max(datetime.fromisoformat(lf.modified) for lf in locks)
    days = (datetime.now(UTC) - newest).days
    if days < 1:
        return ""
    plural = "s" if days != 1 else ""
    return f" (the lock was last written {days} day{plural} ago, so it's probably left over from a crash)"


def _mtime(f: Path) -> str:
    return datetime.fromtimestamp(f.stat().st_mtime, UTC).isoformat(timespec="seconds")


def _desktop_running(pid: int) -> bool | None:
    """On macOS, whether `pid` is a running Tableau process. None where that can't be known."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return "Tableau" in out.stdout
