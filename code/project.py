"""One terminal entry point for progress, profiles, interviews, and simulation commands."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def status(output):
    print("QUILLBOOK — live project status")
    print("Canonical population: 24 voices; 42,000 businesses; 3,100 accountants.")
    events = read(ROOT / "data/official_events.json", {"events": []})
    releases = events if isinstance(events, list) else events.get("events", [])
    supplied = any((ROOT / path).exists() for path in ("decisions/locked_plan.json", "data/locked_plan.json"))
    print(f"Official event inputs: {len(releases)}. Dashboard lock download: {'present; verify against dashboard' if supplied else 'not supplied'}.")
    print("Five-run export and terminal interviews implemented. See control/START_HERE.md.")
    print("RUN                                      PROGRESS   CALLS  STATE")
    paths = sorted(p for p in Path(output).rglob("manifest.json") if "archive" not in p.parts)
    if not paths:
        print("No complete-runner outputs yet.")
    for path in paths:
        folder = path.parent
        manifest = read(path)
        calls = folder / "calls.jsonl"
        count = sum(1 for _ in calls.open()) if calls.exists() else 0
        weekly = folder / "weekly.jsonl"
        rows = sum(1 for _ in weekly.open()) if weekly.exists() else 0
        voices, weeks = len(manifest["profiles"]), manifest["end_week"]
        complete = read(folder / "completion.json", {}).get("complete")
        state = "COMPLETE development" if complete else "RUNNING / resumable"
        if (folder / "REJECTED.md").exists():
            state = "REJECTED: old support bug"
        elif (folder / "failures.json").exists() and not complete:
            state = "FAILED: resume identical command"
        name = str(folder.relative_to(ROOT)) if folder.is_relative_to(ROOT) else str(folder)
        print(f"{name:40} {rows:3}/{voices * weeks:<3} {count:5}  {state}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    progress = subs.add_parser("status")
    progress.add_argument("--output", default=str(ROOT / "output"))
    progress.add_argument("--watch", action="store_true")
    subs.add_parser("personas")
    console = subs.add_parser("ui")
    console.add_argument("--port", type=int, default=8765)
    chat = subs.add_parser("chat")
    chat.add_argument("--run", required=True)
    chat.add_argument("--persona", required=True)
    chat.add_argument("question", nargs="?")
    for name in ("run", "suite", "rehearse", "validate", "compare", "audit"):
        subs.add_parser(name, add_help=False)
    args, rest = parser.parse_known_args()
    if args.command == "status":
        while True:
            status(args.output)
            if not args.watch:
                return
            print("\nRefreshing in 5 seconds; Ctrl-C stops watching.\n", flush=True)
            time.sleep(5)
    elif args.command == "ui":
        raise SystemExit(subprocess.call([sys.executable, str(ROOT / "dashboard.py"), "--port", str(args.port)]))
    elif args.command == "personas":
        for line in (ROOT / "data/personas.jsonl").read_text().splitlines():
            p = json.loads(line)
            role = "businesses" if p["represented_businesses"] else "accountants"
            weight = p["represented_businesses"] or p["represented_accountants"]
            print(f"{p['id']} | {p.get('name', '')} | {p['group']} | {p.get('sector', 'mixed practice')} | represents {weight:,} {role}")
            print("    " + p["backstory"])
    elif args.command == "chat":
        command = [sys.executable, str(ROOT / "interview.py"), "--run", args.run, "--persona", args.persona]
        if args.question:
            raise SystemExit(subprocess.call(command + [args.question]))
        print(f"Interviewing {args.persona} from {args.run}. Type /quit to exit.")
        while True:
            question = input("You: ").strip()
            if question.lower() in ("/quit", "quit", "exit"):
                return
            if question:
                subprocess.call(command + [question])
    else:
        module, operation = {"run": ("engine.py", "run"), "suite": ("engine.py", "suite"),
            "rehearse": ("engine.py", "rehearse"),
            "validate": ("engine.py", "validate"), "compare": ("experiments.py", "run"),
            "audit": ("audit_engine.py", None)}[args.command]
        raise SystemExit(subprocess.call([sys.executable, str(ROOT / module)] + ([operation] if operation else []) + rest))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
