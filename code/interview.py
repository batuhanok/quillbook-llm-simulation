"""Interview a saved persona without modifying simulation evidence."""

import argparse
import json
from pathlib import Path

from google.genai import types

from api_client import create_client
from engine_core import SPEECH_RULES, visible_sources
from simulation import digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--persona", required=True)
    parser.add_argument("question")
    args = parser.parse_args()
    folder = Path(args.run)
    if not (folder / "completion.json").exists() or (folder / "REJECTED.md").exists():
        raise SystemExit("Choose a completed run that has not been rejected for a modeling defect.")
    manifest = json.loads((folder / "manifest.json").read_text())
    state = json.loads((folder / "state.json").read_text())
    persona = next((p for p in manifest["profiles"] if p["id"] == args.persona), None)
    if not persona:
        raise SystemExit("Unknown persona ID")
    week = manifest["end_week"]
    sources = visible_sources(persona, week, manifest["events"], manifest["decisions"], manifest["selectors"])
    weekly = [json.loads(line) for line in (folder / "weekly.jsonl").read_text().splitlines()]
    exchanges = [json.loads(line) for line in (folder / "interactions.jsonl").read_text().splitlines()]
    received = [m for m in exchanges if m["recipient"] == args.persona and
                m["week"] + (m["phase"] == "choice") <= week]
    history_file = folder / "interview_calls.jsonl"
    prior = [json.loads(line) for line in history_file.read_text().splitlines()] if history_file.exists() else []
    prompt = SPEECH_RULES + "Answer the board's question using your saved history. Do not invent earlier experiences.\n" + json.dumps({
        "persona": persona, "saved_beliefs_and_state": state[args.persona], "verified_sources": sources,
        "own_weekly_history": [r for r in weekly if r["persona"] == args.persona],
        "received_messages": received,
        "prior_board_interview": [{"question": r.get("question"), "answer": r["response"]}
                                  for r in prior if r["persona"] == args.persona][-6:],
        "question": args.question}, ensure_ascii=False)
    try:
        with create_client() as client:
            response = client.models.generate_content(model=manifest["model"], contents=prompt,
                config=types.GenerateContentConfig(seed=manifest["seed"], temperature=1.0))
        if not response.text:
            raise ValueError("Empty interview response")
    except Exception as error:
        raise SystemExit(f"Interview failed ({type(error).__name__}); no answer was fabricated.") from None
    with (folder / "interview_calls.jsonl").open("a") as out:
        out.write(json.dumps({"id": digest({"prompt": prompt, "model": manifest["model"]}),
            "persona": args.persona, "question": args.question, "prompt": prompt, "response": response.text,
            "model": manifest["model"], "seed": manifest["seed"], "purpose": "board_interview_not_submission_run"}) + "\n")
    print(response.text)
