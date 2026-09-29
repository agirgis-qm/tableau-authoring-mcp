"""`tam`: developer commands that aren't MCP tools (checks over many files, corpus work)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .twb.document import WORKBOOK_SUFFIXES, Document, DocumentError
from .twb.status import workbook_status


def _files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for p in map(Path, paths):
        p = p.expanduser()
        if p.is_dir():
            found += sorted(
                f for f in p.rglob("*") if f.suffix.lower() in WORKBOOK_SUFFIXES and not f.name.startswith("._")
            )
        else:
            found.append(p)
    return found


def roundtrip(args: argparse.Namespace) -> int:
    """Load and re-serialize each workbook through the re-emit paths, and require identical bytes."""
    ok = failed = skipped = 0
    for f in _files(args.paths):
        try:
            doc = Document.load(f)
        except DocumentError as e:
            skipped += 1
            if args.verbose:
                print(f"SKIP  {f}: {e}")
            continue
        doc.force_reemit(args.level)
        try:
            out = doc.to_bytes()
        except DocumentError as e:
            failed += 1
            print(f"FAIL  {f}: {e}")
            continue
        if out == doc.raw:
            ok += 1
            if args.verbose:
                print(f"OK    {f}")
        else:
            failed += 1
            i = next((i for i, (a, b) in enumerate(zip(out, doc.raw, strict=False)) if a != b), len(out))
            print(f"DIFF  {f} at byte {i}: {doc.raw[max(0, i - 40) : i + 40]!r}")
    print(f"{ok} identical, {failed} different, {skipped} skipped")
    return 1 if failed else 0


def status(args: argparse.Namespace) -> int:
    try:
        print(json.dumps(workbook_status(args.path).model_dump(), indent=2))
    except DocumentError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tam", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    rt = sub.add_parser("roundtrip", help="check that load + save leaves workbooks byte-identical")
    rt.add_argument("paths", nargs="+", help="workbooks or folders (searched recursively)")
    rt.add_argument(
        "--level",
        choices=["root", "structure", "full"],
        default="structure",
        help="how much to force through re-serialization (default: structure)",
    )
    rt.add_argument("-v", "--verbose", action="store_true")
    rt.set_defaults(func=roundtrip)
    st = sub.add_parser("status", help="print twb-status for one workbook as JSON")
    st.add_argument("path")
    st.set_defaults(func=status)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
