"""Build OPML 2.0 export payload for subscribed feeds."""

from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from db import list_feeds


def build_opml_bytes() -> bytes:
    opml = ET.Element("opml", {"version": "2.0"})
    head = ET.SubElement(opml, "head")
    title_el = ET.SubElement(head, "title")
    title_el.text = "infoFeeder sources"
    dc = ET.SubElement(head, "dateCreated")
    dc.text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S UTC")
    body = ET.SubElement(opml, "body")
    for row in list_feeds():
        url = (row["url"] or "").strip()
        if not url:
            continue
        name = (row["name"] or "").strip() or "Untitled"
        outline_attrs = {
            "text": name,
            "title": name,
            "type": "rss",
            "xmlUrl": url,
        }
        base = (row["base_url"] or "").strip()
        if base:
            outline_attrs["htmlUrl"] = base
        cat = (row["category"] or "").strip()
        if cat:
            outline_attrs["category"] = cat
        ET.SubElement(body, "outline", outline_attrs)
    return ET.tostring(opml, encoding="utf-8", xml_declaration=True)
