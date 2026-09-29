"""Phase 1 spike: which version format should generated workbooks use, and are manifest gates real?

Writes five small workbooks. Every element comes from XML Tableau wrote: the empty sheet, dashboard and window
shapes from Desktop's "new workbook" / "new dashboard" diffs in Tableau's plugin corpus, the navigation button
from a Desktop-saved Tableau Public workbook (build 2026.2).

    a  18.1, Desktop-style manifest                          expect: loads (control)
    b  26.2, <ManifestByVersion/> only                       question: does Desktop 2026.2 accept it?
    c  18.1, nav button + BasicButtonObject entries          expect: loads (gate satisfied)
    d  18.1, nav button, BasicButtonObject entries removed   expect: fails if manifest gates are real
    e  26.2, <ManifestByVersion/>, nav button                question: does ManifestByVersion cover gates?

Open each in Tableau Desktop 2026.2 and note: loads or error (with the code), then File > Save and see what
Desktop rewrote (version attribute, manifest).

Usage: uv run python spikes/version_format/make_spike.py [out_dir]
"""

import sys
from pathlib import Path

HOME_WINDOW = "{2B7E6A51-4C3D-4E8F-9A10-B2C3D4E5F601}"

BUTTON_ZONE = """
          <zone fixed-size='45' h='3888' id='55' is-fixed='true' type-v2='dashboard-object' w='13749' x='81084' y='10778'>
            <button action='tabdoc:goto-sheet window-id=&quot;{DETAILS_WINDOW}&quot;' button-type='text'>
              <button-visual-state>
                <caption>Go to Details</caption>
                <button-caption-font-style fontcolor='#ffffff' fontname='Arial' />
                <format attr='background-color' value='#e15759' />
              </button-visual-state>
            </button>
            <zone-style>
              <format attr='border-color' value='#000000' />
              <format attr='border-style' value='none' />
              <format attr='border-width' value='0' />
              <format attr='margin' value='0' />
            </zone-style>
          </zone>"""

DETAILS_WINDOW = "{7C1D2E3F-4A5B-4C6D-8E9F-0A1B2C3D4E5F}"

TEMPLATE = """<?xml version='1.0' encoding='utf-8' ?>

<!-- build 20262.26.0819.2015                               -->
<workbook original-version='{version}' source-build='2026.2.0 (20262.26.0819.2015)' source-platform='mac' \
version='{version}' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
{manifest}
  </document-format-change-manifest>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources />
  <worksheets>
    <worksheet name='Sheet 1'>
      <table>
        <view>
          <datasources />
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Automatic' />
          </pane>
        </panes>
        <rows />
        <cols />
      </table>
      <simple-id uuid='{{D4DCB499-07EB-4111-AD6C-D69EA504B926}}' />
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard enable-sort-zone-taborder='true' name='Home'>
      <style />
      <size maxheight='800' maxwidth='1000' minheight='800' minwidth='1000' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>{button}
        </zone>
      </zones>
      <simple-id uuid='{{F2A60186-1188-4243-83A3-5A63B9051544}}' />
    </dashboard>
    <dashboard enable-sort-zone-taborder='true' name='Details'>
      <style />
      <size maxheight='800' maxwidth='1000' minheight='800' minwidth='1000' />
      <zones />
      <simple-id uuid='{{0E1F2A3B-4C5D-4E6F-8A9B-C0D1E2F3A4B5}}' />
    </dashboard>
  </dashboards>
  <windows source-height='30'>
    <window class='worksheet' name='Sheet 1'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='31'>
            <card type='columns' />
          </strip>
          <strip size='31'>
            <card type='rows' />
          </strip>
          <strip size='31'>
            <card type='title' />
          </strip>
        </edge>
      </cards>
      <simple-id uuid='{{8A46BC0A-3306-42BA-A979-4835049125D0}}' />
    </window>
    <window class='dashboard' maximized='true' name='Home'>
      <viewpoints />
      <active id='-1' />
      <simple-id uuid='{home_window}' />
    </window>
    <window class='dashboard' name='Details'>
      <viewpoints />
      <active id='-1' />
      <simple-id uuid='{details_window}' />
    </window>
  </windows>
</workbook>
"""

DESKTOP_MANIFEST = [
    "AccessibleZoneTabOrder",
    "AnimationOnByDefault",
    "MarkAnimation",
    "SheetIdentifierTracking",
    "WindowsPersistSimpleIdentifiers",
]
BUTTON_ENTRIES = ["BasicButtonObject", "BasicButtonObjectTextSupport"]

VARIANTS = {
    "a-18.1-desktop-manifest": ("18.1", DESKTOP_MANIFEST, False),
    "b-26.2-manifest-by-version": ("26.2", ["ManifestByVersion"], False),
    "c-18.1-button-with-gate": ("18.1", sorted(DESKTOP_MANIFEST + BUTTON_ENTRIES), True),
    "d-18.1-button-gate-removed": ("18.1", DESKTOP_MANIFEST, True),
    "e-26.2-manifest-by-version-button": ("26.2", ["ManifestByVersion"], True),
}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out"
    out.mkdir(parents=True, exist_ok=True)
    for name, (version, manifest, button) in VARIANTS.items():
        xml = TEMPLATE.format(
            version=version,
            manifest="\n".join(f"    <{m} />" for m in manifest),
            button=BUTTON_ZONE.replace("{DETAILS_WINDOW}", DETAILS_WINDOW) if button else "",
            home_window=HOME_WINDOW,
            details_window=DETAILS_WINDOW,
        )
        (out / f"{name}.twb").write_text(xml, encoding="utf-8")
        print(out / f"{name}.twb")


if __name__ == "__main__":
    main()
