"""Audit a real full-runner result and optionally compare a matched control."""

import argparse
import json
from pathlib import Path

from engine_core import Choice, QUESTIONS, aggregate, scenario_calendar
from simulation import read_jsonl


def prompt_context(prompt):
    # Validation repairs append text after the original context JSON.
    return json.JSONDecoder().raw_decode(prompt.split("CONTEXT_JSON\n", 1)[1])[0]


def audit(path):
    folder = Path(path)
    completion = json.loads((folder / "completion.json").read_text())
    assert completion["complete"]
    manifest = json.loads((folder / "manifest.json").read_text())
    profiles = {p["id"]: p for p in manifest["profiles"]}
    calls = read_jsonl(folder / "calls.jsonl")
    valid = {r["id"]: r for r in calls if r["valid"]}
    weekly = read_jsonl(folder / "weekly.jsonl")
    messages = read_jsonl(folder / "interactions.jsonl")
    assert len(weekly) == len(profiles) * manifest["end_week"]
    assert len({(r["persona"], r["week"]) for r in weekly}) == len(weekly)
    by_phase = {(r["persona"], r["week"], r["phase"]): r for r in valid.values()}
    edges = {(e["source"], e["target"]): e for e in manifest["links"]}
    if manifest.get("model_version") == "calendar-grounded-v3":
        # Check information boundaries in observations and baseline too, not only choices.
        for call in valid.values():
            if call["phase"] not in ("baseline", "observation", "choice"):
                continue
            ctx = prompt_context(call["prompt"])
            assert ctx["scenario_calendar"] == scenario_calendar(call["week"])
            assert all(s["week"] <= call["week"] for s in ctx["verified_sources"])
            assert all(m["recipient"] == call["persona"] for m in ctx["peer_inbox"])
            for message in ctx["peer_inbox"]:
                edge = edges[(message["sender"], call["persona"])]
                assert message["recipient_reach_share"] == edge["recipient_reach_share"]
    delivered = 0
    for message in messages:
        raw = json.loads(valid[message["call"]]["response"])
        field = "outgoing" if message["phase"] == "observation" else "replies"
        assert any(m["recipient"] == message["recipient"] and m["text"] == message["text"] for m in raw[field])
        week = message["week"] + (message["phase"] == "choice")
        phase = "choice" if message["phase"] == "observation" else "observation"
        if week <= manifest["end_week"]:
            target = by_phase[(message["recipient"], week, phase)]
            ctx = prompt_context(target["prompt"])
            assert any(m["id"] == message["id"] and m["text"] == message["text"] for m in ctx["peer_inbox"])
            delivered += 1
    for row in weekly:
        call = valid[row["call"]]
        assert call["persona"] == row["persona"] and call["week"] == row["week"]
        raw = Choice.model_validate_json(call["response"]).model_dump()
        assert row["status"] == raw["status"]
        calculated = aggregate(profiles[row["persona"]], raw)
        assert row["cohort_choices"] == calculated["cohort_choices"]
        ctx = prompt_context(call["prompt"])
        if manifest.get("model_version") in ("calendar-grounded-v2", "calendar-grounded-v3"):
            expected_calendar = scenario_calendar(row["week"])
            if manifest.get("model_version") == "calendar-grounded-v2":
                expected_calendar.pop("already_known_public_change", None)
            assert ctx["scenario_calendar"] == expected_calendar
            released = {e["id"] for e in manifest["events"] if e["week"] <= row["week"]}
            unexpected = {e["id"] for e in manifest["events"]} - released
            assert not unexpected.intersection(s["id"] for s in ctx["verified_sources"])
        assert all(s["week"] <= row["week"] for s in ctx["verified_sources"])
        assert all(m["recipient"] == row["persona"] for m in ctx["peer_inbox"])
    probes = read_jsonl(folder / "probe.jsonl")
    for p in probes:
        call = valid[p["call"]]
        assert call["week"] == (0 if p["when"] == "start" else 11)
        raw = {a["question"]: a["score"] for a in json.loads(call["response"])["answers"]}
        assert raw[p["question"]] == p["score"]
    if manifest["probes"] and manifest["end_week"] == 10:
        assert len(probes) == len(profiles) * 2 * len(QUESTIONS)
    if manifest["type"] == "plan_nosurprises":
        assert manifest["events"] == []
        if manifest["end_week"] >= 9:
            for r in weekly:
                if r["week"] == 9:
                    ctx = prompt_context(valid[r["call"]]["prompt"])
                    assert any(s["id"] == "known-year-end-switch" for s in ctx["verified_sources"])
    baseline = json.loads((folder / "baseline.json").read_text())
    starts = {pid: aggregate(profiles[pid], value)["satisfaction"] for pid, value in baseline.items()}
    result = {"profiles": len(profiles), "weeks": manifest["end_week"], "valid_calls": len(valid),
              "repair_attempts": sum(not r["valid"] for r in calls), "weekly_choices": len(weekly),
              "messages": len(messages), "delivered_messages": delivered, "probe_answers": len(probes),
              "baseline_satisfaction_by_voice": starts,
              "metrics": json.loads((folder / "metrics.json").read_text()),
              "integrity_checks": "passed", "development": manifest["development"]}
    return result, weekly, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--control")
    args = parser.parse_args()
    result, rows, manifest = audit(args.run)
    if args.control:
        control, control_rows, control_manifest = audit(args.control)
        assert manifest["profiles"] == control_manifest["profiles"]
        assert manifest["seed"] == control_manifest["seed"]
        assert manifest["events"] == control_manifest["events"]
        assert manifest["assumptions"] == control_manifest["assumptions"]
        assert result["baseline_satisfaction_by_voice"] == control["baseline_satisfaction_by_voice"]
        result["control"] = control
        result["metric_deltas"] = {f"goal_{i}": result["metrics"][f"goal_{i}"] - control["metrics"][f"goal_{i}"]
            if result["metrics"][f"goal_{i}"] is not None and control["metrics"][f"goal_{i}"] is not None else None
            for i in range(1, 5)}
        result["interpretation"] = "One-seed development comparison of the complete package, including its messages. Not an empirically calibrated action-effect estimate."
    path = Path(args.run) / "audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
