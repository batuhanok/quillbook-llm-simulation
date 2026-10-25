"""Import one explicitly selected dashboard release with an explicit scenario week."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from engine import load_inputs, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", help="Original dashboard announcements JSON")
    parser.add_argument("--id", required=True, help="Exact announcement ID to import")
    parser.add_argument("--week", required=True, type=int, choices=range(1, 11))
    parser.add_argument("--audience", help="Comma-separated IDs; omit for all personas")
    parser.add_argument("--affected", help="Comma-separated IDs with direct incident experience; explicit modeling interpretation")
    parser.add_argument("--output", default="data/official_events.json")
    args = parser.parse_args()
    source = Path(args.export)
    raw = json.loads(source.read_text())
    announcements = raw if isinstance(raw, list) else raw["announcements"]
    item = next((a for a in announcements if a["id"] == args.id), None)
    if not item:
        raise ValueError("Announcement ID not found in export")
    if item.get("company_id") not in (None, "quillbook"):
        raise ValueError("Announcement belongs to another company")
    if item.get("title", "").strip().lower() == "spot prize" or item.get("body", "").strip().lower() == "test":
        raise ValueError("This is an administrative/test announcement, not a customer crisis")
    text = item.get("body", item.get("text", ""))
    if not text.strip():
        raise ValueError("Announcement has no body text")
    profiles, *_ = load_inputs()
    ids = {p["id"] for p in profiles}
    audience = args.audience.split(",") if args.audience else []
    affected = args.affected.split(",") if args.affected else []
    if not set(audience + affected) <= ids:
        raise ValueError("Unknown exposure/persona ID")
    if audience and not set(affected) <= set(audience):
        raise ValueError("Directly affected personas must also receive the event")
    event = {"id": item["id"], "week": args.week, "text": text, "title": item.get("title"),
             "audience_ids": audience, "affected": affected, "hypothetical": False,
             "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
             "original_announcement": item,
             "exposure_note": "Release week and audience/affected IDs were explicitly assigned by the operator, not inferred from vague crisis text."}
    path = Path(args.output)
    document = json.loads(path.read_text()) if path.exists() else {"events": []}
    if any(e["id"] == args.id for e in document["events"]):
        raise ValueError("ID already imported; preserve original and use a new ID for an official update")
    document["events"].append(event)
    document["status"] = "Official releases imported; verify completeness against dashboard."
    document["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(path, document)
    print(f"Imported {args.id} verbatim at week {args.week}; {len(document['events'])} releases saved.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from None
