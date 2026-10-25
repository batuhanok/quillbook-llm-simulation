"""Build a checked ZIP from completed real final runs and the exact locked plan.

Never uploads. Development or test-double runs cannot be packaged.
"""

import argparse
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile

from actions import validate_plan

ROOT = Path(__file__).resolve().parent
RUNS = ("plan_1", "plan_2", "nodecision_1", "nodecision_2", "plan_nosurprises")
SOURCES = ("engine.py", "engine_core.py", "actions.py", "api_client.py", "simulation.py",
           "build_profiles.py", "requirements.txt", "README.md", "project.py", "interview.py",
           "experiments.py", "audit_engine.py", "events.py", "results_report.py", "submission.py",
           "dashboard.py", "dashboard.html")
RUN_FILES = {"run.json", "personas.jsonl", "calls.jsonl", "weekly.jsonl", "metrics.json", "probe.jsonl",
             "manifest.json", "baseline.json", "interactions.jsonl", "state.json", "support_daily.jsonl",
             "support_reference.json", "completion.json", "audit.json"}


def official_check(path):
    spec = importlib.util.spec_from_file_location("official_checker", ROOT / "yeni-case-5-sirket/check.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    report, _ = checker.check(path)
    if report.failed:
        raise ValueError("Official checker failed:\n" + "\n".join(report.lines))
    return report


def prepare(suite, locked_plan):
    suite = Path(suite)
    original = json.loads(Path(locked_plan).read_text())
    decisions = original.get("run_decisions", original.get("decisions", []))
    summary = {}
    for name in RUNS:
        folder = suite / "runs" / name
        completion = json.loads((folder / "completion.json").read_text())
        manifest = json.loads((folder / "manifest.json").read_text())
        run = json.loads((folder / "run.json").read_text())
        metrics = json.loads((folder / "metrics.json").read_text())
        if completion.get("development") or not completion.get("complete") or completion["weeks"] != 10 or completion["profiles"] < 24:
            raise ValueError("Only complete, non-development final runs may be packaged")
        if (folder / "REJECTED.md").exists():
            raise ValueError("Rejected simulation evidence cannot be packaged")
        expected_seed = 43 if name in ("plan_2", "nodecision_2") else 42
        if run["seed"] != expected_seed or manifest["seed"] != expected_seed:
            raise ValueError("Final run uses an unexpected comparison seed")
        if any(not isinstance(metrics.get(f"goal_{i}"), (float, int)) or not math.isfinite(metrics[f"goal_{i}"]) for i in range(1, 5)):
            raise ValueError("A board metric is missing or non-finite")
        expected = [] if name.startswith("nodecision") else decisions
        if run["decisions"] != expected:
            raise ValueError("Run decisions differ from the locked dashboard download")
        validate_plan(expected, manifest["profiles"], manifest["selectors"], require_two=not name.startswith("nodecision"))
        if any(e.get("hypothetical") for e in manifest["events"]):
            raise ValueError("Hypothetical diagnostics cannot appear in final runs")
        if "OFFLINE TEST DOUBLE" in (folder / "calls.jsonl").read_text():
            raise ValueError("Test-double responses cannot be submitted")
        summary[name] = metrics
    first = json.loads((suite / "runs/plan_1/manifest.json").read_text())
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected
           for name, expected in first["sources"].items()):
        raise ValueError("Runtime code changed since the final runs; rerun before packaging")
    for name in ("plan_2", "nodecision_1", "nodecision_2", "plan_nosurprises"):
        other = json.loads((suite / "runs" / name / "manifest.json").read_text())
        if first.get("model_version") != other.get("model_version"):
            raise ValueError("Final runs use different simulation versions")
        if first.get("conversation_version", "original") != other.get("conversation_version", "original"):
            raise ValueError("Final runs use different conversation models")
        if first["profiles"] != other["profiles"] or first["assumptions"] != other["assumptions"] or first["links"] != other["links"] or first["model"] != other["model"] or first["sources"] != other["sources"]:
            raise ValueError("Final comparison inputs differ")
        if other["events"] != ([] if name == "plan_nosurprises" else first["events"]):
            raise ValueError("Final surprise-event ledger differs from the required comparison")
    from audit_engine import audit
    for name in RUNS:
        audit(suite / "runs" / name)
    code = suite / "code"
    code.mkdir(exist_ok=True)
    for name in SOURCES:
        shutil.copyfile(ROOT / name, code / name)
    (code / "data").mkdir(exist_ok=True)
    (code / "data/personas.jsonl").write_text((suite / "runs/plan_1/personas.jsonl").read_text())
    (code / "data/network.json").write_text(json.dumps(first["links"], indent=2))
    (code / "data/official_events.json").write_text(json.dumps({"events": first["events"]}, indent=2))
    shutil.copyfile(locked_plan, code / "data/locked_plan.json")
    shutil.copyfile(ROOT / "14-quillbook.md", code / "14-quillbook.md")
    (code / "yeni-case-5-sirket").mkdir(exist_ok=True)
    for name in ("02-challenge.md", "03-audience-attributes.md", "check.py"):
        shutil.copyfile(ROOT / "yeni-case-5-sirket" / name, code / "yeni-case-5-sirket" / name)
    if not (suite / "TEAM_DOC.md").exists():
        shutil.copyfile(ROOT / "TEAM_DOC.md", suite / "TEAM_DOC.md")
    if not (suite / "CLIENT_MEMO.md").exists():
        lines = ["# Quillbook board memo", "", "Simulation estimates, not measured customer outcomes. Review before presentation.", "",
                 "| Run | Renewal % | Maximum four-week churn % | Accountant satisfaction change | Support hours |",
                 "|---|---:|---:|---:|---:|"]
        for name, m in summary.items():
            lines.append(f"| {name} | {m['goal_1']:.1f} | {m['goal_2']:.1f} | {m['goal_3']:.1f} | {m['goal_4']:.1f} |")
        lines += ["", f"Combined decision cost: ${summary['plan_1']['cost_usd']:,.0f}.", "",
                  "Decisions and exact messages are in the attached run files. Compare the paired seeds and the no-surprise run; do not treat two seeds as statistical confidence.", "",
                  "Limitations: fictional cohort representation; synthetic behavior; uncalibrated support/reliability assumptions; four-week churn is a monthly proxy. Monitor actual renewal completion, partner sentiment, support queues, and incident severity before acting on forecasts."]
        (suite / "CLIENT_MEMO.md").write_text("\n".join(lines) + "\n")
    official_check(suite)
    return suite


def package(suite, locked_plan, output):
    suite = prepare(suite, locked_plan)
    output = Path(output)
    if not re.fullmatch(r"team-\d{2}_submission\.zip", output.name):
        raise ValueError("Use team-NN_submission.zip")
    allowed = [suite / "CLIENT_MEMO.md", suite / "TEAM_DOC.md"]
    allowed += [p for p in (suite / "code").rglob("*") if p.is_file()]
    allowed += [suite / "runs" / name / filename for name in RUNS for filename in sorted(RUN_FILES)
                if (suite / "runs" / name / filename).is_file()]
    for path in allowed:
        if path.name.startswith(".env") or any(part in (".venv", "__pycache__", ".git") for part in path.parts):
            raise ValueError("Secret/environment/cache file in staging; remove it before packaging")
        if re.search(rb"AQ\.[A-Za-z0-9_-]{40}|AIza[A-Za-z0-9_-]{30}", path.read_bytes()):
            raise ValueError("Possible credential in staging; archive was not created")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in allowed:
            archive.write(path, path.relative_to(suite))
    if temporary.stat().st_size > 100_000_000:
        raise ValueError("ZIP exceeds dashboard's 100 MB limit")
    official_check(temporary)
    temporary.replace(output)
    print(f"Checked archive ready: {output.resolve()}; not uploaded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--locked-plan", required=True)
    parser.add_argument("--output", default="team-08_submission.zip")
    args = parser.parse_args()
    package(args.suite, args.locked_plan, args.output)
