"""Load and save Tableau XML without changing bytes nobody touched.

Tableau workbooks are large, Tableau-formatted XML: single-quoted attributes, `<tag />`, CRLF in some files,
CDATA inside datasource attributes. A normal XML library re-serializes all of that its own way, so saving an
unchanged file rewrites thousands of lines, diffs become unreadable, and nobody can see what a patch did.

So a `Document` keeps the original bytes. On load it parses twice: lxml builds the tree we edit, and expat
reports where every element, comment and processing instruction starts in the original bytes. On save, any
node whose content is unchanged is copied verbatim from the original; only changed or new nodes are
serialized, in Tableau's style. An unchanged file therefore round-trips byte for byte, and a patch changes
only the bytes it touches. The output is re-parsed and compared with the edited tree before it's returned,
so a change can't be lost or invented on the way out.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.parsers import expat

from lxml import etree

WORKBOOK_SUFFIXES = (".twb", ".twbx")
_XML_NS = "http://www.w3.org/XML/1998/namespace"

# A start tag, honouring quoted attribute values (which may legally contain '>').
_START_TAG = re.compile(rb"<[^\s/>]+(?:\s+[^\s=/>]+\s*=\s*(?:'[^']*'|\"[^\"]*\"))*\s*/?>")
_SELF_CLOSE_SUFFIX = re.compile(rb"\s*/>$")


class DocumentError(Exception):
    """A file that can't be loaded or saved; the message says why and what to do."""


@dataclass(slots=True)
class _Span:
    """Where a node sits in the original bytes. All offsets are byte indexes into `Document.raw`."""

    start: int  # the node's '<'
    stag_end: int  # just past the start tag (the whole node, for comments and PIs)
    text_end: int  # end of the text before the first child or the end tag
    end: int  # just past the node's last byte
    tail_end: int  # end of the text that follows the node, before its next sibling or its parent's end tag
    self_closing: bool


@dataclass(slots=True)
class _Orig:
    """What a node looked like when loaded, to tell which nodes a patch changed."""

    tag: object
    attrs: tuple
    text: str | None
    tail: str | None
    children: tuple


@dataclass(slots=True)
class _Archive:
    """A .twbx: a zip whose root .twb is the workbook; every other member is copied through unchanged."""

    path: Path
    member: str


class Document:
    """A Tableau XML document (.twb, or the .twb inside a .twbx) that can be edited and saved faithfully."""

    def __init__(self, raw: bytes, *, path: Path | None = None, archive: _Archive | None = None):
        self.raw = raw
        self.path = path
        self._archive = archive
        self.newline = "\r\n" if raw.count(b"\r\n") * 2 > raw.count(b"\n") else "\n"
        parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True, no_network=True)
        try:
            self.root = etree.fromstring(raw, parser)
        except etree.XMLSyntaxError as e:
            raise DocumentError(
                f"Not well-formed XML ({e}). The file may be truncated or hand-edited; open the last backup instead."
            ) from e
        self._spans: dict[etree._Element, _Span] = {}
        self._orig: dict[etree._Element, _Orig] = {}
        self._index()

    # ------------------------------------------------------------------ loading

    @classmethod
    def load(cls, path: str | os.PathLike) -> Document:
        p = Path(path).expanduser()
        if not p.exists():
            raise DocumentError(f"File not found: {p}. Check the path; it must be absolute or ~-relative.")
        if p.suffix.lower() not in WORKBOOK_SUFFIXES:
            raise DocumentError(f"{p.name} is not a workbook. Expected one of: {', '.join(WORKBOOK_SUFFIXES)}.")
        if p.suffix.lower() == ".twbx":
            member = twbx_member(p)
            with zipfile.ZipFile(p) as z:
                return cls(z.read(member), path=p, archive=_Archive(p, member))
        return cls(p.read_bytes(), path=p)

    def _index(self) -> None:
        """Pair every lxml node with its byte span in the original, and snapshot it."""
        events = _scan(self.raw)
        root_events = [e for e in events if e[0] == "e"]
        root_start = root_events[0][1]
        root_endtag = root_events[0][2]
        events = [e for e in events if root_start <= e[1] <= root_endtag]
        nodes = list(self.root.iter())
        if len(nodes) != len(events):
            raise DocumentError(
                f"Couldn't map the XML to byte positions ({len(nodes)} nodes vs {len(events)} events). "
                "This file uses a construct the loader doesn't handle yet; report it with the file."
            )
        raw = self.raw
        for node, (kind, start, endtag) in zip(nodes, events, strict=True):
            if kind == "e":
                m = _START_TAG.match(raw, start)
                if m is None:
                    raise DocumentError(f"Couldn't read the start tag at byte {start}.")
                stag_end = m.end()
                self_closing = raw[stag_end - 2 : stag_end] == b"/>"
                end = stag_end if self_closing else raw.index(b">", endtag) + 1
                text_end = stag_end if self_closing else endtag
            elif kind == "c":
                end = stag_end = text_end = raw.index(b"-->", start) + 3
                self_closing = True
            else:
                end = stag_end = text_end = raw.index(b"?>", start) + 2
                self_closing = True
            self._spans[node] = _Span(start, stag_end, text_end, end, end, self_closing)
        for node in nodes:
            span = self._spans[node]
            children = list(node)
            if children:
                span.text_end = self._spans[children[0]].start
            for i, child in enumerate(children):
                nxt = children[i + 1] if i + 1 < len(children) else None
                self._spans[child].tail_end = self._spans[nxt].start if nxt is not None else _endtag_start(raw, span)
            self._orig[node] = _snapshot(node)

    # ------------------------------------------------------------------ saving

    def is_changed(self) -> bool:
        return not self._content_clean(self.root, {})

    def to_bytes(self) -> bytes:
        """Serialize: original bytes for unchanged nodes, Tableau-style XML for changed ones."""
        root_span = self._spans[self.root]
        if not self.is_changed():
            return self.raw
        out: list[bytes] = []
        self._emit(self.root, out, {})
        result = self.raw[: root_span.start] + b"".join(out) + self.raw[root_span.end :]
        _verify(result, self.root)
        return result

    def save(self, path: str | os.PathLike | None = None) -> Path:
        """Write atomically (temp file, then rename). Defaults to the file it was loaded from."""
        target = Path(path).expanduser() if path is not None else self.path
        if target is None:
            raise DocumentError("No path to save to: this document wasn't loaded from a file.")
        data = self.to_bytes()
        if self._archive is not None and target.suffix.lower() == ".twbx":
            _write_twbx(self._archive, target, data)
        else:
            _atomic_write(target, data)
        return target

    def force_reemit(self, level: str) -> None:
        """Testing hook: make nodes look changed so saving exercises the re-emit paths.

        root: only the root's start tag is re-serialized. structure: every element is rebuilt from its start
        tag, text, children, tails and a generated end tag. full: every start tag is also re-serialized in
        Tableau's style. An unchanged document must still produce identical bytes at every level.
        """
        targets = [self.root] if level == "root" else list(self._orig)
        for node in targets:
            orig = self._orig[node]
            if level == "structure":
                orig.children = (None,)
            else:
                orig.attrs = (None,)

    # ------------------------------------------------------------------ internals

    def _content_clean(self, node, memo: dict) -> bool:
        """True when the node's tag, attributes, text and children (with their tails) are as loaded."""
        if node in memo:
            return memo[node]
        orig = self._orig.get(node)
        ok = (
            orig is not None
            and orig.tag == node.tag
            and orig.text == node.text
            and orig.attrs == tuple(node.attrib.items())
            and orig.children == tuple(node)
            and all(c.tail == self._orig[c].tail and self._content_clean(c, memo) for c in node)
        )
        memo[node] = ok
        return ok

    def _gen(self, text: str) -> bytes:
        return text.replace("\n", self.newline).encode("utf-8")

    def _emit(self, node, out: list[bytes], memo: dict) -> None:
        raw = self.raw
        span = self._spans.get(node)
        if span is not None and self._content_clean(node, memo):
            out.append(raw[span.start : span.end])
            return
        if isinstance(node, etree._Comment):
            out.append(self._gen(f"<!--{node.text or ''}-->"))
            return
        if isinstance(node, etree._ProcessingInstruction):
            out.append(self._gen(f"<?{node.target} {node.text or ''}?>"))
            return
        orig = self._orig.get(node)
        empty = len(node) == 0 and node.text is None
        if span is not None and orig.tag == node.tag and orig.attrs == tuple(node.attrib.items()):
            stag = raw[span.start : span.stag_end]
            head = _SELF_CLOSE_SUFFIX.sub(b"", stag) if span.self_closing else stag[:-1]
            out.append(head + (b" />" if empty else b">"))
        else:
            out.append(self._gen(_start_tag(node) + (" />" if empty else ">")))
        if empty:
            return
        if span is not None and not span.self_closing and node.text == orig.text:
            out.append(raw[span.stag_end : span.text_end])
        else:
            out.append(self._gen(escape_text(node.text or "")))
        for child in node:
            self._emit(child, out, memo)
            cspan = self._spans.get(child)
            if cspan is not None and child.tail == self._orig[child].tail:
                out.append(raw[cspan.end : cspan.tail_end])
            else:
                out.append(self._gen(escape_text(child.tail or "")))
        out.append(self._gen(f"</{_qname(node, node.tag)}>"))


# ---------------------------------------------------------------------- helpers


def twbx_member(path: Path) -> str:
    """The workbook inside a .twbx: the .twb at the archive root."""
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".twb")]
    except zipfile.BadZipFile as e:
        raise DocumentError(f"{path.name} is not a valid .twbx (not a zip archive).") from e
    top = [n for n in names if "/" not in n]
    if not (top or names):
        raise DocumentError(f"{path.name} contains no .twb workbook.")
    return (top or names)[0]


def escape_attr(value: str) -> str:
    """Escape an attribute value the way Tableau does (single-quoted)."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
        .replace("\t", "&#9;")
    )


def escape_text(value: str) -> str:
    """Escape text content the way Tableau does."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _qname(node, name: str) -> str:
    if not name.startswith("{"):
        return name
    uri, local = name[1:].split("}", 1)
    if uri == _XML_NS:
        return f"xml:{local}"
    for prefix, u in node.nsmap.items():
        if u == uri and prefix:
            return f"{prefix}:{local}"
    raise DocumentError(f"No namespace prefix declared for {uri} on <{local}>.")


def _start_tag(node) -> str:
    parts = [f"<{_qname(node, node.tag)}"]
    for key, value in node.attrib.items():
        parts.append(f" {_qname(node, key)}='{escape_attr(value)}'")
    parent = node.getparent()
    inherited = parent.nsmap if parent is not None else {}
    for prefix, uri in node.nsmap.items():
        if inherited.get(prefix) != uri:
            parts.append(f" xmlns:{prefix}='{uri}'" if prefix else f" xmlns='{uri}'")
    return "".join(parts)


def _endtag_start(raw: bytes, span: _Span) -> int:
    """Byte index of '</' for an element that has an end tag."""
    return raw.rindex(b"</", span.start, span.end)


def _snapshot(node) -> _Orig:
    return _Orig(node.tag, tuple(node.attrib.items()), node.text, node.tail, tuple(node))


def _scan(raw: bytes) -> list[list]:
    """Byte offsets of every element, comment and PI, in document order.

    Each event is [kind, start, endtag_start]; kind is 'e', 'c' or 'p'. For elements, endtag_start is where
    expat saw the end (the '</' of the end tag, or the start tag itself when self-closing).
    """
    parser = expat.ParserCreate()
    events: list[list] = []
    stack: list[int] = []

    def start(name, attrs):
        events.append(["e", parser.CurrentByteIndex, -1])
        stack.append(len(events) - 1)

    def end(name):
        events[stack.pop()][2] = parser.CurrentByteIndex

    def comment(data):
        events.append(["c", parser.CurrentByteIndex, parser.CurrentByteIndex])

    def pi(target, data):
        events.append(["p", parser.CurrentByteIndex, parser.CurrentByteIndex])

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CommentHandler = comment
    parser.ProcessingInstructionHandler = pi
    try:
        parser.Parse(raw, True)
    except expat.ExpatError as e:
        raise DocumentError(f"Not well-formed XML ({e}).") from e
    return events


def _verify(data: bytes, tree) -> None:
    """Re-parse the output and require it to match the edited tree exactly."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True, no_network=True)
    back = etree.fromstring(data, parser)
    problem = _diff_trees(tree, back, "")
    if problem:
        raise DocumentError(
            f"Internal error: the saved XML doesn't match the edited workbook at {problem}. Nothing was written."
        )


def _diff_trees(a, b, path: str) -> str | None:
    here = f"{path}/{a.tag if isinstance(a.tag, str) else 'comment'}"
    if a.tag != b.tag or a.text != b.text or tuple(a.attrib.items()) != tuple(b.attrib.items()):
        return here
    if len(a) != len(b):
        return here
    for ca, cb in zip(a, b, strict=True):
        if ca.tail != cb.tail:
            return here
        problem = _diff_trees(ca, cb, here)
        if problem:
            return problem
    return None


def _atomic_write(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if target.exists():
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _write_twbx(archive: _Archive, target: Path, data: bytes) -> None:
    """Rewrite a .twbx with a new root .twb; every other member is copied with its original zip settings."""
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(archive.path) as zin, zipfile.ZipFile(tmp, "w") as zout:
            for info in zin.infolist():
                if info.filename == archive.member:
                    zout.writestr(info, data)
                else:
                    with zin.open(info) as src, zout.open(info, "w") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
