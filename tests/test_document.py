import difflib
import zipfile

import pytest
from lxml import etree

from tableau_authoring_mcp.twb.document import Document, DocumentError


def changed_lines(before: bytes, after: bytes) -> list[str]:
    diff = difflib.unified_diff(before.decode().splitlines(), after.decode().splitlines(), lineterm="", n=0)
    return [line for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---"))]


@pytest.mark.parametrize("level", [None, "root", "structure", "full"])
def test_unchanged_document_round_trips_byte_for_byte(minimal, level):
    doc = Document.load(minimal)
    if level:
        doc.force_reemit(level)
    assert doc.to_bytes() == minimal.read_bytes()


def test_crlf_file_round_trips_and_new_content_uses_crlf(tmp_path, minimal):
    crlf = tmp_path / "crlf.twb"
    crlf.write_bytes(minimal.read_bytes().replace(b"\n", b"\r\n"))
    doc = Document.load(crlf)
    doc.force_reemit("full")
    assert doc.to_bytes() == crlf.read_bytes()

    zones = doc.root.find(".//zone[@id='1']")
    new = etree.SubElement(zones, "zone", h="10", id="3", w="10", x="0", y="0")
    new.tail = zones[-2].tail
    zones[-2].tail = "\n          "
    out = doc.to_bytes()
    assert b"<zone h='10' id='3' w='10' x='0' y='0' />\r\n" in out
    assert b"\n" not in out.replace(b"\r\n", b"")


def test_attribute_change_touches_only_that_line(minimal):
    doc = Document.load(minimal)
    doc.root.find(".//worksheet").set("name", "Sales by Area")
    changes = changed_lines(minimal.read_bytes(), doc.to_bytes())
    assert changes == ["-    <worksheet name='Sales by Region'>", "+    <worksheet name='Sales by Area'>"]


def test_new_attribute_values_are_escaped_like_tableau(minimal):
    doc = Document.load(minimal)
    col = doc.root.find(".//column[@name='[REGION]']")
    col.set("caption", 'Region\'s "best" <5> & more\nline')
    out = doc.to_bytes()
    assert b"caption='Region&apos;s &quot;best&quot; &lt;5&gt; &amp; more&#10;line'" in out
    assert len(changed_lines(minimal.read_bytes(), out)) == 2


def test_added_element_is_serialized_in_tableau_style(minimal):
    doc = Document.load(minimal)
    manifest = doc.root.find("document-format-change-manifest")
    last = manifest[-1]
    new = etree.SubElement(manifest, "NavigationAction")
    new.tail, last.tail = last.tail, manifest[0].tail
    changes = changed_lines(minimal.read_bytes(), doc.to_bytes())
    assert changes == ["+    <NavigationAction />"]


def test_removed_element_disappears_cleanly(minimal):
    doc = Document.load(minimal)
    prefs = doc.root.find("preferences")
    prefs.getprevious().tail = prefs.tail
    doc.root.remove(prefs)
    changes = changed_lines(minimal.read_bytes(), doc.to_bytes())
    assert changes == [
        "-  <preferences>",
        "-    <preference name='ui.encoding.shelf.height' value='24' />",
        "-  </preferences>",
    ]


def test_cdata_and_comments_survive_edits_elsewhere(minimal):
    doc = Document.load(minimal)
    doc.root.find(".//dashboard").set("name", "Summary")
    out = doc.to_bytes()
    assert b"&quot;<![CDATA[<raw & unescaped>]]>&quot;" in out
    assert b"<!-- a comment inside the zone tree -->" in out


def test_self_closing_element_that_gains_a_child_gets_an_end_tag(minimal):
    doc = Document.load(minimal)
    style = doc.root.find(".//dashboard/style")
    rule = etree.SubElement(style, "style-rule", element="table")
    rule.tail = "\n      "
    style.text = "\n        "
    out = doc.to_bytes().decode()
    assert "<style>\n        <style-rule element='table' />\n      </style>" in out


def test_text_change_is_escaped(minimal):
    doc = Document.load(minimal)
    doc.root.find(".//rows").text = "[a] < [b] & 'c'"
    assert b"<rows>[a] &lt; [b] &amp; &apos;c&apos;</rows>" in doc.to_bytes()


def test_save_writes_atomically_and_reloads_identically(minimal):
    doc = Document.load(minimal)
    doc.root.find(".//worksheet").set("name", "Renamed")
    doc.save()
    again = Document.load(minimal)
    assert again.root.find(".//worksheet").get("name") == "Renamed"
    assert again.to_bytes() == minimal.read_bytes()
    assert not list(minimal.parent.glob(".minimal.twb.*.tmp"))


def test_twbx_round_trip_keeps_other_members(tmp_path, minimal):
    twbx = tmp_path / "packaged.twbx"
    with zipfile.ZipFile(twbx, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(minimal, "packaged.twb")
        z.writestr("Data/Extracts/sample.hyper", b"\x00binary extract\xff")
    doc = Document.load(twbx)
    assert doc.to_bytes() == minimal.read_bytes()
    doc.root.find(".//worksheet").set("name", "Renamed")
    doc.save()
    with zipfile.ZipFile(twbx) as z:
        assert z.read("Data/Extracts/sample.hyper") == b"\x00binary extract\xff"
        assert b"name='Renamed'" in z.read("packaged.twb")


def test_malformed_xml_gives_an_actionable_error(tmp_path):
    bad = tmp_path / "broken.twb"
    bad.write_text("<?xml version='1.0' ?>\n<workbook><worksheets></workbook>")
    with pytest.raises(DocumentError, match="Not well-formed XML"):
        Document.load(bad)


def test_wrong_file_type_is_refused(tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("hi")
    with pytest.raises(DocumentError, match="not a workbook"):
        Document.load(other)
