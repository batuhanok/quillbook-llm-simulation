"""Complete Quillbook runner. API-generated choices; explicit world assumptions.

Run `python engine.py --help`. Existing pilot outputs are left untouched.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import tempfile
import time
from threading import Lock

from google.genai import types

from actions import ASSUMPTIONS, MENU, action_cost, support_week, validate_plan
from api_client import DEFAULT_MODEL, create_client
from build_profiles import validate as validate_population
from engine_core import (Choice, Observation, Probe, QUESTIONS, MODEL_VERSION, scenario_calendar, aggregate,
                         profiles_with_segments, prompt_for, validate_choice,
                         validate_messages, visible_sources)
from simulation import digest, encode, read_jsonl

ROOT = Path(__file__).resolve().parent
RUNS = {"plan_1": ("plan", 42, True), "plan_2": ("plan", 43, False),
        "nodecision_1": ("nodecision", 42, True), "nodecision_2": ("nodecision", 43, False),
        "plan_nosurprises": ("plan_nosurprises", 42, False)}
_CACHE_LOCKS = {}
_CACHE_GUARD = Lock()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_rows(path, rows):
    path.write_text("".join(encode(row) + "\n" for row in rows))


class RequestFailure(Exception):
    def __init__(self, records, error_type):
        self.records, self.error_type = records, error_type


class Gateway:
    def __init__(self, client, model, seed, cache_folder):
        self.client, self.model, self.seed = client, model, seed
        self.cache = Path(cache_folder)
        self.cache.mkdir(parents=True, exist_ok=True)

    def ask(self, persona, week, phase, prompt, schema, validator):
        key = digest({"prompt": prompt, "schema": schema.model_json_schema(), "model": self.model,
                      "persona": persona, "week": week, "phase": phase,
                      "seed": self.seed, "temperature": 1.0, "engine_contract": 4})
        # Parallel matched branches must share one actual baseline response,
        # including on a cold cache; a seed alone does not ensure determinism.
        with _CACHE_GUARD:
            lock = _CACHE_LOCKS.setdefault(str(self.cache / key), Lock())
        with lock:
            return self._ask_locked(persona, week, phase, prompt, schema, validator, key)

    def _ask_locked(self, persona, week, phase, prompt, schema, validator, key):
        cached = self.cache / (key + ".json")
        if cached.exists():
            records = json.loads(cached.read_text())
            value = schema.model_validate_json(records[-1]["response"]).model_dump()
            validator(value)
            return value, records[-1]["id"], records
        records, current = [], prompt
        for attempt in range(3):
            started = time.monotonic()
            try:
                response = self.client.models.generate_content(model=self.model, contents=current,
                    config=types.GenerateContentConfig(seed=self.seed, temperature=1.0,
                        response_mime_type="application/json", response_schema=schema))
            except Exception as error:
                raise RequestFailure(records, type(error).__name__) from None
            raw = response.text or ""
            row = {"id": key + (f"-repair-{attempt}" if attempt else ""), "persona": persona,
                   "week": week, "phase": phase, "prompt": current, "response": raw,
                   "model": self.model, "seed": self.seed, "temperature": 1.0,
                   "seconds": round(time.monotonic() - started, 3), "valid": False}
            records.append(row)
            try:
                value = schema.model_validate_json(raw).model_dump()
                validator(value)
            except ValueError as error:
                row["validation_issue"] = str(error)[:350]
                current = prompt + "\nRepair the following contract error: " + str(error)[:350] + "\nPrevious answer:\n" + raw
                continue
            row["valid"] = True
            with tempfile.NamedTemporaryFile(mode="w", dir=self.cache, delete=False) as handle:
                json.dump(records, handle)
                temporary = Path(handle.name)
            temporary.replace(cached)
            return value, row["id"], records
        raise RequestFailure(records, "StructuredResponseValidation")


def load_inputs(events_path=None, plan_path=None):
    profiles = profiles_with_segments(read_jsonl(ROOT / "data/personas.jsonl"))
    links = json.loads((ROOT / "data/network.json").read_text())
    validate_population(profiles, links)
    document = json.loads(Path(events_path).read_text()) if events_path else {"events": []}
    events = document if isinstance(document, list) else document["events"]
    seen = set()
    for event in events:
        if event["id"] in seen or type(event.get("week")) is not int or not 1 <= event["week"] <= 10 or not event.get("text"):
            raise ValueError("Events need unique IDs, exact text, and release weeks 1–10")
        seen.add(event["id"])
        if event.get("audience_ids") and not set(event["audience_ids"]) <= {p["id"] for p in profiles}:
            raise ValueError("Unknown event audience ID")
        if isinstance(event.get("affected"), list) and not set(event["affected"]) <= {p["id"] for p in profiles}:
            raise ValueError("Unknown directly affected persona ID")
    plan = json.loads(Path(plan_path).read_text()) if plan_path else {"run_decisions": [], "selectors": {}}
    decisions = plan.get("run_decisions", plan.get("decisions", []))
    selectors = plan.get("selectors", {})
    validate_plan(decisions, profiles, selectors)
    return profiles, links, events, decisions, selectors


def metrics(profiles, weekly, baseline, support_days, decisions, end_week):
    by_id = {p["id"]: p for p in profiles}
    businesses = [p for p in profiles if p["represented_businesses"]]
    accountants = [p for p in profiles if p["represented_accountants"]]
    total = sum(p["represented_businesses"] for p in businesses)
    accountant_count = sum(p["represented_accountants"] for p in accountants)
    cumulative = {0: 0.0}
    for week in range(1, end_week + 1):
        cumulative[week] = sum(by_id[r["persona"]]["represented_businesses"] *
            next(x["fraction"] for x in r["cohort_choices"] if x["status"] == "moved to a rival")
            for r in weekly if r["week"] == week and by_id[r["persona"]]["represented_businesses"])
    churn_windows = []
    for week in range(4, end_week + 1):
        opening = total - cumulative[week - 4]
        churn_windows.append({"end_week": week, "pct": 100 * (cumulative[week] - cumulative[week - 4]) / max(opening, 1e-9)})
    due = sum(sum(p.get("renewal_counts", {}).values()) for p in businesses)
    renewed = sum(by_id[r["persona"]].get("renewal_counts", {}).get(str(r["week"]), 0) * r["renewal_fraction"]
                  for r in weekly if r["week"] in (9, 10))
    first_sat = sum(p["represented_accountants"] * aggregate(p, baseline[p["id"]])["satisfaction"] for p in accountants) / accountant_count
    final_sat = sum(by_id[r["persona"]]["represented_accountants"] * r["satisfaction"] for r in weekly if r["week"] == end_week) / accountant_count
    response = max((d["mean_hours"] for d in support_days if not d["excluded_from_goal"]), default=0.0)
    return {"goal_1": 100 * renewed / due if end_week == 10 else None,
            "goal_2": max((x["pct"] for x in churn_windows), default=None),
            "goal_3": final_sat - first_sat, "goal_4": response,
            "units": {"goal_1": "% of original annual plans due in weeks 9–10 renewed",
                      "goal_2": "maximum rolling four-week departure percentage; monthly proxy, not calendar-month measurement",
                      "goal_3": "partner-accountant satisfaction change on model 1–5 scale, end minus baseline",
                      "goal_4": "maximum daily population-weighted mean support response hours, excluding January 4–5"},
            "renewed_plans": renewed, "due_plans": due, "churn_windows": churn_windows,
            "accountant_satisfaction_baseline": first_sat, "accountant_satisfaction_final": final_sat,
            "cost_usd": sum(action_cost(a) for d in decisions for a in d["actions"]),
            "warnings": ["Behavior and intervention effects are synthetic and uncalibrated.",
                         "Support is a baseline-anchored workload proxy, not a calibrated queue; hotline prioritization can harm other customers.",
                         "Partial development runs do not have all board metrics; do not submit them."]}


def execute_run(folder, profiles, links, events, decisions, selectors, *, kind="nodecision", seed=42,
                model=DEFAULT_MODEL, end_week=10, probes=True, concurrency=24,
                development=True, client=None, cache_folder=None, assumptions=None,
                interactions_off=False, reasoned_messages=True):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    assumptions = {**ASSUMPTIONS, **(assumptions or {})}
    if not all(any(p[field] > 0 for p in profiles) for field in ("represented_businesses", "represented_accountants")):
        raise ValueError("A run needs both business and accountant populations for its metrics")
    if concurrency < 1 or assumptions["baseline_support_staff"] <= 0 or assumptions["staff_productivity"] <= 0 or assumptions["baseline_weekly_support_contacts"] <= 0:
        raise ValueError("Concurrency, staffing, productivity, and baseline demand must be positive")
    if not 0 <= assumptions["hotline_priority_share"] < 1 or not all(0 < assumptions[k] <= 1 for k in ("testing_workload_factor", "freeze_workload_factor")):
        raise ValueError("Priority share must be in [0,1); workload factors must be in (0,1]")
    if kind == "nodecision":
        decisions = []
    if kind == "plan_nosurprises":
        events = []
    validate_plan(decisions, profiles, selectors, require_two=kind != "nodecision" and not development)
    if not development and (end_week != 10 or len(profiles) < 24 or any(e.get("hypothetical") for e in events)):
        raise ValueError("Official runs require ten weeks, at least 24 profiles, and no hypothetical fixtures")
    signatures = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ("engine.py", "engine_core.py", "actions.py")}
    manifest = {"engine": "complete-runner-v2", "model_version": MODEL_VERSION,
                "sources": signatures, "company": "quillbook", "type": kind,
                "seed": seed, "model": model, "decisions": decisions, "selectors": selectors,
                "profiles": profiles, "links": links, "events": events, "end_week": end_week,
                "probes": probes, "development": development, "assumptions": assumptions,
                "interactions_off": interactions_off,
                "conversation_version": "reasoned-calendar-v2" if reasoned_messages else "calendar-only-v2"}
    old = folder / "manifest.json"
    if old.exists() and json.loads(old.read_text()) != manifest:
        raise ValueError("Output has different inputs/code; choose a new folder")
    write_json(old, manifest)
    snapshot = folder / "code_snapshot"
    snapshot.mkdir(exist_ok=True)
    for name in signatures:
        (snapshot / name).write_bytes((ROOT / name).read_bytes())
    write_rows(folder / "personas.jsonl", profiles)
    write_json(folder / "run.json", {"company": "quillbook", "type": kind, "seed": seed,
                                     "model": model, "model_version": MODEL_VERSION,
                                     "decisions": decisions, "development": development})
    all_calls = {r["id"]: r for r in read_jsonl(folder / "calls.jsonl")}
    gateway = Gateway(client, model, seed, cache_folder or ROOT / "output/engine_cache")
    state, baseline, weekly, exchanges, probe_rows, support_days = {}, {}, [], [], [], []
    def batch(jobs):
        results, failures = {}, []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            tasks = {pool.submit(gateway.ask, *job): job[0] for job in jobs}
            for future in as_completed(tasks):
                pid = tasks[future]
                try:
                    value, call_id, records = future.result()
                    results[pid] = (value, call_id)
                except RequestFailure as error:
                    records = error.records
                    failures.append({"persona": pid, "error_type": error.error_type})
                for record in records:
                    if record["id"] not in all_calls:
                        all_calls[record["id"]] = record
                        with (folder / "calls.jsonl").open("a") as out:
                            out.write(encode(record) + "\n")
        if failures:
            write_json(folder / "failures.json", failures)
            raise RuntimeError("Some model calls failed. Redacted details in failures.json; rerun identical command to resume.")
        return results

    def run_probe(when):
        week = 0 if when == "start" else 11
        jobs = []
        for p in profiles:
            prompt = ("Answer every exact question as this persona; retain original 1–5 scores, including negatively worded items. "
                      "No reverse scoring. Use the supplied fictional dates, not today's date. "
                      "In each answer, question MUST be the ID (1a, 1b, 2a, 2b, 3a, 3b, 4a, 4b), not the question text.\n"
                      + encode({"persona": p, "state": state[p["id"]], "scenario_calendar": scenario_calendar(week), "questions": QUESTIONS}))
            def check(value):
                if len(value["answers"]) != 8 or {x["question"] for x in value["answers"]} != set(QUESTIONS):
                    raise ValueError("Probe needs each of the eight question IDs once")
            jobs.append((p["id"], week, "probe-" + when, prompt, Probe, check))
        for pid, (value, call_id) in batch(jobs).items():
            probe_rows.extend({"persona": pid, "when": when, "question": answer["question"],
                               "score": answer["score"], "call": call_id} for answer in value["answers"])
        write_rows(folder / "probe.jsonl", probe_rows)

    print(f"{folder.name}: individualized baseline ({len(profiles)} voices)", flush=True)
    jobs = []
    for p in profiles:
        prompt = prompt_for(p, {}, 0, links, [], [], [], {}, baseline=True)
        jobs.append((p["id"], 0, "baseline", prompt, Choice,
                     lambda value, p=p: validate_choice(value, p, {}, [], [], links, baseline=True)))
    for pid, (value, call_id) in batch(jobs).items():
        state[pid] = value
        baseline[pid] = value
    write_json(folder / "baseline.json", baseline)
    if probes:
        run_probe("start")
    baseline_contacts = {"business": 0.0, "accountant": 0.0}
    for p in profiles:
        role = "business" if p["represented_businesses"] else "accountant"
        baseline_contacts[role] += (p["represented_businesses"] or p["represented_accountants"]) * aggregate(p, baseline[p["id"]])["support_contact_fraction"]
    # Anchor service to this sampled population's modeled baseline, not an
    # arbitrary ticket capacity smaller than its starting demand.
    reference = {role: value if value > 0 else assumptions["baseline_weekly_support_contacts"] *
                 sum(p["represented_businesses"] if role == "business" else p["represented_accountants"] for p in profiles)
                 for role, value in baseline_contacts.items()}
    write_json(folder / "support_reference.json", {"contacts": reference,
        "note": "LLM-generated baseline demand; response-time references are dossier 3/8 hours. Comparative proxy, not a calibrated queue."})
    pending, backlog = [], {"reference_contacts": reference}
    for week in range(1, end_week + 1):
        contacts = {"business": 0.0, "accountant": 0.0}
        for p in profiles:
            key = "business" if p["represented_businesses"] else "accountant"
            contacts[key] += (p["represented_businesses"] or p["represented_accountants"]) * aggregate(p, state[p["id"]])["support_contact_fraction"]
        days, backlog = support_week(week, contacts, decisions, assumptions, backlog)
        support_days.extend(days)
        sources = {p["id"]: visible_sources(p, week, events, decisions, selectors) for p in profiles}
        rounds = {}
        for phase, schema in (("observation", Observation), ("choice", Choice)):
            jobs = []
            inboxes = {}
            for p in profiles:
                pid = p["id"]
                inbox = [m for m in pending if m["recipient"] == pid]
                inboxes[pid] = inbox
                observation = rounds.get("observation", {}).get(pid, (None,))[0]
                role = "business" if p["represented_businesses"] else "accountant"
                # Show response experience only when some of this cohort has contacted support.
                support = {"source_id": f"support-{week}-{pid}", "hours": sum(d[role + "_hours"] for d in days) / 7,
                           "exposed_share": aggregate(p, state[pid])["support_contact_fraction"]} if contacts[role] and aggregate(p, state[pid])["support_contact_fraction"] else None
                personal_sources = list(sources[pid])
                if support:
                    personal_sources.append({"id": support["source_id"], "week": week,
                        "kind": "personal_experience", "text": f"Some cohort members contacting support observe modeled average response {support['hours']:.1f} hours. This is a world-model assumption, not a company promise."})
                prompt = prompt_for(p, state[pid], week, links, inbox, personal_sources,
                                    decisions, selectors, observation=observation, support=support,
                                    reasoned_messages=reasoned_messages)
                if schema is Observation:
                    check = lambda value, p=p, s=personal_sources, inbox=inbox: validate_messages(value["outgoing"], p, links, s, inbox)
                else:
                    check = lambda value, p=p, s=personal_sources, inbox=inbox: validate_choice(value, p, state[p["id"]], inbox, s, links,
                        due=p.get("renewal_counts", {}).get(str(week), 0) > 0)
                jobs.append((pid, week, phase, prompt, schema, check))
            results = batch(jobs)
            rounds[phase] = results
            routed = []
            edges = {(e["source"], e["target"]): e for e in links}
            for sender in sorted(results):
                value, call_id = results[sender]
                for i, m in enumerate(value["outgoing"] if phase == "observation" else value["replies"]):
                    routed.append({"id": f"{call_id}-message-{i}", "sender": sender, "recipient": m["recipient"],
                        "text": m["text"], "basis": m["basis"], "source_ids": m["source_ids"],
                        "week": week, "phase": phase, "call": call_id,
                        "recipient_reach_share": edges[(sender, m["recipient"])]["recipient_reach_share"],
                        "verified_world_fact": False})
            if interactions_off:
                routed = []
            exchanges.extend(routed)
            pending = pending + routed if phase == "observation" else routed
        for p in profiles:
            value, call_id = rounds["choice"][p["id"]]
            state[p["id"]] = value
            weekly.append({"persona": p["id"], "week": week, "call": call_id, **value, **aggregate(p, value)})
        write_rows(folder / "weekly.jsonl", weekly)
        write_rows(folder / "interactions.jsonl", exchanges)
        write_rows(folder / "support_daily.jsonl", support_days)
        write_json(folder / "state.json", state)
        print(f"{folder.name}: week {week}/{end_week} saved", flush=True)
    if probes and end_week == 10:
        run_probe("end")
    result = metrics(profiles, weekly, baseline, support_days, decisions, end_week)
    write_json(folder / "metrics.json", result)
    write_json(folder / "completion.json", {"complete": True, "weeks": end_week, "profiles": len(profiles),
        "development": development, "valid_calls": sum(r["valid"] for r in all_calls.values()),
        "all_required_metrics_available": all(result[f"goal_{i}"] is not None for i in range(1, 5))})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "run", "suite", "rehearse"))
    parser.add_argument("--events", default=str(ROOT / "data/official_events.json"))
    parser.add_argument("--plan")
    parser.add_argument("--locked-plan", help="Exact downloaded dashboard JSON; declares these decisions actually locked")
    parser.add_argument("--output", default=str(ROOT / "output/engine_run"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--weeks", type=int, choices=range(1, 11), default=10)
    parser.add_argument("--ids", help="Deprecated: persona subsets are disabled; use all 24")
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--parallel-runs", type=int, choices=range(1, 6), default=3,
                        help="Concurrent final runs; maximum API concurrency is this times --concurrency")
    parser.add_argument("--probes", action="store_true")
    parser.add_argument("--interactions-off", action="store_true")
    parser.add_argument("--reasoned-messages", action=argparse.BooleanOptionalAction, default=True,
                        help="Brief practical reasons in peer advice; enabled in the current model")
    parser.add_argument("--assumptions", help="JSON overrides for support/reliability sensitivity")
    args = parser.parse_args()
    profiles, links, events, decisions, selectors = load_inputs(args.events, args.locked_plan or args.plan)
    if args.locked_plan:
        validate_plan(decisions, profiles, selectors, require_two=True)
    if args.command == "validate":
        print(encode({"profiles": len(profiles), "links": len(links), "events": len(events),
                      "decisions": len(decisions), "cost_usd": validate_plan(decisions, profiles, selectors),
                      "known_crisis": "always included at week 9", "model": args.model}))
        return
    if args.ids:
        raise ValueError("Persona subsets are disabled by user instruction; run all 24 profiles")
    assumptions = json.loads(Path(args.assumptions).read_text()) if args.assumptions else None
    with create_client() as client:
        if args.command == "run":
            result = execute_run(args.output, profiles, links, events, decisions, selectors,
                kind="plan" if decisions else "nodecision", seed=args.seed, model=args.model,
                end_week=args.weeks, probes=args.probes, concurrency=args.concurrency,
                client=client, assumptions=assumptions, interactions_off=args.interactions_off,
                reasoned_messages=args.reasoned_messages)
            print(encode(result))
        else:
            rehearsal = args.command == "rehearse"
            if args.weeks != 10 or (not rehearsal and not args.locked_plan):
                raise ValueError("Final suite needs all profiles, ten weeks, and --locked-plan with the actual download")
            if rehearsal and not args.plan:
                raise ValueError("Rehearsal requires --plan with the supplied actual decision download; missing future decisions remain pending")
            def run_one(item):
                name, (kind, seed, probes) = item
                return execute_run(Path(args.output) / "runs" / name, profiles, links, events, decisions, selectors,
                    kind=kind, seed=seed, model=args.model, probes=probes, development=rehearsal,
                    concurrency=args.concurrency, client=client, assumptions=assumptions,
                    reasoned_messages=args.reasoned_messages)
            with ThreadPoolExecutor(max_workers=args.parallel_runs) as pool:
                list(pool.map(run_one, RUNS.items()))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
